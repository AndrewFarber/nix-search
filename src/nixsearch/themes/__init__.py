from pathlib import Path

from nixsearch.exceptions import UnknownThemeError

THEMES_DIR = Path(__file__).parent


def available_themes() -> list[str]:
    """Return sorted list of available theme names."""
    return sorted(p.stem for p in THEMES_DIR.glob("*.tcss") if p.stem != "base")


def theme_paths(name: str) -> list[Path]:
    """Return list of CSS file paths for the given theme."""
    theme = THEMES_DIR / f"{name}.tcss"
    if not theme.exists():
        raise UnknownThemeError(f"Unknown theme: {name!r} (available: {available_themes()})")
    return [THEMES_DIR / "base.tcss", theme]


def load_theme_css(name: str) -> str:
    """Read and concatenate CSS for the given theme."""
    return "\n".join(p.read_text() for p in theme_paths(name))
