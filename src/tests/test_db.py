import io
import json
from contextlib import closing, contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from nixsearch.db import PackageIndex
from nixsearch.db.ingest import ingest, split_name_version
from nixsearch.db.queries import IndexInfo, _quote_fts
from nixsearch.db.schema import connect, create_schema
from nixsearch.exceptions import IndexRefreshError


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "packages.db"


@pytest.fixture
def index(db_path: Path) -> PackageIndex:
    return PackageIndex(db_path=db_path)


@pytest.fixture
def sample_json(tmp_path: Path) -> Path:
    path = tmp_path / "packages.json"
    payload = {
        "version": 2,
        "packages": {
            "hello": {
                "name": "hello-2.12.1",
                "meta": {
                    "description": "A program that produces a familiar greeting",
                    "homepage": "https://www.gnu.org/software/hello/",
                    "broken": False,
                },
            },
            "ripgrep": {
                "name": "ripgrep-14.1.0",
                "meta": {
                    "description": "Recursive search tool like grep but faster",
                    "homepage": "https://github.com/BurntSushi/ripgrep",
                },
            },
            "python3": {
                "name": "python3-3.12.0",
                "meta": {"description": "High-level dynamically-typed language"},
            },
            "noversion": {
                "name": "noversion",
                "meta": {"description": "package with no version suffix"},
            },
        },
    }
    path.write_text(json.dumps(payload))
    return path


# --- split_name_version ---------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("hello-2.12.1", ("hello", "2.12.1")),
        ("ripgrep-14.1.0", ("ripgrep", "14.1.0")),
        ("python3-3.12.0", ("python3", "3.12.0")),
        ("noversion", ("noversion", None)),
        ("foo-bar", ("foo-bar", None)),
        ("foo-bar-1.0", ("foo-bar", "1.0")),
        ("", ("", None)),
    ],
)
def test_split_name_version(name, expected):
    assert split_name_version(name) == expected


# --- _quote_fts -----------------------------------------------------------


def test_quote_fts_single_token():
    assert _quote_fts("hello") == '"hello"*'


def test_quote_fts_multiple_tokens():
    assert _quote_fts("hello world") == '"hello"* "world"*'


def test_quote_fts_escapes_double_quotes():
    assert _quote_fts('foo"bar') == '"foo""bar"*'


def test_quote_fts_empty():
    assert _quote_fts("") == ""
    assert _quote_fts("   ") == ""


# --- schema ---------------------------------------------------------------


def test_connect_does_not_create_directory(tmp_path: Path):
    missing = tmp_path / "nope" / "db.sqlite"
    with pytest.raises(Exception):  # noqa: B017 -- sqlite3.OperationalError
        connect(missing)


def test_create_schema_is_idempotent(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(db_path)) as conn:
        create_schema(conn)
        create_schema(conn)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','index')"
            )
        }
    assert "packages" in tables
    assert "channels" in tables
    assert "packages_fts" in tables
    assert "idx_packages_channel" in tables


# --- ingest ---------------------------------------------------------------


def test_ingest_populates_tables(index: PackageIndex, sample_json: Path):
    with closing(connect(index.db_path)) as conn:
        info = ingest(conn, "nixos-unstable", sample_json, revision="rev-abc")
    assert info.channel == "nixos-unstable"
    assert info.revision == "rev-abc"
    assert info.pkg_count == 4

    with closing(connect(index.db_path)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM packages").fetchone()[0]
        fts_count = conn.execute("SELECT COUNT(*) FROM packages_fts").fetchone()[0]
    assert count == 4
    assert fts_count == 4


def test_ingest_is_atomic_replace_per_channel(
    index: PackageIndex, sample_json: Path, tmp_path: Path
):
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", sample_json, revision="rev-1")

    smaller = tmp_path / "smaller.json"
    smaller.write_text(
        json.dumps({"packages": {"hello": {"name": "hello-3.0", "meta": {"description": "hi"}}}})
    )
    with closing(connect(index.db_path)) as conn:
        info = ingest(conn, "nixos-unstable", smaller, revision="rev-2")

    assert info.pkg_count == 1
    assert info.revision == "rev-2"
    assert index.info("nixos-unstable").pkg_count == 1


def test_ingest_isolates_channels(index: PackageIndex, sample_json: Path):
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", sample_json, revision="u")
        ingest(conn, "nixos-25.05", sample_json, revision="r")
    assert index.info("nixos-unstable").pkg_count == 4
    assert index.info("nixos-25.05").pkg_count == 4


# --- queries --------------------------------------------------------------


def test_info_returns_none_for_unknown_channel(index: PackageIndex):
    assert index.info("nope") is None


def test_search_empty_query_returns_empty(index: PackageIndex, sample_json: Path):
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", sample_json, revision="r")
    assert index.search("   ", "nixos-unstable") == []


def test_search_returns_matches(index: PackageIndex, sample_json: Path):
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", sample_json, revision="r")

    results = index.search("ripgrep", "nixos-unstable")
    assert len(results) == 1
    assert results[0].nixpkgs_attr == "ripgrep"
    assert results[0].name == "ripgrep"
    assert results[0].version == "14.1.0"
    assert "Recursive" in results[0].description


def test_search_prefix_match(index: PackageIndex, sample_json: Path):
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", sample_json, revision="r")
    # "hell" should match "hello" via prefix
    results = index.search("hell", "nixos-unstable")
    assert any(p.nixpkgs_attr == "hello" for p in results)


def test_search_scoped_to_channel(index: PackageIndex, sample_json: Path):
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", sample_json, revision="r")
    assert index.search("hello", "other-channel") == []


def test_search_limit(index: PackageIndex, sample_json: Path):
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", sample_json, revision="r")
    # broad query that hits multiple
    results = index.search("a", "nixos-unstable", limit=2)
    assert len(results) <= 2


def test_get_meta_roundtrip(index: PackageIndex, sample_json: Path):
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", sample_json, revision="r")
    meta = index.get_meta("hello", "nixos-unstable")
    assert meta is not None
    assert meta["homepage"] == "https://www.gnu.org/software/hello/"
    assert meta["broken"] is False


def test_get_meta_missing(index: PackageIndex, sample_json: Path):
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", sample_json, revision="r")
    assert index.get_meta("nonexistent", "nixos-unstable") is None
    assert index.get_meta("hello", "other-channel") is None


# --- IndexInfo model ------------------------------------------------------


def test_index_info_roundtrip():
    info = IndexInfo(channel="x", revision="r", pkg_count=3, fetched_at=123)
    assert info.channel == "x"
    assert info.revision == "r"
    assert info.pkg_count == 3
    assert info.fetched_at == 123


# --- refresh (mocked download) -------------------------------------------


@pytest.mark.asyncio
async def test_refresh_ingests_downloaded_file(
    index: PackageIndex, sample_json: Path, tmp_path: Path
):
    async def fake_download(_channel: str):
        # caller cleans up json_path.parent, so place it under a fresh dir
        dest_dir = tmp_path / "dl"
        dest_dir.mkdir()
        dest = dest_dir / "packages.json"
        dest.write_bytes(sample_json.read_bytes())
        return dest, "rev-downloaded"

    with patch("nixsearch.db.ingest.download_and_decompress", side_effect=fake_download):
        info = await index.refresh("nixos-unstable")

    assert info.pkg_count == 4
    assert info.revision == "rev-downloaded"
    assert not (tmp_path / "dl").exists()  # cleaned up


@contextmanager
def _fake_urlopen(payload: bytes, final_url: str):
    """Yield a context-manager-compatible fake urlopen response."""

    class _Resp(io.BytesIO):
        def geturl(self):
            return final_url

    resp = _Resp(payload)
    try:
        yield resp
    finally:
        resp.close()


@pytest.mark.asyncio
async def test_download_brotli_missing_raises():
    from nixsearch.db import ingest as ingest_mod

    final_url = "https://releases.nixos.org/nixos/unstable/nixos-26.05pre.x/packages.json.br"
    with patch(
        "nixsearch.db.ingest.urllib.request.urlopen",
        return_value=_fake_urlopen(b"compressed-bytes", final_url),
    ):
        with patch(
            "nixsearch.db.ingest.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("no brotli"),
        ):
            with pytest.raises(IndexRefreshError, match="brotli not found"):
                await ingest_mod.download_and_decompress("nixos-unstable")


# --- is_stale -------------------------------------------------------------


def test_is_stale_true_when_channel_missing(index: PackageIndex):
    assert index.is_stale("never-fetched", ttl_days=1) is True


def test_is_stale_false_for_fresh_channel(index: PackageIndex, sample_json: Path):
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", sample_json, revision="r")
    assert index.is_stale("nixos-unstable", ttl_days=1) is False


def test_is_stale_true_for_old_channel(index: PackageIndex, sample_json: Path):
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", sample_json, revision="r")
        # Backdate the cache to two days ago.
        two_days_ago = int(__import__("time").time()) - 2 * 86_400
        conn.execute(
            "UPDATE channels SET fetched_at = ? WHERE channel = ?",
            (two_days_ago, "nixos-unstable"),
        )
        conn.commit()
    assert index.is_stale("nixos-unstable", ttl_days=1) is True


# --- ingest: maintainersPosition fallback ---------------------------------


def test_ingest_normalizes_maintainersPosition(index: PackageIndex, tmp_path: Path):
    path = tmp_path / "packages.json"
    path.write_text(
        json.dumps(
            {
                "packages": {
                    "hello": {
                        "name": "hello-1.0",
                        "meta": {
                            "description": "x",
                            "maintainersPosition": {
                                "file": "/nix/store/abc/pkgs/hello/default.nix",
                                "line": 42,
                            },
                        },
                    }
                }
            }
        )
    )
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", path, revision="r")
    meta = index.get_meta("hello", "nixos-unstable")
    assert meta is not None
    assert meta["position"] == "/nix/store/abc/pkgs/hello/default.nix:42"


def test_ingest_preserves_explicit_position_over_maintainers(index: PackageIndex, tmp_path: Path):
    path = tmp_path / "packages.json"
    path.write_text(
        json.dumps(
            {
                "packages": {
                    "hello": {
                        "name": "hello-1.0",
                        "meta": {
                            "description": "x",
                            "position": "explicit.nix:1",
                            "maintainersPosition": {"file": "fallback.nix", "line": 99},
                        },
                    }
                }
            }
        )
    )
    with closing(connect(index.db_path)) as conn:
        ingest(conn, "nixos-unstable", path, revision="r")
    meta = index.get_meta("hello", "nixos-unstable")
    assert meta is not None
    assert meta["position"] == "explicit.nix:1"


# --- download_and_decompress: error paths --------------------------------


@pytest.mark.asyncio
async def test_download_raises_on_http_oserror():
    from nixsearch.db import ingest as ingest_mod

    def _raise(*_args, **_kwargs):
        raise OSError("network down")

    with patch("nixsearch.db.ingest.urllib.request.urlopen", side_effect=_raise):
        with pytest.raises(IndexRefreshError, match="failed to download"):
            await ingest_mod.download_and_decompress("nixos-unstable")


@pytest.mark.asyncio
async def test_download_returns_none_revision_on_unparseable_url():
    from nixsearch.db import ingest as ingest_mod

    # final URL has no "/nixos/" segment, so revision parsing falls back to None.
    final_url = "https://example.com/some/other/path/packages.json.br"

    class _FakeProc:
        returncode = 0

        async def communicate(self):
            return b"", b""

    async def _fake_exec(*args, **kwargs):
        # The "decompressed" json path is the -o argument; write a stub there
        # so the function's post-conditions hold (the file's content is not
        # consumed by download_and_decompress itself).
        out_path = Path(args[args.index("-o") + 1])
        out_path.write_text("{}")
        return _FakeProc()

    with patch(
        "nixsearch.db.ingest.urllib.request.urlopen",
        return_value=_fake_urlopen(b"compressed-bytes", final_url),
    ):
        with patch("nixsearch.db.ingest.asyncio.create_subprocess_exec", side_effect=_fake_exec):
            json_path, revision = await ingest_mod.download_and_decompress("nixos-unstable")

    assert revision is None
    # Caller owns cleanup; remove the temp dir we just created.
    import shutil as _shutil

    _shutil.rmtree(json_path.parent, ignore_errors=True)


@pytest.mark.asyncio
async def test_download_raises_when_brotli_returns_nonzero():
    from nixsearch.db import ingest as ingest_mod

    final_url = "https://releases.nixos.org/nixos/unstable/nixos-26.05pre.x/packages.json.br"

    class _FailingProc:
        returncode = 1

        async def communicate(self):
            return b"", b"corrupt input"

    async def _fake_exec(*_args, **_kwargs):
        return _FailingProc()

    with patch(
        "nixsearch.db.ingest.urllib.request.urlopen",
        return_value=_fake_urlopen(b"compressed-bytes", final_url),
    ):
        with patch("nixsearch.db.ingest.asyncio.create_subprocess_exec", side_effect=_fake_exec):
            with pytest.raises(IndexRefreshError, match="brotli decompression failed"):
                await ingest_mod.download_and_decompress("nixos-unstable")
