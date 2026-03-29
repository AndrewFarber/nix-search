from unittest.mock import AsyncMock, patch

import pytest

from nixsearch.app import NixSearchApp
from nixsearch.detail_screen import DetailScreen
from nixsearch.exceptions import NixSearchFailedError
from nixsearch.service import NixLicense, NixMaintainer, NixPackage, NixPackageMetadata

SAMPLE_META = NixPackageMetadata(
    description="A greeting program",
    homepage="https://example.com",
    position="/nix/store/abc-source/pkgs/hello/default.nix:1",
    broken=False,
    unfree=False,
    insecure=False,
    available=True,
    long_description="A longer description\nwith multiple lines.",
    changelog="https://example.com/changelog",
    license=[
        NixLicense(
            full_name="MIT",
            spdx_id="MIT",
            url="https://opensource.org/licenses/MIT",
            free=True,
        )
    ],
    maintainers=[NixMaintainer(name="Alice", email="alice@example.com", github="alice")],
    main_program="hello",
    platforms=["x86_64-linux"],
)

SAMPLE_PKG = NixPackage(
    name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"
)


@pytest.mark.asyncio
async def test_detail_screen_mounts():
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        screen._service = AsyncMock()
        screen._service.get_meta = AsyncMock(return_value=SAMPLE_META)
        app.push_screen(screen)
        await pilot.pause()
        content = screen.query_one("#detail-content")
        assert content is not None


@pytest.mark.asyncio
async def test_detail_screen_shows_metadata():
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        screen._service = AsyncMock()
        screen._service.get_meta = AsyncMock(return_value=SAMPLE_META)
        app.push_screen(screen)
        await pilot.pause()
        text = str(screen.query_one("#detail-content").render())
        assert "hello" in text
        assert "MIT" in text
        assert "https://example.com" in text


@pytest.mark.asyncio
async def test_detail_screen_handles_error():
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        screen._service = AsyncMock()
        screen._service.get_meta = AsyncMock(side_effect=NixSearchFailedError("nix failed"))
        app.push_screen(screen)
        await pilot.pause()
        text = str(screen.query_one("#detail-content").render())
        assert "Failed" in text


@pytest.mark.asyncio
async def test_detail_screen_go_back():
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        screen._service = AsyncMock()
        screen._service.get_meta = AsyncMock(return_value=SAMPLE_META)
        app.push_screen(screen)
        await pilot.pause()
        assert isinstance(app.screen, DetailScreen)
        screen.action_go_back()
        await pilot.pause()
        assert not isinstance(app.screen, DetailScreen)


@pytest.mark.asyncio
async def test_detail_screen_copy_attr():
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        screen._service = AsyncMock()
        screen._service.get_meta = AsyncMock(return_value=SAMPLE_META)
        app.push_screen(screen)
        await pilot.pause()
        # Should not raise
        screen.action_copy_attr()


@pytest.mark.asyncio
async def test_detail_screen_copy_attr_clipboard_failure():
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        screen._service = AsyncMock()
        screen._service.get_meta = AsyncMock(return_value=SAMPLE_META)
        app.push_screen(screen)
        await pilot.pause()
        with patch.object(app, "copy_to_clipboard", side_effect=OSError("no clipboard")):
            screen.action_copy_attr()


@pytest.mark.asyncio
async def test_detail_screen_format_flags():
    meta = NixPackageMetadata(
        description="A broken package",
        homepage="",
        position="",
        broken=True,
        unfree=True,
        insecure=True,
        available=False,
    )
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        screen._service = AsyncMock()
        screen._service.get_meta = AsyncMock(return_value=meta)
        app.push_screen(screen)
        await pilot.pause()
        text = str(screen.query_one("#detail-content").render())
        assert "broken" in text
        assert "unfree" in text
        assert "insecure" in text
        assert "unavailable" in text
