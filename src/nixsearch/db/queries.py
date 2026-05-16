"""Read-only queries against the package index."""

from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel

from nixsearch.service import NixPackage


class IndexInfo(BaseModel):
    channel: str
    revision: str | None
    pkg_count: int
    fetched_at: int


def _quote_fts(query: str) -> str:
    """Quote a user query for safe FTS5 MATCH usage with prefix matching."""
    tokens = [t.replace('"', '""') for t in query.split() if t]
    return " ".join(f'"{t}"*' for t in tokens)


def get_info(conn: sqlite3.Connection, channel: str) -> IndexInfo | None:
    row = conn.execute(
        "SELECT channel, revision, pkg_count, fetched_at FROM channels WHERE channel = ?",
        (channel,),
    ).fetchone()
    if row is None:
        return None
    return IndexInfo(channel=row[0], revision=row[1], pkg_count=row[2], fetched_at=row[3])


def search(
    conn: sqlite3.Connection, query: str, channel: str, limit: int = 200
) -> list[NixPackage]:
    if not query.strip():
        return []
    rows = conn.execute(
        """
        SELECT p.attr_path, p.pname, p.version, p.description
        FROM packages_fts
        JOIN packages p ON p.rowid = packages_fts.rowid
        WHERE packages_fts MATCH ? AND p.channel = ?
        ORDER BY bm25(packages_fts), p.attr_path
        LIMIT ?
        """,
        (_quote_fts(query), channel, limit),
    ).fetchall()
    return [
        NixPackage(
            name=pname,
            nixpkgs_attr=attr_path,
            version=version or "unknown",
            description=description or "",
        )
        for attr_path, pname, version, description in rows
    ]


def get_meta(conn: sqlite3.Connection, attr_path: str, channel: str) -> dict | None:
    row = conn.execute(
        "SELECT meta_json FROM packages WHERE channel = ? AND attr_path = ?",
        (channel, attr_path),
    ).fetchone()
    return json.loads(row[0]) if row else None
