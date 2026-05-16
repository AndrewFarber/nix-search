from unittest.mock import MagicMock, patch

import pytest

from nixsearch.app import NixSearchApp
from nixsearch.detail_screen import DetailScreen
from nixsearch.service import NixPackage, NixPackageMetadata, NixSearchService

SAMPLE_PKG = NixPackage(
    name="hello", nixpkgs_attr="hello", version="2.12", description="A greeting"
)

SAMPLE_META_DICT = {
    "description": "A greeting program",
    "homepage": "https://example.com",
    "position": "/nix/store/abc-source/pkgs/hello/default.nix:1",
    "broken": False,
    "unfree": False,
    "insecure": False,
    "available": True,
    "longDescription": "A longer description\nwith multiple lines.",
    "changelog": "https://example.com/changelog",
    "license": [
        {
            "fullName": "MIT",
            "spdxId": "MIT",
            "url": "https://opensource.org/licenses/MIT",
            "free": True,
        }
    ],
    "maintainers": [{"name": "Alice", "email": "alice@example.com", "github": "alice"}],
    "mainProgram": "hello",
    "platforms": ["x86_64-linux"],
}


@pytest.mark.asyncio
async def test_detail_screen_mounts(mock_package_index):
    mock_package_index.get_meta.return_value = SAMPLE_META_DICT
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        content = screen.query_one("#detail-content")
        assert content is not None


@pytest.mark.asyncio
async def test_detail_screen_shows_metadata(mock_package_index):
    mock_package_index.get_meta.return_value = SAMPLE_META_DICT
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        text = str(screen.query_one("#detail-content").render())
        assert "hello" in text
        assert "MIT" in text
        assert "https://example.com" in text


@pytest.mark.asyncio
async def test_detail_screen_handles_missing_cache(mock_package_index):
    mock_package_index.get_meta.return_value = None
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        text = str(screen.query_one("#detail-content").render())
        assert "No metadata cached" in text


@pytest.mark.asyncio
async def test_detail_screen_handles_invalid_meta(mock_package_index):
    # description must be a string; passing a list triggers ValidationError
    mock_package_index.get_meta.return_value = {"description": [1, 2, 3]}
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        # Call the loader directly so we can deterministically inspect the result
        await screen._load_meta()
        text = str(screen.query_one("#detail-content").render())
        assert "Failed to parse" in text
        assert screen._meta is None


@pytest.mark.asyncio
async def test_detail_screen_go_back(mock_package_index):
    mock_package_index.get_meta.return_value = SAMPLE_META_DICT
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        assert isinstance(app.screen, DetailScreen)
        screen.action_go_back()
        await pilot.pause()
        assert not isinstance(app.screen, DetailScreen)


@pytest.mark.asyncio
async def test_detail_screen_copy_attr(mock_package_index):
    mock_package_index.get_meta.return_value = SAMPLE_META_DICT
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        screen.action_copy_attr()


@pytest.mark.asyncio
async def test_detail_screen_copy_attr_clipboard_failure(mock_package_index):
    mock_package_index.get_meta.return_value = SAMPLE_META_DICT
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        with patch.object(app, "copy_to_clipboard", side_effect=OSError("no clipboard")):
            screen.action_copy_attr()


@pytest.mark.asyncio
async def test_detail_screen_format_flags(mock_package_index):
    mock_package_index.get_meta.return_value = {
        "description": "A broken package",
        "homepage": "",
        "position": "",
        "broken": True,
        "unfree": True,
        "insecure": True,
        "available": False,
    }
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        text = str(screen.query_one("#detail-content").render())
        assert "broken" in text
        assert "unfree" in text
        assert "insecure" in text
        assert "unavailable" in text


def test_copy_nix_source(tmp_path):
    source_dir = tmp_path / "pkgs" / "hello"
    source_dir.mkdir(parents=True)
    (source_dir / "default.nix").write_text("{ stdenv }: stdenv.mkDerivation {}")
    (source_dir / "builder.nix").write_text("{ ... }")
    (source_dir / "README.md").write_text("not a nix file")

    position = f"{source_dir}/default.nix:42"
    result_dir, main_file = NixSearchService.copy_nix_source(position)

    assert main_file == "default.nix"
    assert (result_dir / "default.nix").exists()
    assert (result_dir / "builder.nix").exists()
    assert not (result_dir / "README.md").exists()


def test_copy_nix_source_missing_dir():
    position = "/nonexistent/path/default.nix:1"
    with pytest.raises(FileNotFoundError, match="Source directory not found"):
        NixSearchService.copy_nix_source(position)


@pytest.mark.asyncio
async def test_edit_source_no_meta(mock_package_index):
    mock_package_index.get_meta.return_value = SAMPLE_META_DICT
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        screen._meta = None
        screen.action_edit_source()


@pytest.mark.asyncio
async def test_edit_source_no_position(mock_package_index):
    mock_package_index.get_meta.return_value = {"description": "test", "position": None}
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        screen.action_edit_source()


@pytest.mark.asyncio
async def test_edit_source_opens_editor(tmp_path, mock_package_index):
    source_dir = tmp_path / "pkgs" / "hello"
    source_dir.mkdir(parents=True)
    (source_dir / "default.nix").write_text("{ stdenv }: stdenv.mkDerivation {}")

    mock_package_index.get_meta.return_value = {
        "description": "test",
        "position": f"{source_dir}/default.nix:1",
    }
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        with (
            patch("nixsearch.detail_screen.subprocess.run") as mock_run,
            patch.object(app, "suspend", return_value=MagicMock()),
        ):
            screen.action_edit_source()
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert cmd[1].endswith("default.nix")


@pytest.mark.asyncio
async def test_edit_source_source_not_found(mock_package_index):
    mock_package_index.get_meta.return_value = {
        "description": "test",
        "position": "/nonexistent/path/default.nix:1",
    }
    app = NixSearchApp()
    async with app.run_test() as pilot:
        screen = DetailScreen(SAMPLE_PKG)
        app.push_screen(screen)
        await pilot.pause()
        screen.action_edit_source()


def test_sample_meta_dict_parses():
    # Sanity check that the dict literal we use in tests round-trips into the model.
    meta = NixPackageMetadata(**SAMPLE_META_DICT)
    assert meta.description == "A greeting program"
    assert meta.license[0].full_name == "MIT"
    assert meta.long_description.startswith("A longer description")
