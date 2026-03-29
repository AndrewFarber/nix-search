from unittest.mock import MagicMock, patch

import pytest

from nixsearch.app import NixSearchApp, main
from nixsearch.config import Config
from nixsearch.exceptions import MissingDependencyError


def test_app_init():
    app = NixSearchApp()
    assert app.TITLE == "nix-search"
    assert "background" in app.CSS


def test_app_init_with_theme():
    app = NixSearchApp(theme_name="gruvbox")
    assert "#282828" in app.CSS


def test_main():
    mock_config = Config(theme="dracula")
    with (
        patch("nixsearch.app.setup_logging"),
        patch("nixsearch.app.check_dependencies"),
        patch("nixsearch.app.config", mock_config),
        patch("nixsearch.app.NixSearchApp") as mock_app_cls,
    ):
        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app
        main()
        mock_app_cls.assert_called_once_with(theme_name="dracula")
        mock_app.run.assert_called_once()


def test_main_with_theme():
    mock_config = Config(theme="dracula")
    with (
        patch("nixsearch.app.setup_logging"),
        patch("nixsearch.app.check_dependencies"),
        patch("nixsearch.app.config", mock_config),
        patch("nixsearch.app.NixSearchApp") as mock_app_cls,
    ):
        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app
        main()
        mock_app_cls.assert_called_once_with(theme_name="dracula")


def test_main_missing_dependency():
    with (
        patch("nixsearch.app.setup_logging"),
        patch(
            "nixsearch.app.check_dependencies",
            side_effect=MissingDependencyError("missing required commands: nix"),
        ),
    ):
        with pytest.raises(SystemExit, match="1"):
            main()
