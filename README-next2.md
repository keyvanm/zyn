# Zyn

> **The missing session layer for your terminal.**
>
> One editor per workspace. Every tool routes to it.

You're in your terminal. You click `src/auth.rs:42` in Claude Code's output. You expect a new nvim window. Instead, your existing nvim — already running in the pane next door — jumps to that file, at line 42. No new instance. No window-switching. No re-opening files you already had loaded.

That's zyn.

<!-- TODO: 5–10s asciinema/GIF here. Show: click a path in Claude Code's output → nvim in the next pane jumps to that line. -->

> _Zyn started as an acronym — **Z**ellij, **Y**azi, **N**eovim — the three tools it was built to wire together. It outgrew the name. Today zyn works inside any multiplexer (or none), routes through any tool that respects `$EDITOR`, and extends to Hyprland and sway workspaces. The wiring stayed._

## The loop

The basic loop works on any system, with any terminal. Open two terminals in your project. In one, run `zyn --start` — your editor boots in that pane. From the other, run `zyn src/app.py:42`. The file appears in the editor, on a new tab, at line 42. Open more terminals; every `zyn <file>` lands in the same editor.

That's it. No multiplexer required, no bundles, just zyn.

Now scale it. Set `$EDITOR=zyn` and every tool that opens files — Claude Code, yazi, lazygit, ripgrep, every clickable path — routes through the same editor.

The wired version: zyn + the three bundles + zellij.

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

Launch zellij with `--layout zyn`. Yazi browses your repo on the left, with git status inline. Your nvim sits on the right. A terminal below for builds, tests, or Claude Code.

- Select a file in yazi → opens in nvim, line 1.
- Run a test in the terminal that fails at `src/handler.rs:99` → click the path, nvim jumps there.
- Ask Claude about an unrelated bug. Click the path in its output → nvim again, same session, right line.
- Hit `gi` in yazi to launch lazygit, stage files, exit → your nvim is exactly where you left it.

One editor. Always.

If you use Hyprland or sway, set `ZYN_SCOPE=mux,wm` and the same repo in two workspaces gets two independent editors — one per workspace. No cross-talk.

## What this fixes

How many editor instances do you have open right now? When was the last time you closed a duplicate nvim because some tool spawned it for you?

Every tool in your terminal — Claude Code, yazi, lazygit, every grep result, every clickable path — invokes `$EDITOR` independently. Each spawns its own. None know about the editor already running next door.

zyn fixes this by being the one `$EDITOR` that knows where your editor actually lives.

## The missing layer

Every modern IDE has session management baked in. VS Code, Cursor, Zed — all of them know which window owns which workspace, and route file-opens accordingly. The terminal ecosystem doesn't. Each tool is its own island.

zyn is the missing layer. **Not a wrapper. Not a multiplexer. Not an IDE.** A small Python primitive that lets the tools you already use cooperate.

> _(Tried yazelix? It depends on Nix and locks you into Zellij. zyn is a single Python tool that works with whatever stack you already have.)_

## Install

Required: **nvim**, **uv** (we'll install it in step 1).
Optional: a multiplexer (zellij or tmux).

```sh
# 1. Install uv (skip if you have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install zyn
uv tool install git+https://github.com/keyvanm/zyn

# 3. Set your environment (add these to your shell profile)
export EDITOR=zyn
export ZYN_EDITOR=nvim

# 4. Bootstrap a session at your workspace root
cd ~/projects/myrepo
zyn --start
```

You're done. From anywhere in this repo, `zyn src/app.py:42` opens that file in your nvim session, at line 42.

```sh
zyn src/app.py:42:5         # open at line 42, column 5
zyn a.py b.py c.py:99       # multiple files; cursor lands on the last
zyn --reveal                # focus the editor pane without opening a file
zyn --detached notes.md     # raw editor, ignores any session
zyn -w ~/other file.py      # attach to a session at a specific root
```

zyn understands the `path:line:col` convention emitted by Claude Code, ripgrep, grep, ESLint, gcc, and most clickable-path terminal integrations. For the full surface, run `zyn --help`.

## Companion plugin: zyn.nvim

[`zyn.nvim`](https://github.com/keyvanm/zyn.nvim) completes the experience. When zyn routes a file to a session in another pane (or another Hyprland workspace), zyn.nvim's hook focuses that pane — so you actually _see_ the file. Without it, the file still routes; you just stay in the calling pane.

```lua
-- in any file under ~/.config/nvim/plugin/
vim.pack.add({ "https://github.com/keyvanm/zyn.nvim" })
```

Requires nvim 0.12+ for `vim.pack`. For older versions, use your plugin manager of choice.

## Bundles

zyn.nvim is the first companion. **Bundles** are more — curated configs that wire your other tools (yazi, lazygit, zellij) to use zyn's routing, plus quality-of-life additions.

```sh
# install just + stow first (the bundle install mechanism)
brew install just stow                  # macOS
sudo pacman -S just stow                # Arch

# then install one bundle, or all of them
just fresh-install gatzi
just fresh-install-all                  # all bundles + zyn CLI
```

> [!NOTE]
> Fresh-install backs up the `~/.config/` directories the bundle touches to `~/.local/share/zyn/backups/` before replacing them. Originals are recoverable.

Each bundle has a `deps.txt` listing the system packages it depends on. Install them with `just brew <bundle>` (macOS) or your package manager of choice.

Prefer to integrate manually? Each bundle in `bundles/<name>/` is a stow package — cherry-pick files into your existing config, or run `stow` yourself.

| Bundle      | What it does                                                                                                                                                                  | Upstream deps      |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| **gatzi**   | yazi + lazygit wiring; yazi git-status indicator; `gi` keybind to launch lazygit from yazi. Post-install runs `ya pkg install` to fetch the yazi plugins it depends on.       | yazi, lazygit, git |
| **zennij**  | Two zellij layouts: `zyn` (desktop), `zynm` (mobile/stacked)                                                                                                                  | zellij             |
| **gigazyn** | nvim pack manifest loading [`giga.nvim`](https://github.com/keyvanm/giga.nvim) and [`zyn.nvim`](https://github.com/keyvanm/zyn.nvim). Replaces a standalone zyn.nvim install. giga.nvim's language pack expects formatters and LSPs (ruff, ty, marksman, stylua, etc.) — see giga.nvim's [Requirements](https://github.com/keyvanm/giga.nvim#requirements) for the full list. | neovim, tree-sitter |

## Coming from VS Code or Cursor?

This is the stack to build toward. Install nvim and zellij first; then `just fresh-install-all` to install zyn, zyn.nvim, and all three bundles in one shot. The first day you click a Claude Code path and watch it land in the right pane, you'll wonder why no one built this sooner.

## What's next

If zyn saves you a context switch today:

- ⭐ **Star the repo** — helps prioritize a PyPI release
- 🐛 **[Open an issue](https://github.com/keyvanm/zyn/issues)** for helix, VS Code, or anything broken
- 💬 **Tell us how you use it** — we're still figuring out who else needs this

**Today**: nvim sessions with zellij/tmux scoping, Hyprland and sway focus, `path:line:col` parsing, multi-file open, race-safe sibling-pane handoff.

**Roadmap**: VSCode/Codium/Helix support, tmux config bundle, hyprland bundle, publish to PyPI.
