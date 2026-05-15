# CLAUDE.md

`zyn` routes file-open requests to one "master" editor session per workspace. Set `$EDITOR=zyn`; calls like `zyn src/app.py:42` land in the same editor anywhere in the tree. See `README.md` for user-facing usage.

## Two binaries

- **`zyn`** — Python CLI (`src/zyn/`, dep: `typer`, tests: `pytest`). Session bootstrap, discovery, locking, nvim remote-send.
- **`zyn-probe`** — Rust binary (`zyn-probe/`, cargo workspace at repo root). Fast read-only "is there a live session for this path?" check. Exists because python's cold-start was perceptible as a UI flash on every yazi-driven file open.

**Lockstep constraint:** the socket-keying scheme (md5 of abs path joined with scope components, sockets under `$XDG_RUNTIME_DIR/zyn/`) is duplicated between `src/zyn/editors.py` and `zyn-probe/src/main.rs`. Changes on either side must be mirrored. No parity test today — add one if this drifts.

## Commands

- Python: `uv run pytest`, `uv run zyn ...`
- Rust: `cargo build --release`, `cargo install --path zyn-probe`
- Install + bundles: `just` (run with no args for the list)

## Layout

- `src/zyn/`, `tests/` — python CLI + suite
- `zyn-probe/` — rust probe (workspace member)
- `plugins/<name>.yazi/` — tool plugins; bundles consume them via relative symlinks
- `bundles/<name>/` — stow packages mirroring `~/.config/` subtrees

## Bundles

Each `bundles/<name>/` is a `stow --no-folding` package: its tree mirrors `~/.config/` and `just install <name>` symlinks each leaf file into place. Bundles wire sibling tools to route through `zyn`.

- `gatzi/` — yazi + lazygit. Wires `plugins/zyn.yazi` into yazi's open keys for flash-free routing.
- `zennij/` — zellij layouts (`zyn` desktop, `zynm` mobile/stacked) pairing yazi with `zyn -s`.
- `gigazyn/` — nvim pack manifest loading `giga.nvim` + `zyn.nvim` via `vim.pack`.
- `kitty/` — clicked-path and OSC 8 routing into `zyn`, plus hints-kitten keymaps.

Each bundle's `deps.txt` is the canonical (manager-agnostic) list of upstream packages. `just pkg <name>` detects the package manager (pacman > apt > dnf > brew) and installs via it. Bundles can override per-manager with optional `deps.pacman`, `deps.apt`, `deps.dnf`, `deps.brew` files when names diverge. To add a bundle: create `bundles/<new>/` mirroring its `~/.config/` footprint, drop a `deps.txt`, and add it to the `*-all` aggregates in the `Justfile`.

## Workspace context

This project lives inside a Kaotic Multiplexer workspace (see `../../.claude/CLAUDE.md`). That layer is about typed knowledge-work records and is unrelated to the `zyn` codebase — the records framework does not apply here.
