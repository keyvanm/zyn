# Zyn

> Abandon your IDE and use a master terminal editor tied to a workspace root.

Zyn designates a terminal editor as the master synced to a workspace root, and optionally a multiplexer session, Hyprland workspace or both. Click a file path in your Claude Code terminal, select a file in Yazi, follow any reference — it lands in your master editor for that workspace, at the right line, not in a new pane or window.

Set `$EDITOR=zyn` and `$ZYN_EDITOR=nvim`. Bootstrap a session at your workspace root with `zyn --start`; from then on, every `zyn <file>` inside that tree routes into the same editor. No wiring per tool, no configuration per workspace.

Made primarily for terminal editors, with GUI editor support on the roadmap.

## Install

> [!NOTE]
> Want a fresh install of everything, including the bundles? Go to [Bundles](#bundles).

### 0. Get uv

[uv](https://docs.astral.sh/uv/) manages zyn and its Python runtime.

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 1. Install zyn

```sh
uv tool install git+https://github.com/keyvanm/zyn
```

### 2. Set your environment

```sh
export EDITOR=zyn
export ZYN_EDITOR=nvim   # or helix, etc. — see roadmap
```

Add these to your shell profile to persist them.

## Usage

```sh
cd ~/projects/myrepo
zyn --start                # bootstrap a session here

zyn src/app.py             # opens in the session (from anywhere in the tree)
zyn src/app.py:42:5        # opens at line 42, column 5
zyn a.py b.py c.py:99      # multiple files; cursor lands on the last
zyn --detached notes.md    # raw editor, ignores any session
zyn -w ~/other file.py     # attach to a session at a specific root
zyn --reveal               # focus the editor pane without opening a file
```

`zyn` understands the `path:line:col` convention emitted by ripgrep, grep, ESLint, gcc, and most clickable-path terminal integrations.

## Session scoping

By default, sessions are keyed by `(root, multiplexer session)`. So `zyn --start` in zellij session A and another in zellij session B are independent — opening a file from each routes to the right one, even when they share the same workspace root.

```sh
ZYN_SCOPE=mux,wm           # also scope by WM workspace (hyprland/sway)
zyn --scope none ...       # disable scoping entirely; plain root-only key
```

Hyprland users typically set `ZYN_SCOPE=mux,wm` to get one session per (project, workspace) — same repo can run two parallel editors in two workspaces.

## Pane focus follow

When `zyn` routes a file into a session living in another multiplexer pane (or hyprland workspace), it triggers an editor-side hook that also focuses that pane and/or window — so you actually see the file. Requires the `zyn.nvim` companion plugin in your nvim config; without it, the file still routes, you just stay in the calling pane.

```sh
zyn --no-focus file.py     # opt out for one invocation
ZYN_NO_FOCUS=1             # persistent
```

## Race handling

If a zellij/tmux layout spawns yazi and `zyn --start` in the same instant, `zyn file.py` from yazi waits up to 10 s for the editor pane to bind its socket, then attaches — instead of opening a duplicate. Two concurrent `--start` invocations error explicitly so you don't bootstrap a second editor by accident.

## Bundles

Zyn ships config bundles that wire sibling terminal tools to route through it. Install them with [`just`](https://just.systems) and [`stow`](https://www.gnu.org/software/stow/).

```sh
# brew (macOS)
brew install just stow

# pacman (Arch)
sudo pacman -S just stow
```

Then clone this repo and run:

```sh
just fresh-install-all    # installs zyn + all bundles
just fresh-install gatzi  # or pick individual bundles
```

Each `fresh-install` snapshots your existing config before overwriting it. Backups land in `~/.local/share/zyn/backups/`.

### gatzi — yazi + lazygit

Routes file selection in yazi and lazygit's editor actions through zyn. Also adds a yazi git-status indicator and a `gi` keybind to open lazygit.

```sh
# brew
brew install yazi lazygit git

# pacman
sudo pacman -S yazi lazygit git
```

### zennij — zellij layouts

Two zellij layouts (`zyn` desktop, `zynm` mobile/stacked) that open a yazi explorer and a `zyn --start` editor pane side by side.

```sh
# brew
brew install zellij

# pacman
sudo pacman -S zellij
```

Launch with `zellij --layout zyn` or `zellij --layout zynm`.

### gigazyn — neovim plugins

Drops a neovim pack manifest into `~/.config/nvim/plugin/` that loads [`giga.nvim`](https://github.com/keyvanm/giga.nvim) and [`zyn.nvim`](https://github.com/keyvanm/zyn.nvim) on startup. `zyn.nvim` provides the focus hook that brings the editor pane to the foreground when zyn routes a file.

```sh
# brew
brew install neovim

# pacman
sudo pacman -S neovim
```

## Status

Today: nvim sessions with zellij/tmux scoping, hyprland and sway focus, `path:line:col` parsing, multi-file open, race-safe sibling-pane handoff.

Roadmap: VSCode/Codium/Helix support, tmux config bundle, hyprland bundle, publish to PyPI.
