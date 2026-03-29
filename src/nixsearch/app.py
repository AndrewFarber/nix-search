import sys

from textual.app import App

from nixsearch.check_dependencies import check_dependencies
from nixsearch.config import config
from nixsearch.exceptions import MissingDependencyError
from nixsearch.log import get_logger, setup_logging
from nixsearch.search_screen import SearchScreen
from nixsearch.themes import load_theme_css

log = get_logger("app")


class NixSearchApp(App):
    TITLE = "nix-search"
    SUB_TITLE = "Nix Package Search"
    ENABLE_COMMAND_PALETTE = False
    ansi_color = False

    def __init__(self, theme_name: str = "tokyonight"):
        super().__init__()
        self.CSS = load_theme_css(theme_name)

    def on_mount(self) -> None:
        self.push_screen(SearchScreen())


def main():
    setup_logging()
    try:
        check_dependencies()
    except MissingDependencyError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    log.info("nix-search starting")
    app = NixSearchApp(theme_name=config.theme)
    try:
        app.run()
    except Exception:
        log.exception("nix-search crashed")
        raise
    log.info("nix-search exiting")
