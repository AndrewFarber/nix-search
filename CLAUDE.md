# nix-search

TUI for searching Nix packages, built with Textual + Pydantic.

## Development

```bash
# direnv auto-loads the nix dev shell
just test        # run all tests (pytest with coverage)
just run         # launch the TUI (PYTHONPATH=src)
just lint        # ruff check + format check
```

## Architecture

- `src/nixsearch/app.py` — Textual App entry point, theme loading
- `src/nixsearch/search_screen.py` — main UI screen with vim-style keybindings
- `src/nixsearch/service.py` — async wrapper around `nix search --json`
- `src/nixsearch/config.py` — Pydantic Settings config (env vars with `NIX_SEARCH_` prefix)
- `src/nixsearch/exceptions.py` — exception hierarchy with auto-logging
- `src/nixsearch/log.py` — file logging to `~/.local/share/nix-search/`
- `src/nixsearch/check_dependencies.py` — verifies `nix` is in PATH
- `src/nixsearch/themes/` — TCSS theme files (dracula, gruvbox, nord, tokyonight)

## Git

- Never include "Co-Authored-By" or any AI/assistant mention in commit messages.

## Testing

Tests live in `src/tests/`. All UI tests use Textual's `run_test()` pilot. Service tests mock `asyncio.create_subprocess_exec`. Target: 99%+ coverage.
