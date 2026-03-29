import pytest

from nixsearch.exceptions import UnknownThemeError
from nixsearch.themes import available_themes, load_theme_css, theme_paths


def test_available_themes():
    themes = available_themes()
    assert isinstance(themes, list)
    assert "base" not in themes
    assert "dracula" in themes


def test_theme_paths_default():
    paths = theme_paths("dracula")
    assert len(paths) == 2
    assert paths[0].name == "base.tcss"
    assert paths[1].name == "dracula.tcss"


def test_theme_paths_with_name():
    paths = theme_paths("dracula")
    assert len(paths) == 2
    assert paths[0].name == "base.tcss"
    assert paths[1].name == "dracula.tcss"


def test_theme_paths_unknown():
    with pytest.raises(UnknownThemeError, match="Unknown theme"):
        theme_paths("nonexistent")


def test_load_theme_css():
    css = load_theme_css("gruvbox")
    assert "#search-input" in css  # from base.tcss
    assert "#282828" in css  # from gruvbox.tcss
