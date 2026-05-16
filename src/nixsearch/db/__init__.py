"""SQLite-backed offline index for nixpkgs metadata."""

from __future__ import annotations

import shutil
import time
from contextlib import closing
from pathlib import Path

from nixsearch.config import config
from nixsearch.db import ingest, queries
from nixsearch.db.queries import IndexInfo
from nixsearch.db.schema import connect, create_schema
from nixsearch.log import get_logger
from nixsearch.service import NixPackage

log = get_logger("db")


class PackageIndex:
    """Facade over the SQLite package index.

    Reads are synchronous (microsecond-scale). ``refresh()`` is async because
    it downloads and decompresses ~9 MB / ~350 MB of JSON before ingesting.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (config.data_dir / "packages.db")
        with closing(connect(self.db_path)) as conn:
            create_schema(conn)

    def info(self, channel: str) -> IndexInfo | None:
        with closing(connect(self.db_path)) as conn:
            return queries.get_info(conn, channel)

    def search(self, query: str, channel: str, limit: int = 200) -> list[NixPackage]:
        with closing(connect(self.db_path)) as conn:
            return queries.search(conn, query, channel, limit=limit)

    def get_meta(self, attr_path: str, channel: str) -> dict | None:
        with closing(connect(self.db_path)) as conn:
            return queries.get_meta(conn, attr_path, channel)

    def is_stale(self, channel: str, ttl_days: int) -> bool:
        """True if the channel is missing or older than ``ttl_days``."""
        info = self.info(channel)
        if info is None:
            return True
        return (int(time.time()) - info.fetched_at) > ttl_days * 86_400

    async def refresh(self, channel: str) -> IndexInfo:
        log.info("Refreshing index for %s", channel)
        json_path, revision = await ingest.download_and_decompress(channel)
        try:
            with closing(connect(self.db_path)) as conn:
                return ingest.ingest(conn, channel, json_path, revision)
        finally:
            shutil.rmtree(json_path.parent, ignore_errors=True)


__all__ = ["IndexInfo", "PackageIndex"]
