"""Shared test fixtures.

- Isolates every test from the user's real ``~/.local/share/nix-search/``.
- Patches ``PackageIndex`` everywhere it is imported so screens don't hit a
  real SQLite file (or schedule a background network refresh) during tests.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nixsearch.config import config
from nixsearch.db import IndexInfo


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "nix-search-data"
    data_dir.mkdir()
    monkeypatch.setattr(config, "data_dir", data_dir)
    return data_dir


def _make_mock_index() -> MagicMock:
    """A PackageIndex stand-in: fresh cache, empty results, async refresh."""
    info = IndexInfo(
        channel=config.channel,
        revision="test-rev",
        pkg_count=42,
        fetched_at=int(time.time()),
    )
    m = MagicMock(name="PackageIndex")
    m.info.return_value = info
    m.is_stale.return_value = False
    m.search.return_value = []
    m.get_meta.return_value = None
    m.refresh = AsyncMock(return_value=info)
    return m


@pytest.fixture(autouse=True)
def mock_package_index(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace PackageIndex with a controllable mock in both screen modules.

    Returns the mock instance that ``PackageIndex(...)`` will yield, so tests
    can configure ``mock_package_index.search.return_value = [...]`` etc.
    """
    instance = _make_mock_index()
    monkeypatch.setattr("nixsearch.search_screen.PackageIndex", lambda *a, **kw: instance)
    monkeypatch.setattr("nixsearch.detail_screen.PackageIndex", lambda *a, **kw: instance)
    return instance
