"""Write-path: download a channel's packages.json.br and ingest into SQLite.

Data source: ``https://channels.nixos.org/<channel>/packages.json.br`` — the
same dataset ``search.nixos.org`` indexes. Requires the ``brotli`` CLI on PATH.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
import tempfile
import time
import urllib.request
from pathlib import Path

from nixsearch.db.queries import IndexInfo
from nixsearch.exceptions import IndexRefreshError
from nixsearch.log import get_logger

log = get_logger("db.ingest")

CHANNEL_URL = "https://channels.nixos.org/{channel}/packages.json.br"


def split_name_version(name: str) -> tuple[str, str | None]:
    """Split a derivation name like ``foo-1.2.3`` into ``('foo', '1.2.3')``."""
    if not name:
        return ("", None)
    parts = name.rsplit("-", 1)
    if len(parts) == 2 and parts[1] and parts[1][0].isdigit():
        return (parts[0], parts[1])
    return (name, None)


def ingest(
    conn: sqlite3.Connection,
    channel: str,
    json_path: Path,
    revision: str | None,
) -> IndexInfo:
    """Replace ``channel``'s rows with the contents of a decompressed packages.json."""
    with open(json_path) as f:
        payload = json.load(f)
    pkgs = payload.get("packages", {})
    rows = []
    for attr_path, entry in pkgs.items():
        name = entry.get("name") or ""
        pname, version = split_name_version(name)
        meta = entry.get("meta") or {}
        mp = meta.get("maintainersPosition")
        if isinstance(mp, dict) and "file" in mp and "line" in mp and "position" not in meta:
            meta["position"] = f"{mp['file']}:{mp['line']}"
        description = meta.get("description") or ""
        rows.append((channel, attr_path, pname, version, description, json.dumps(meta)))
    now = int(time.time())
    with conn:
        conn.execute("DELETE FROM packages WHERE channel = ?", (channel,))
        conn.executemany(
            "INSERT INTO packages"
            " (channel, attr_path, pname, version, description, meta_json)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.execute("INSERT INTO packages_fts(packages_fts) VALUES('rebuild')")
        conn.execute(
            "INSERT OR REPLACE INTO channels"
            " (channel, revision, pkg_count, fetched_at) VALUES (?, ?, ?, ?)",
            (channel, revision, len(rows), now),
        )
    log.info("Ingested %d packages for %s (rev=%s)", len(rows), channel, revision)
    return IndexInfo(channel=channel, revision=revision, pkg_count=len(rows), fetched_at=now)


async def download_and_decompress(channel: str) -> tuple[Path, str | None]:
    """Download packages.json.br for ``channel`` and decompress to a temp file.

    Returns ``(json_path, revision)``. Caller owns the returned path and is
    responsible for cleaning up the containing temp directory.
    """
    url = CHANNEL_URL.format(channel=channel)
    tmpdir = Path(tempfile.mkdtemp(prefix="nix-search-idx-"))
    br_path = tmpdir / "packages.json.br"
    json_path = tmpdir / "packages.json"

    def _download() -> str | None:
        try:
            with urllib.request.urlopen(url) as resp:
                final_url = resp.geturl()
                with open(br_path, "wb") as out:
                    shutil.copyfileobj(resp, out)
        except OSError as e:
            shutil.rmtree(tmpdir, ignore_errors=True)
            msg = f"failed to download {url}: {e}"
            raise IndexRefreshError(msg) from e
        parts = final_url.split("/")
        try:
            return parts[parts.index("nixos") + 2]
        except (ValueError, IndexError):
            return None

    revision = await asyncio.to_thread(_download)

    try:
        proc = await asyncio.create_subprocess_exec(
            "brotli",
            "-d",
            "-f",
            "-o",
            str(json_path),
            str(br_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        shutil.rmtree(tmpdir, ignore_errors=True)
        msg = "brotli not found in PATH"
        raise IndexRefreshError(msg) from e
    _, stderr = await proc.communicate()
    br_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        shutil.rmtree(tmpdir, ignore_errors=True)
        err = stderr.decode("utf-8", errors="replace").strip()
        msg = f"brotli decompression failed: {err}"
        raise IndexRefreshError(msg)
    return json_path, revision
