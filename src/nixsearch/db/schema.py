"""SQLite schema and connection management for the package index."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    channel    TEXT PRIMARY KEY,
    revision   TEXT,
    pkg_count  INTEGER NOT NULL,
    fetched_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS packages (
    rowid       INTEGER PRIMARY KEY,
    channel     TEXT    NOT NULL,
    attr_path   TEXT    NOT NULL,
    pname       TEXT    NOT NULL,
    version     TEXT,
    description TEXT,
    meta_json   TEXT    NOT NULL,
    UNIQUE(channel, attr_path)
);

CREATE INDEX IF NOT EXISTS idx_packages_channel ON packages(channel);

CREATE VIRTUAL TABLE IF NOT EXISTS packages_fts USING fts5(
    attr_path, pname, description,
    content='packages',
    content_rowid='rowid',
    tokenize='unicode61'
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection and apply pragmas. Caller must ensure the parent directory exists."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the tables and FTS5 index if they do not already exist."""
    conn.executescript(SCHEMA)
