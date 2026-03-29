from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input

from nixsearch.config import config
from nixsearch.log import get_logger
from nixsearch.service import NixPackage, NixSearchService

log = get_logger("search_screen")


class SearchScreen(Screen):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False, priority=True),
        Binding("k", "cursor_up", "Up", show=False, priority=True),
        Binding("ctrl+d", "page_down", "Page Down", show=False, priority=True),
        Binding("ctrl+u", "page_up", "Page Up", show=False, priority=True),
        Binding("home", "cursor_first", "First", show=False, priority=True),
        Binding("end", "cursor_last", "Last", show=False, priority=True),
        Binding("G", "cursor_last", "Last", show=False, priority=True),
        Binding("enter", "submit_or_select", "Select", priority=True),
        Binding("escape", "focus_table", "Back", priority=True),
        Binding("slash", "focus_input", "New Search"),
        Binding("q", "quit", "Quit", show=False, priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Search nixpkgs (Enter to search)...", id="search-input")
        yield DataTable(id="search-results")
        yield Footer()

    def on_mount(self) -> None:
        self._service = NixSearchService()
        self._results: list[NixPackage] = []
        self._table = self.query_one("#search-results", DataTable)
        self._input = self.query_one("#search-input", Input)
        self._table.cursor_type = "row"
        self._table.add_column("Name", width=30)
        self._table.add_column("Version", width=15)
        self._table.add_column("Description")
        self._input.focus()

    def _input_has_focus(self) -> bool:
        return self._input.has_focus

    def _do_search(self) -> None:
        query = self._input.value.strip()
        if query:
            self.run_worker(self._search_worker(query), exclusive=True, exit_on_error=False)

    async def _search_worker(self, query: str) -> None:
        self._table.clear()
        self._results = []
        self.notify("Searching...", timeout=2)
        try:
            results = await self._service.search(query)
        except Exception as e:
            log.error("Search failed for %r: %s", query, e)
            self.notify(f"Search failed: {e}", severity="error")
            return
        self._results = results
        if not results:
            self.notify("No results found", severity="warning")
            return
        for pkg in results:
            desc = pkg.description
            if len(desc) > config.max_description_length:
                desc = desc[: config.max_description_length] + "..."
            self._table.add_row(pkg.name, pkg.version, desc)
        self._table.focus()

    def action_cursor_down(self) -> None:
        if self._input_has_focus() or self._table.row_count == 0:
            return
        self._table.action_cursor_down()

    def action_cursor_up(self) -> None:
        if self._input_has_focus() or self._table.row_count == 0:
            return
        self._table.action_cursor_up()

    def action_page_down(self) -> None:
        if self._input_has_focus() or self._table.row_count == 0:
            return
        target = min(self._table.cursor_row + config.half_page, self._table.row_count - 1)
        self._table.move_cursor(row=target)

    def action_page_up(self) -> None:
        if self._input_has_focus() or self._table.row_count == 0:
            return
        target = max(self._table.cursor_row - config.half_page, 0)
        self._table.move_cursor(row=target)

    def action_cursor_first(self) -> None:
        if self._input_has_focus() or self._table.row_count == 0:
            return
        self._table.move_cursor(row=0)

    def action_cursor_last(self) -> None:
        if self._input_has_focus() or self._table.row_count == 0:
            return
        self._table.move_cursor(row=self._table.row_count - 1)

    def action_submit_or_select(self) -> None:
        if self._input_has_focus():
            self._do_search()
        elif self._table.row_count > 0:
            row_idx = self._table.cursor_row
            if 0 <= row_idx < len(self._results):
                pkg = self._results[row_idx]
                try:
                    self.app.copy_to_clipboard(pkg.name)
                    self.notify(f"Copied: {pkg.name}")
                except Exception:
                    log.warning("Clipboard unavailable")
                    self.notify(f"Clipboard unavailable — package: {pkg.name}", severity="warning")

    def action_focus_input(self) -> None:
        if not self._input_has_focus():
            self._input.focus()

    def action_focus_table(self) -> None:
        if self._input_has_focus() and self._table.row_count > 0:
            self._table.focus()

    def action_quit(self) -> None:
        if not self._input_has_focus():
            self.app.exit()
