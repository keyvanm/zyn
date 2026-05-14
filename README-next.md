# Zyn

> **Click a file path anywhere in your terminal — it lands in your editor, at the right line, every time.**

Zyn sits between your terminal and your editor. Every tool that opens a file opens it in the same editor instance per workspace, at the right cursor position.

## The Problem

Every tool in your terminal acts on its own when opening a file.

Click `src/app.py:42` in Claude Code's output — a new nvim opens somewhere. Select a file in yazi — another one. Lazygit's edit action — another one. Each tool invokes `$EDITOR` independently, unaware of the session already running in the next pane.

You end up navigating back to the right editor more often than reading the file.

Zyn fixes this by being the one `$EDITOR` that knows where your editor actually lives.

Unlike yazelix, which depends on Nix and locks you into Zellij, Zyn is a single Python tool that works inside any multiplexer — or none — and extends to Hyprland and sway workspaces.

## Install

> [!NOTE]
> Zyn routes to nvim only today (helix and others are on the [roadmap](#roadmap)). If you don't run a terminal editor yet, see [The Wired Workspace](#the-wired-workspace) first — it shows what zyn enables and the stack to build toward.

### Prerequisites

Required:

- **nvim**
- **uv** — manages zyn's Python runtime. We'll install it in step 1 if you don't have it.

Optional:

- **A multiplexer** (zellij or tmux) — zyn works without one, but unlocks per-session scoping when you have one.

### Steps

1. **Install uv** (skip if you already have it):

    ```sh
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2. **Install zyn**:

    ```sh
    uv tool install git+https://github.com/keyvanm/zyn
    ```

3. **Set your environment**:

    ```sh
    export EDITOR=zyn
    export ZYN_EDITOR=nvim
    ```

    Add these to your shell profile to persist them.

4. **Bootstrap a session** at your workspace root:

    ```sh
    cd ~/projects/myrepo
    zyn --start
    ```

You're done. From anywhere in this repo, `zyn src/app.py:42` opens that file in your nvim session, at line 42.

## Usage

```sh
zyn src/app.py:42:5         # open at line 42, column 5
zyn a.py b.py c.py:99       # multiple files; cursor lands on the last
zyn --reveal                # focus the editor pane without opening a file
zyn --detached notes.md     # raw editor, ignores any session
zyn -w ~/other file.py      # attach to a session at a specific root
```

Zyn understands the `path:line:col` convention emitted by Claude Code, ripgrep, grep, ESLint, gcc, and most clickable-path terminal integrations — clicking a result anywhere in your terminal lands the file in the right editor, at the right line.

For the full surface, run `zyn --help`.

## zyn.nvim

[`zyn.nvim`](https://github.com/keyvanm/zyn.nvim) is the companion plugin that completes the experience. When zyn routes a file into a session living in another multiplexer pane (or Hyprland workspace), it triggers a hook in zyn.nvim that focuses that pane — so you actually see the file. Without it, the file still routes; you just stay in the calling pane.

Add it to your nvim config:

```lua
-- in any file under ~/.config/nvim/plugin/
vim.pack.add({ "https://github.com/keyvanm/zyn.nvim" })
```

Requires nvim 0.12+ for `vim.pack`. For older versions, install via your plugin manager of choice.

## Bundles

zyn.nvim is the first companion. Bundles are more — curated configs that wire your sibling terminal tools (yazi, lazygit, zellij) to use zyn's routing, plus quality-of-life additions like layouts and keybinds.

### Prerequisites

The bundle install mechanism uses [`just`](https://just.systems) and [`stow`](https://www.gnu.org/software/stow/):

```sh
brew install just stow                  # macOS
sudo pacman -S just stow                # Arch
```

### Two install paths

**Fresh install (recommended).**

> [!NOTE]
> Fresh-install backs up the `~/.config/` directories the bundle touches to `~/.local/share/zyn/backups/`, then replaces them with the bundle's config. Your originals are recoverable from the backup.

```sh
just fresh-install gatzi                # one bundle
just fresh-install-all                  # all bundles + zyn CLI
```

**Integrate manually.** Each bundle in `bundles/<name>/` is a stow package mirroring `~/.config/`. Cherry-pick files into your existing config, or run stow yourself:

```sh
cd bundles/gatzi
stow --no-folding -t ~/.config .
```

### Available bundles

#### gatzi — yazi + lazygit

Routes file selection in yazi and lazygit's editor actions through zyn. Adds a yazi git-status indicator and a `gi` keybind to open lazygit from yazi.

```sh
brew install yazi lazygit git           # macOS
sudo pacman -S yazi lazygit git         # Arch

just fresh-install gatzi
```

#### zennij — zellij layouts

Two zellij layouts that open a yazi explorer and a `zyn --start` editor pane side by side: `zyn` (desktop) and `zynm` (mobile/stacked).

```sh
brew install zellij                     # macOS
sudo pacman -S zellij                   # Arch

just fresh-install zennij
```

Launch with `zellij --layout zyn` or `zellij --layout zynm`.

#### gigazyn — neovim plugins

Drops a neovim pack manifest into `~/.config/nvim/plugin/` that loads [`giga.nvim`](https://github.com/keyvanm/giga.nvim) and [`zyn.nvim`](https://github.com/keyvanm/zyn.nvim) on startup. If you already added zyn.nvim standalone, you can remove that line — gigazyn covers it.

```sh
brew install neovim                     # macOS
sudo pacman -S neovim                   # Arch

just fresh-install gigazyn
```

## The Wired Workspace

Install zyn, zyn.nvim, and the three bundles, and your terminal looks like this:

```
┌────────────┬──────────────────────┐
│            │                      │
│   yazi     │       nvim           │
│ (explorer) │     (editor)         │
│            │                      │
├────────────┴──────────────────────┤
│   terminal                        │
└───────────────────────────────────┘
```

Launch it with `zellij --layout zyn`. Yazi browses your repo on the left with git status inline. Your nvim session lives on the right. A terminal sits below for builds, tests, or Claude Code.

The loop: select a file in yazi — it opens in nvim. Run a test in the terminal that fails at `src/auth.rs:42` — click the path, nvim jumps there. Ask Claude about an unrelated bug; click `src/handler.rs:99` in its output — nvim again, same session, line 99. Hit `g,i` in yazi to launch lazygit, stage files, exit — your nvim is exactly where you left it.

If you use Hyprland or sway, set `ZYN_SCOPE=mux,wm` and the same repo in two workspaces gets two independent editor sessions — one per workspace, no cross-talk.

That's the wired workspace. For laptops or stacked layouts, `zellij --layout zynm` gives you the same panes in a mobile-friendly variant.

**Coming from VS Code or Cursor?** This is the stack to build toward. Install nvim and zellij first; then run `just fresh-install-all` to install zyn, zyn.nvim, and all three bundles in one shot.