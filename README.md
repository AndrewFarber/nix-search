# nix-search

A terminal UI for searching [Nix](https://nixos.org/) packages, built with [Textual](https://textual.textualize.io/).

## Features

- Fast, interactive search of nixpkgs
- Vim-style keybindings (j/k, Ctrl+d/u, G)
- Multiple color themes: dracula, gruvbox, nord, tokyonight
- Configurable via environment variables

## Installation

Requires [Nix](https://nixos.org/) with flakes enabled.

```bash
# Run directly
nix run github:AndrewFarber/nix-search

# Or install into your profile
nix profile install github:AndrewFarber/nix-search
```

### Development

```bash
git clone https://github.com/afarber/nix-search.git
cd nix-search
direnv allow   # auto-loads the nix dev shell
just run       # launch the TUI
just test      # run all tests
just lint      # ruff check + format
```

## Usage

Launch with `nix-search`, type a query, and press Enter to search.

### Keybindings

| Key        | Action                              |
|------------|-------------------------------------|
| `/`        | New search                          |
| `Enter`    | Search (input) / Copy install (table) |
| `Escape`   | Return to table                     |
| `j` / `k`  | Cursor down / up                    |
| `Ctrl+d`   | Page down                           |
| `Ctrl+u`   | Page up                             |
| `Home`     | First row                           |
| `End` / `G`| Last row                            |
| `q`        | Quit                                |

### Configuration

Environment variables (prefix `NIX_SEARCH_`):

| Variable                         | Default | Description              |
|----------------------------------|---------|--------------------------|
| `NIX_SEARCH_THEME`               | —       | Theme: dracula, gruvbox, nord, tokyonight |
| `NIX_SEARCH_LOG_LEVEL`           | INFO    | Logging level            |
| `NIX_SEARCH_HALF_PAGE`           | 15      | Half-page scroll size    |
| `NIX_SEARCH_MAX_DESCRIPTION_LENGTH` | 60   | Truncate descriptions    |

## License

[MIT](LICENSE)
