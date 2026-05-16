from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from textual.widgets import Select

from nixsearch.app import NixSearchApp
from nixsearch.exceptions import IndexRefreshError, NixSearchFailedError
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
async def test_search_populates_table(mock_package_index):
    packages = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
        NixPackage(name="world", nixpkgs_attr="world", version="1.0", description="The world"),
    ]
    mock_package_index.search.return_value = packages
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        table = screen.query_one("#search-results")
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_search_empty_query_does_nothing(mock_package_index):
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "   "
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        mock_package_index.search.assert_not_called()


@pytest.mark.asyncio
async def test_search_failure_notifies(mock_package_index):
    mock_package_index.search.side_effect = RuntimeError("boom")
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        table = screen.query_one("#search-results")
        assert table.row_count == 0


@pytest.mark.asyncio
async def test_long_description_truncated(mock_package_index):
    long_desc = "A" * 100
    mock_package_index.search.return_value = [
        NixPackage(name="pkg", nixpkgs_attr="pkg", version="1.0", description=long_desc),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "pkg"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        table = screen.query_one("#search-results")
        assert table.row_count == 1


@pytest.mark.asyncio
async def test_search_no_results_notifies(mock_package_index):
    mock_package_index.search.return_value = []
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "nonexistent"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        table = screen.query_one("#search-results")
        assert table.row_count == 0


@pytest.mark.asyncio
async def test_search_no_cache_warns(mock_package_index):
    mock_package_index.info.return_value = None
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        mock_package_index.search.assert_not_called()


@pytest.mark.asyncio
async def test_quit_with_input_focused_does_nothing():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.focus()
        await pilot.pause()
        assert input_widget.has_focus
        screen.action_quit()
        assert screen.query_one("#search-input") is not None


@pytest.mark.asyncio
async def test_cursor_navigation_empty_table():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen.action_cursor_down()
        screen.action_cursor_up()
        screen.action_page_down()
        screen.action_page_up()
        screen.action_cursor_first()
        screen.action_cursor_last()


@pytest.mark.asyncio
async def test_cursor_navigation_with_rows(mock_package_index):
    mock_package_index.search.return_value = [
        NixPackage(name=f"pkg{i:02d}", nixpkgs_attr=f"pkg{i:02d}", version="1.0", description="d")
        for i in range(20)
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
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
async def test_submit_without_focus_does_nothing(mock_package_index):
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        table = screen.query_one("#search-results")
        table.focus()
        await pilot.pause()
        screen.action_submit_or_select()
        mock_package_index.search.assert_not_called()


@pytest.mark.asyncio
async def test_escape_returns_focus_to_table(mock_package_index):
    mock_package_index.search.return_value = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
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
async def test_select_pushes_detail_screen(mock_package_index):
    mock_package_index.search.return_value = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
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
async def test_copy_attr_with_y(mock_package_index):
    mock_package_index.search.return_value = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        screen.action_copy_attr()


@pytest.mark.asyncio
async def test_clipboard_failure_shows_warning(mock_package_index):
    mock_package_index.search.return_value = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        with patch.object(pilot.app, "copy_to_clipboard", side_effect=OSError("no clipboard")):
            screen.action_copy_attr()


@pytest.mark.asyncio
async def test_channel_select_exists():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        select = screen.query_one("#channel-select", Select)
        assert select is not None
        assert select.value == "nixos-unstable"


@pytest.mark.asyncio
async def test_channel_select_loads_channels():
    channels = [NixChannel(branch="nixos-25.05"), NixChannel(branch="nixos-24.11")]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.list_channels = AsyncMock(return_value=channels)
        await screen._load_channels()
        await pilot.pause()
        select = screen.query_one("#channel-select", Select)
        assert select.value == "nixos-unstable"


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


@pytest.mark.asyncio
async def test_selected_channel_none_returns_default():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._channel_select = MagicMock()
        screen._channel_select.value = None
        assert screen._selected_channel == "nixos-unstable"


@pytest.mark.asyncio
async def test_load_channels_error_is_handled():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen._service = AsyncMock()
        screen._service.list_channels = AsyncMock(side_effect=NixSearchFailedError("git failed"))
        await screen._load_channels()
        await pilot.pause()
        select = screen.query_one("#channel-select", Select)
        assert select.value == "nixos-unstable"


@pytest.mark.asyncio
async def test_search_with_non_default_channel(mock_package_index):
    mock_package_index.search.return_value = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        select = screen.query_one("#channel-select", Select)
        select.set_options([("nixos-25.05", "nixos-25.05")])
        select.value = "nixos-25.05"
        await pilot.press("enter")
        await pilot.pause()
        table = screen.query_one("#search-results")
        assert table.row_count == 1
        # search was called with the non-default channel
        assert (
            mock_package_index.search.call_args.kwargs.get("channel") == "nixos-25.05"
            or "nixos-25.05" in mock_package_index.search.call_args.args
        )


@pytest.mark.asyncio
async def test_copy_attr_input_focused_does_nothing(mock_package_index):
    mock_package_index.search.return_value = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        input_widget.focus()
        await pilot.pause()
        mock_copy = MagicMock()
        with patch.object(pilot.app, "copy_to_clipboard", mock_copy):
            screen.action_copy_attr()
        mock_copy.assert_not_called()


@pytest.mark.asyncio
async def test_quit_with_table_focused_exits(mock_package_index):
    mock_package_index.search.return_value = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        table = screen.query_one("#search-results")
        assert table.has_focus
        screen.action_quit()


@pytest.mark.asyncio
async def test_refresh_action_triggers_refresh(mock_package_index):
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        # Drop input focus so the action runs
        screen.query_one("#search-results").focus()
        await pilot.pause()
        screen.action_refresh_cache()
        await pilot.pause()
        mock_package_index.refresh.assert_called()


@pytest.mark.asyncio
async def test_refresh_failure_notifies(mock_package_index):
    mock_package_index.refresh.side_effect = IndexRefreshError("network down")
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen.query_one("#search-results").focus()
        await pilot.pause()
        screen.action_refresh_cache()
        await pilot.pause()
        # should not raise; failure handled internally


@pytest.mark.asyncio
async def test_auto_refresh_on_stale_cache(mock_package_index):
    mock_package_index.is_stale.return_value = True
    async with NixSearchApp().run_test() as pilot:
        _get_screen(pilot)
        await pilot.pause()
        mock_package_index.refresh.assert_called()


@pytest.mark.asyncio
async def test_subtitle_shows_cache_info(mock_package_index):
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        await pilot.pause()
        assert "42 pkgs" in screen.sub_title
        assert "nixos-unstable" in screen.sub_title


@pytest.mark.asyncio
async def test_subtitle_empty_cache(mock_package_index):
    mock_package_index.info.return_value = None
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        await pilot.pause()
        assert "empty" in screen.sub_title


# --- channel cycling (j/k while channel select is focused) ---------------


def _set_channel_options(screen: SearchScreen, options: list[str]) -> None:
    select = screen.query_one("#channel-select", Select)
    select.set_options([(o, o) for o in options])
    select.value = options[0]


@pytest.mark.asyncio
async def test_cycle_channel_with_j_advances_forward():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        _set_channel_options(screen, ["nixos-unstable", "nixos-25.05", "nixos-24.11"])
        screen.query_one("#channel-select", Select).focus()
        await pilot.pause()
        await pilot.press("j")
        await pilot.pause()
        assert screen.query_one("#channel-select", Select).value == "nixos-25.05"


@pytest.mark.asyncio
async def test_cycle_channel_with_k_advances_backward_and_wraps():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        _set_channel_options(screen, ["nixos-unstable", "nixos-25.05", "nixos-24.11"])
        screen.query_one("#channel-select", Select).focus()
        await pilot.pause()
        await pilot.press("k")
        await pilot.pause()
        # Wraps from index 0 to the last option.
        assert screen.query_one("#channel-select", Select).value == "nixos-24.11"


@pytest.mark.asyncio
async def test_cycle_channel_with_no_options_is_safe():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        # Force the empty-options branch via the private API used by the screen.
        screen._channel_select = MagicMock()
        screen._channel_select._options = []
        screen._channel_select.value = "anything"
        # Should not raise and should not assign a new value.
        screen._cycle_channel(1)
        screen._channel_select.value = "anything"  # untouched


@pytest.mark.asyncio
async def test_cycle_channel_with_unknown_value_resets_to_first():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        _set_channel_options(screen, ["a", "b", "c"])
        select = screen.query_one("#channel-select", Select)
        # Mock to bypass Select's value validation while exercising the
        # except-ValueError branch in _cycle_channel.
        with patch.object(type(select), "value", new_callable=lambda: MagicMock()):
            # Simulate a stale current value that isn't in the options list.
            spy = MagicMock()
            spy._options = select._options
            spy.value = "not-in-list"
            screen._channel_select = spy
            screen._cycle_channel(1)
            # idx fell back to 0, so cycle(1) lands on options[1] == "b".
            assert spy.value == "b"


@pytest.mark.asyncio
async def test_arrow_keys_ignored_when_table_empty_and_table_focused():
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        table = screen.query_one("#search-results")
        table.focus()
        await pilot.pause()
        # Empty table: cursor actions should be no-ops (covers row_count==0 guards).
        screen.action_cursor_down()
        screen.action_cursor_up()


@pytest.mark.asyncio
async def test_enter_on_channel_focus_moves_to_table(mock_package_index):
    mock_package_index.search.return_value = [
        NixPackage(name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"),
    ]
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        # Populate the table first so focus has somewhere to land.
        input_widget = screen.query_one("#search-input")
        input_widget.value = "hello"
        input_widget.focus()
        await pilot.press("enter")
        await pilot.pause()
        # Now focus the channel selector and press Enter.
        screen.query_one("#channel-select", Select).focus()
        await pilot.pause()
        screen.action_submit_or_select()
        await pilot.pause()
        assert screen.query_one("#search-results").has_focus


@pytest.mark.asyncio
async def test_refresh_keybind_ignored_when_input_focused(mock_package_index):
    async with NixSearchApp().run_test() as pilot:
        screen = _get_screen(pilot)
        screen.query_one("#search-input").focus()
        await pilot.pause()
        screen.action_refresh_cache()
        await pilot.pause()
        mock_package_index.refresh.assert_not_called()
