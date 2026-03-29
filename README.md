# nix-search

A terminal UI for searching [Nix](https://nixos.org/) packages, built with [Textual](https://textual.textualize.io/).

## Features

- Fast, interactive search of nixpkgs
- Channel selector with NixOS release branches
- Package detail screen with metadata, license, and maintainers
- View and edit package source files
- Vim-style keybindings (j/k, Ctrl+d/u, G)
- Multiple color themes: dracula, gruvbox, nord, tokyo-night
- Configurable via environment variables

## Installation

Requires [Nix](https://nixos.org/) with flakes enabled.

```bash
# Run directly
nix run github:AndrewFarber/nix-search

# Or install into your profile
nix profile install github:AndrewFarber/nix-search
```

### NixOS / Home Manager

Add the flake input, then reference the package:

```nix
# flake.nix
{
  inputs.nix-search.url = "github:AndrewFarber/nix-search";

  outputs = { nixpkgs, nix-search, ... }: {
    # ...
  };
}
```

**NixOS (`configuration.nix`):**

```nix
environment.systemPackages = [
  inputs.nix-search.packages.${pkgs.system}.default
];
```

**Home Manager:**

```nix
home.packages = [
  inputs.nix-search.packages.${pkgs.system}.default
];
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

```bash
nix run github:AndrewFarber/nix-search
```

Type a query and press Enter to search. Select a result and press Enter to view package details.

### Keybindings

**Search screen:**

| Key        | Action                              |
|------------|-------------------------------------|
| `/`        | New search                          |
| `Enter`    | Search (input) / Open detail (table)|
| `Escape`   | Return to table                     |
| `j` / `k`  | Cursor down / up                    |
| `Ctrl+d`   | Page down                           |
| `Ctrl+u`   | Page up                             |
| `Home`     | First row                           |
| `End` / `G`| Last row                            |
| `y`        | Copy attribute path to clipboard    |
| `c`        | Focus channel selector              |
| `q`        | Quit                                |

**Channel selector** (after pressing `c`):

| Key        | Action                              |
|------------|-------------------------------------|
| `j` / `k`  | Next / previous channel            |
| `Enter`    | Confirm and return to table         |
| `Escape`   | Return to table                     |

**Detail screen:**

| Key        | Action                              |
|------------|-------------------------------------|
| `Escape`   | Back to search                      |
| `q`        | Back to search                      |
| `y`        | Copy attribute path to clipboard    |
| `e`        | Edit package source                 |

### Configuration

Environment variables (prefix `NIX_SEARCH_`):

| Variable                         | Default    | Description              |
|----------------------------------|------------|--------------------------|
| `NIX_SEARCH_THEME`               | tokyo-night | Theme: dracula, gruvbox, nord, tokyo-night |
| `NIX_SEARCH_CHANNEL`             | nixpkgs    | Default channel / flake ref |
| `NIX_SEARCH_MAX_CHANNELS`        | 5          | Max release branches shown |
| `NIX_SEARCH_EDITOR`              | nvim       | Editor for source viewing |
| `NIX_SEARCH_LOG_LEVEL`           | INFO       | Logging level            |
| `NIX_SEARCH_HALF_PAGE`           | 15         | Half-page scroll size    |
| `NIX_SEARCH_MAX_DESCRIPTION_LENGTH` | 60      | Truncate descriptions    |

## License

[MIT](LICENSE)
