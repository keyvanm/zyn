# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`zyn` is a CLI that routes file-open requests to a single "master" editor session per workspace. Set `$EDITOR=zyn`; calls like `zyn src/app.py:42:5` from anywhere in the workspace tree land in the same editor instance at the right line.

Python 3.14+, single dependency `typer`. Tests with `pytest`. See `README.md` for user-facing usage.

## Commands

Use `uv` for everything Python:

```sh
uv sync                                        # install deps + dev deps
uv run pytest                                  # run the full suite
uv run pytest tests/test_zyn.py::test_name     # single test
uv run zyn ...                                 # invoke the CLI from the source tree
```

Bundle installation is managed via `just` (requires `stow`):

```sh
just                          # list all recipes
just install-cli              # install zyn CLI from GitHub via uv tool
just install-cli-dev          # install from local source (editable)
just fresh-install gatzi      # backup → clear → install a bundle
just fresh-install-all        # same for all bundles + CLI
just backup gatzi             # snapshot ~/.config dirs the bundle touches
just clear gatzi              # wipe those dirs (backs up first by default)
just clear gatzi true         # wipe without backup
just uninstall gatzi          # remove only the symlinks stow owns
just brew gatzi               # install bundle's upstream deps via brew
```

## Architecture

Two-module package under `src/zyn/`:

- `__main__.py` — Typer CLI surface. Parses flags, resolves scope, picks editor class, dispatches one of four modes: `--start` (bootstrap), `--reveal` (focus only), `--detached` (no session), or default (attach + open).
- `editors.py` — All session machinery + editor backends. `Editor` is the abstract base; `Neovim` is the only concrete impl. `EDITORS` dict in `__main__.py` is the registry.

### Session identity

A session is keyed by `(root, SessionScope)`. `SessionScope` carries optional `multiplexer` and `wm_workspace` discriminators detected via env vars + `tmux`/`hyprctl`/`swaymsg`. `Editor.get_socket_for()` md5-hashes the joined components into `$XDG_RUNTIME_DIR/zyn/<hash>.sock`. Empty scope collapses to root-only keying.

`--scope` accepts `none`, `all`, or a comma-list of dimensions in `AVAILABLE_SCOPES`. To add a new scope dimension: add a detector in `editors.py`, extend `SessionScope`, `AVAILABLE_SCOPES`, and `build_scope`.

### Concurrency model

Two `zyn --start` invocations at the same `(root, scope)` must not both spawn editors. The mechanism:

- `Editor.acquire_start_lock()` does atomic `mkdir` on `<hash>.lock`. Holder owns the right to bind the socket.
- `Editor.wait_for_session()` polls for the live socket; bails when the lock disappears (holder gave up) or after `DEFAULT_WAIT_TIMEOUT` (10 s).
- `Editor.discover(..., wait_pending=True)` walks parent dirs and, on hitting a pending lock, waits — this is what lets a yazi pane race-attach to a sibling `zyn --start` rather than open a duplicate nvim.
- Locks older than `STALE_LOCK_AGE_SECONDS` are auto-cleaned by `is_session_pending()`.

`_is_live_socket()` actually connects (with a short timeout) — a bare socket file from a crashed nvim is treated as stale and unlinked.

### Routing into nvim

`Neovim.launch` starts nvim with `--listen <socket>`. `Neovim.open` shells out to `nvim --server <socket> --remote-send` with a `<Esc>:...<CR>` payload that chains `tab drop <file>` per target plus a cursor-positioning ex command on the last target. When `focus=True`, the payload also calls `Zyn.focus()` — a Lua hook expected from the companion `zyn.nvim` plugin; the `type(Zyn)=='table'` guard makes it a no-op when the plugin isn't installed.

### Target parsing

`Target.parse()` uses `rsplit` so a path that literally contains colons is preserved unless the trailing 1–2 segments are all-digits (matches helix/sublime convention). Multi-file open puts the cursor on the *last* target only.

## Bundles

`bundles/` contains curated config sets that wire sibling terminal tools to route through `zyn`. Each bundle is a stow package — its directory tree mirrors `~/.config/`, so `just install <bundle>` symlinks leaf files into place with `stow --no-folding`.

- `gatzi/` — yazi + lazygit. Both point their edit action at `zyn`. Also includes a yazi git-status plugin and a `gi` keybind to launch lazygit from yazi.
- `zennij/` — zellij layouts (`zellij/layouts/zyn.kdl` desktop, `zynm.kdl` mobile/stacked) that spawn `yazi` + `zyn -s` in paired panes.
- `gigazyn/` — nvim pack manifest (`nvim/plugin/gigazyn.lua`) that loads `giga.nvim` + `zyn.nvim` via `vim.pack.add`. Auto-loaded by nvim from `plugin/`; no `require` needed.
- `kitty/` — kitty config (`kitty/kitty.conf`, `kitty/open-actions.conf`) that routes clicked `file://` URLs and OSC 8 hyperlinks to `zyn` via `open-actions.conf` rules, and adds `kitty_mod+p>f|l` hints-kitten keymaps for keyboard-driven path picking.

Each bundle has a `deps.txt` (one brew package per line) consumed by `just brew <bundle>`. Backups land in `$XDG_DATA_HOME/zyn/backups/` (default `~/.local/share/zyn/backups/`).

To add a new bundle: create `bundles/<name>/` mirroring the `~/.config/` subtree it targets, add `deps.txt`, and add it to the `*-all` aggregates in the Justfile.

## Workspace context

This project lives inside a Kaotic Multiplexer workspace (see `../../.claude/CLAUDE.md`). That layer is about typed knowledge-work records and is unrelated to the `zyn` codebase itself — the records framework does not apply when editing code here.
