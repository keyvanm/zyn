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