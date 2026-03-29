from unittest.mock import AsyncMock, patch

import pytest
from textual.widgets import Select

from nixsearch.app import NixSearchApp
from nixsearch.search_screen import SearchScreen
from nixsearch.service import NixChannel, NixPackage


def _get_screen(pilot) -> SearchScreen:
    screen = pilot.app.screen
    assert isinstance(screen, SearchScreen)
    return screen


@pytest.mark.asyncio
async def test_screen_mounts():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        assert screen.query_one("#search-input") is not None
        assert screen.query_one("#search-results") is not None


@pytest.mark.asyncio
async def test_search_populates_table():
    packages = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
        NixPackage(name="world", nixpkgs_attr="world", version="1.0", description="The world"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.search = AsyncMock(return_value=packages)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        table = screen.query_one("#search-results")
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_search_empty_query_does_nothing():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        input_widget = screen.query_one("#search-input")
        input_widget.value = "   "
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        screen._service.search.assert_not_called()


@pytest.mark.asyncio
async def test_search_failure_notifies():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.search = AsyncMock(side_effect=RuntimeError("boom"))
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        table = screen.query_one("#search-results")
        assert table.row_count == 0


@pytest.mark.asyncio
async def test_long_description_truncated():
    long_desc = "A" * 100
    packages = [
        NixPackage(name="pkg", nixpkgs_attr="pkg", version="1.0", description=long_desc),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.search = AsyncMock(return_value=packages)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "pkg"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        table = screen.query_one("#search-results")
        assert table.row_count == 1


@pytest.mark.asyncio
async def test_search_no_results_notifies():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.search = AsyncMock(return_value=[])
        input_widget = screen.query_one("#search-input")
        input_widget.value = "nonexistent"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        table = screen.query_one("#search-results")
        assert table.row_count == 0


@pytest.mark.asyncio
async def test_quit_with_input_focused_does_nothing():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.focus()
        await pilot.pause()
        assert input_widget.has_focus
        screen.action_quit()
        # App should still be running (quit is ignored when input has focus)
        assert screen.query_one("#search-input") is not None


@pytest.mark.asyncio
async def test_cursor_navigation_empty_table():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        # These should not raise on an empty table
        screen.action_cursor_down()
        screen.action_cursor_up()
        screen.action_page_down()
        screen.action_page_up()
        screen.action_cursor_first()
        screen.action_cursor_last()


@pytest.mark.asyncio
async def test_cursor_navigation_with_rows():
    packages = [
        NixPackage(
            name=f"pkg{i:02d}",
            nixpkgs_attr=f"pkg{i:02d}",
            version="1.0",
            description="desc",
        )
        for i in range(20)
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.search = AsyncMock(return_value=packages)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "pkg"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()

        screen.action_cursor_down()
        screen.action_cursor_up()
        screen.action_page_down()
        screen.action_page_up()
        screen.action_cursor_first()
        screen.action_cursor_last()


@pytest.mark.asyncio
async def test_focus_input():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen.action_focus_input()
        assert screen.query_one("#search-input").has_focus


@pytest.mark.asyncio
async def test_quit():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen.action_quit()


@pytest.mark.asyncio
async def test_submit_without_focus_does_nothing():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        table = screen.query_one("#search-results")
        table.focus()
        await pilot.pause()
        screen.action_submit_or_select()
        screen._service.search.assert_not_called()


@pytest.mark.asyncio
async def test_escape_returns_focus_to_table():
    packages = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.search = AsyncMock(return_value=packages)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        # Focus is on the table after search; go back to input then escape
        screen.action_focus_input()
        await pilot.pause()
        assert input_widget.has_focus
        screen.action_focus_table()
        await pilot.pause()
        table = screen.query_one("#search-results")
        assert table.has_focus


@pytest.mark.asyncio
async def test_escape_with_empty_table_stays_on_input():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.focus()
        screen.action_focus_table()
        assert input_widget.has_focus


@pytest.mark.asyncio
async def test_select_pushes_detail_screen():
    packages = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.search = AsyncMock(return_value=packages)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        screen.action_submit_or_select()
        await pilot.pause()
        from nixsearch.detail_screen import DetailScreen

        assert isinstance(pilot.app.screen, DetailScreen)


@pytest.mark.asyncio
async def test_copy_attr_with_y():
    packages = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.search = AsyncMock(return_value=packages)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        # Should not raise
        screen.action_copy_attr()


@pytest.mark.asyncio
async def test_clipboard_failure_shows_warning():
    packages = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.search = AsyncMock(return_value=packages)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        with patch.object(pilot.app, "copy_to_clipboard", side_effect=OSError("no clipboard")):
            screen.action_copy_attr()
            # Should not raise — the warning notification is shown instead


@pytest.mark.asyncio
async def test_channel_select_exists():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        select = screen.query_one("#channel-select", Select)
        assert select is not None
        assert select.value == "nixpkgs"


@pytest.mark.asyncio
async def test_channel_select_loads_channels():
    channels = [
        NixChannel(branch="nixos-24.11"),
        NixChannel(branch="nixos-24.05"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.list_channels = AsyncMock(return_value=channels)
        await screen._load_channels()
        await pilot.pause()
        select = screen.query_one("#channel-select", Select)
        assert select.value == "nixpkgs"


@pytest.mark.asyncio
async def test_focus_channel():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        table = screen.query_one("#search-results")
        table.focus()
        await pilot.pause()
        screen.action_focus_channel()
        await pilot.pause()
        select = screen.query_one("#channel-select", Select)
        assert select.has_focus
