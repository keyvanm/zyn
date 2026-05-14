# Zyn

**The missing session layer for your terminal editor**

Get one editor per project. Every tool routes to it.

Yazi on the left, Claude Code on the right, nvim already open. You press Enter on a file in yazi — a new nvim takes over the pane. You click `src/auth.rs:42` in Claude Code's output — another one spawns somewhere else. The nvim you already had open goes untouched.

With **Zyn**, both route to the same session. Press Enter in yazi or click a path in Claude Code — your existing nvim jumps to that file, at the right line. No new instance. No window-switching.

<!-- TODO: 5–10s asciinema/GIF here. Show: click a path in Claude Code's output → nvim in the next pane jumps to that line. -->

> [!NOTE]
> Zyn started as an acronym — **Z**ellij, **Y**azi, **N**eovim — the three tools it was built to wire together. It outgrew the name. Today zyn works inside any multiplexer (or none), is built to be editor agnostic, and extends to Hyprland and sway workspaces. The wiring stayed.

## The loop

The basic loop works on any system, with any terminal. Open two terminals in your project. In one, run `zyn --start` — your editor boots in that pane. From the other, run `zyn src/app.py:42`. The file appears in the editor, on a new tab, at line 42. Open more terminals; every `zyn <file>` lands in the same editor.

Now scale it. Set `$EDITOR=zyn` and every tool that opens files — Claude Code, yazi, lazygit, ripgrep, every clickable path — routes through the same editor.

The wired version comes in two flavors. Pick whichever matches the stack you already live in.

### Wired with a multiplexer (zellij / tmux)

```
┌────────────┬──────────────────────┐
│            │                      │
│   yazi     │       nvim           │
│ (explorer) │     (editor)         │
│            │                      │
│            ├──────────────────────┤
│            │     terminal         │
│            │                      │
└────────────┴──────────────────────┘
```

Launch zellij with `--layout zyn` — yazi browses your repo on the left with git status inline, your nvim sits on the right, a terminal below for builds, tests, or Claude Code. On tmux, recreate the same three-pane arrangement and the wiring is identical: every pane invokes `zyn`, every `zyn` lands in the editor above.

### Wired with Hyprland or sway

Skip the multiplexer — your WM is the multiplexer. Run yazi, nvim, and a Claude Code terminal in three tiled windows; zyn finds the right session regardless of which window the call comes from.

By default, one repo means one editor — even across workspaces. Drop a terminal on workspace 10, click `src/auth.rs:42`, and the [`zyn.nvim`](#companion-plugin-zynnvim) hook focuses you back to workspace 1 where your nvim lives. Want isolation instead? Set `ZYN_SCOPE=mux,wm` and the same repo opened in two workspaces gets two independent editors — one per workspace, no cross-talk.

### Either way

- Run `rg TODO` in the terminal, click any hit → nvim opens at the match.
- `cargo test` fails at `src/handler.rs:99` → click the path, nvim jumps there.
- ESLint warns about `app/page.tsx:14:7` in your dev server output → same nvim, same session.
- Press `e` on a file in lazygit → opens in your nvim, ready to edit.

One editor. Always.

## The missing layer

How many editor instances do you have open right now? When was the last time you closed a duplicate nvim because some tool spawned it for you?

Every modern IDE has session management baked in. VS Code, Cursor, Zed — all of them know which window owns which workspace, and route file-opens accordingly. The terminal ecosystem doesn't. Each tool — Claude Code, yazi, lazygit, every grep result, every clickable path — invokes `$EDITOR` independently and spawns its own. None know about the editor already running next door.

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

# 3. Set your environment (add this to your shell profile)
export EDITOR=zyn

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

[`zyn.nvim`](https://github.com/keyvanm/zyn.nvim) is what makes the routing visible. zyn delivers the file to the right nvim; zyn.nvim's hook focuses that pane or window so you actually _see_ it. For multiplexer users it's a polish layer — the calling pane stays focused otherwise, one extra keypress away. For Hyprland and sway users on default scoping, it's load-bearing: one editor session covers every workspace, so a click in workspace 10 has to bring you to the nvim on workspace 1, and the hook is what does that.

```lua
-- in ~/.config/nvim/init.lua or any file under ~/.config/nvim/plugin/
vim.pack.add({ "https://github.com/keyvanm/zyn.nvim" })
```

Requires nvim 0.12+ for `vim.pack`. For older versions, use your plugin manager of choice.

## Bundles

zyn.nvim is the first companion. **Bundles** go further — curated configs that wire your other tools (yazi, lazygit, zellij) to use zyn's routing, plus quality-of-life additions.

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

| Bundle      | What it does                                                                                                                                                                                                                                                                                                                                                                  | Upstream deps       |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| **gatzi**   | yazi + lazygit wiring; yazi git-status indicator; `gi` keybind to launch lazygit from yazi. Post-install runs `ya pkg install` to fetch the yazi plugins it depends on.                                                                                                                                                                                                       | yazi, lazygit, git  |
| **zennij**  | Two zellij layouts: `zyn` (desktop), `zynm` (mobile/stacked)                                                                                                                                                                                                                                                                                                                  | zellij              |
| **gigazyn** | nvim pack manifest loading [`giga.nvim`](https://github.com/keyvanm/giga.nvim) and [`zyn.nvim`](https://github.com/keyvanm/zyn.nvim). Replaces a standalone zyn.nvim install. giga.nvim's language pack expects formatters and LSPs (ruff, ty, marksman, stylua, etc.) — see giga.nvim's [Requirements](https://github.com/keyvanm/giga.nvim#requirements) for the full list. | neovim, tree-sitter |

## Coming from VS Code or Cursor?

This is the stack to build toward. Install nvim, set `$EDITOR=zyn`, then pick your tiling:

- **Without a tiling WM**: install zellij and run `just fresh-install-all` — you get yazi + nvim + terminal in one `--layout zyn` window.
- **Hyprland or sway**: skip zellij — your WM already tiles. Run `just fresh-install gatzi` (yazi/lazygit wiring) and `just fresh-install gigazyn` (nvim plugin pack). One editor per repo follows you across every workspace.

The first day you click a Claude Code path and watch it land in the right place, you'll wonder why no one built this sooner.

## What's next

If zyn saves you a context switch today:

- ⭐ **Star the repo** — helps prioritize a PyPI release
- 🐛 **[Open an issue](https://github.com/keyvanm/zyn/issues)** for helix, VS Code, or anything broken
- 💬 **Tell us how you use it** — we're still figuring out who else needs this

**Today**: nvim sessions with optional scoping (multiplexer pane, WM workspace, or both), cross-workspace focus via zyn.nvim on Hyprland/sway, `path:line:col` parsing, multi-file open, race-safe sibling-pane handoff.

**Roadmap**: VSCode/Codium/Helix support, tmux bundle (prebuilt session config + keybinds), hyprland bundle (prebuilt window rules + keybinds), publish to PyPI.