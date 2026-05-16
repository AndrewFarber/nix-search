import subprocess

from pydantic import ValidationError
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from nixsearch.config import config
from nixsearch.db import PackageIndex
from nixsearch.log import get_logger
from nixsearch.service import NixPackage, NixPackageMetadata, NixSearchService

log = get_logger("detail_screen")


class DetailScreen(Screen):
    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("q", "go_back", "Back"),
        Binding("y", "copy_attr", "Copy attr"),
        Binding("e", "edit_source", "Edit source"),
    ]

    def __init__(self, package: NixPackage, channel: str = "nixos-unstable") -> None:
        super().__init__()
        self._package = package
        self._channel = channel
        self._index: PackageIndex | None = None
        self._meta: NixPackageMetadata | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield VerticalScroll(Static(id="detail-content"))
        yield Footer()

    def on_mount(self) -> None:
        content = self.query_one("#detail-content", Static)
        content.update(f"Loading metadata for {self._package.nixpkgs_attr}...")
        self.run_worker(self._load_meta(), exclusive=True, exit_on_error=False)

    async def _load_meta(self) -> None:
        content = self.query_one("#detail-content", Static)
        if self._index is None:
            self._index = PackageIndex()
        index = self._index
        raw = index.get_meta(self._package.nixpkgs_attr, channel=self._channel)
        if raw is None:
            content.update(
                f"No metadata cached for {self._package.nixpkgs_attr} in {self._channel}"
            )
            return
        try:
            meta = NixPackageMetadata(**raw)
        except ValidationError as e:
            log.error("Invalid cached metadata for %s: %s", self._package.nixpkgs_attr, e)
            content.update(Text(f"Failed to parse cached metadata: {e}"))
            return
        self._meta = meta
        content.update(self._format_meta(meta))

    def _format_meta(self, meta: NixPackageMetadata) -> str:
        pkg = self._package
        lines = [
            f"[bold]{pkg.nixpkgs_attr}[/bold]  {pkg.version or 'unknown'}",
            "",
            f"[bold]Description:[/bold]  {meta.description or 'No description'}",
        ]
        if meta.long_description:
            lines.append(f"\n{meta.long_description.strip()}")
        if meta.homepage:
            lines.append(f"\n[bold]Homepage:[/bold]    {meta.homepage}")
        if meta.changelog:
            lines.append(f"[bold]Changelog:[/bold]   {meta.changelog}")
        if meta.license:
            names = ", ".join(lic.full_name for lic in meta.license)
            lines.append(f"[bold]License:[/bold]     {names}")
        if meta.main_program:
            lines.append(f"[bold]Program:[/bold]     {meta.main_program}")
        if meta.maintainers:
            names = ", ".join(m.name or m.github or "unknown" for m in meta.maintainers)
            lines.append(f"[bold]Maintainers:[/bold] {names}")
        if meta.position:
            lines.append(f"[bold]Position:[/bold]    {meta.position}")

        flags = []
        if meta.broken:
            flags.append("[red]broken[/red]")
        if meta.unfree:
            flags.append("[yellow]unfree[/yellow]")
        if meta.insecure:
            flags.append("[red]insecure[/red]")
        if not meta.available:
            flags.append("[red]unavailable[/red]")
        if flags:
            lines.append(f"\n[bold]Flags:[/bold]       {', '.join(flags)}")

        return "\n".join(lines)

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_copy_attr(self) -> None:
        try:
            self.app.copy_to_clipboard(self._package.nixpkgs_attr)
            self.notify(f"Copied: {self._package.nixpkgs_attr}")
        except (OSError, RuntimeError):
            log.warning("Clipboard unavailable")
            self.notify(
                f"Clipboard unavailable — package: {self._package.nixpkgs_attr}",
                severity="warning",
            )

    def action_edit_source(self) -> None:
        if self._meta is None or not self._meta.position:
            self.notify("No source position available", severity="warning")
            return
        try:
            tmp_dir, main_file = NixSearchService.copy_nix_source(self._meta.position)
        except FileNotFoundError as e:
            log.warning("Source not found: %s", e)
            self.notify(f"Source not found: {e}", severity="error")
            return
        file_path = str(tmp_dir / main_file)
        with self.app.suspend():
            subprocess.run([config.editor, file_path], check=False)  # noqa: S603
        self.notify(f"Source files in {tmp_dir}")
