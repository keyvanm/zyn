# Zyn

> The missing session protocol for your terminal stack

Open files in one shared terminal editor per project — anywhere in the worktree, from any tool.

## Why Zyn?

Yazi on the left, Claude Code on the right, nvim already open. You press Enter on a file in yazi and a new nvim takes over the pane. You click `src/auth.rs:42` in Claude Code's output and another one spawns somewhere else. The nvim you already had open is sitting there awkwardly.

With **Zyn**, both route to the same session. Press Enter in yazi or click a path in Claude Code, your existing nvim jumps to that file, at the right line. No new instance. No window-switching.

<!-- TODO: 5–10s asciinema/GIF here. Show: click a path in Claude Code's output → nvim in the next pane jumps to that line. -->

> [!NOTE]
> Zyn started as an acronym (**Z**ellij, **Y**azi, **N**eovim) for the three tools it was built to wire together. It outgrew the name. Today zyn works inside any multiplexer (or none), is built to be editor agnostic, and extends to Hyprland and sway workspaces. The wiring stayed.

## Install

Required: a supported editor (today: **nvim**), **uv** (we'll install it in step 1).
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

## In practice

Here's what zyn looks like wired up: yazi browsing files in one pane, lazygit handling commits in another, Claude Code in a third — every clicked path lands in the same nvim. No new instances. No window-switching.

zyn works without any of the below — set `$EDITOR=zyn` and you're done. But most setups want yazi to open into the session, a zellij layout that pre-panes the workspace, an nvim pack that knows about zyn. We ship those as **integrations**, installable independently:

- **`gatzi`** — yazi's open keys route through zyn; lazygit launches from yazi
- **`zennij`** — zellij layouts (`zyn` desktop, `zynm` mobile/stacked) that pre-pane yazi + nvim + terminal
- **`gigazyn`** — nvim pack: `giga.nvim` (nvim distro) + `zyn.nvim` (zyn's editor-side companion)
- **`kitty`** — clicked-path and OSC 8 hyperlink routing into zyn

Take everything with `just fresh-install-all`, or pick one: `just fresh-install gatzi`. Each integration's full anatomy lives [further down](#bundles).

Works on Linux and macOS — any Unix in theory.

## The loop

The basic loop works on any system, with any terminal. Open two terminals in your project. In one, run `zyn --start`. Your editor boots in that pane. From the other, run `zyn src/app.py:42`. The file appears in the editor, on a new tab, at line 42. Open more terminals; every `zyn <file>` lands in the same editor.

Now scale it. Set `$EDITOR=zyn` and every tool that opens files - Claude Code, yazi, lazygit, ripgrep, every clickable path - routes through the same editor.

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

Launch zellij with `--layout zyn`. Yazi browses your repo on the left with git status inline, your nvim sits on the right, a terminal below for builds, tests, or Claude Code. On tmux, recreate the same three-pane arrangement and the wiring is identical: every pane invokes `zyn`, every `zyn` lands in the editor above.

### Wired with Hyprland or sway

```
── workspace 1 ──────────────────────    ── workspace 10 ──────

┌────────────┐  ┌──────────────────┐     ┌──────────────────┐
│   yazi     │  │       nvim       │     │     terminal     │
│ (explorer) │  │     (editor)     │     │  (Claude Code)   │
│            │  │                  │     │                  │
└────────────┘  └──────────────────┘     └──────────────────┘
```

Skip the multiplexer: your WM is the multiplexer. Run yazi, nvim, and a Claude Code terminal in three tiled windows; zyn finds the right session regardless of which window the call comes from.

By default, one repo means one editor, even across workspaces. Drop a terminal on workspace 10, click `src/auth.rs:42`, and the [`zyn.nvim`](#companion-plugin-zynnvim) hook focuses you back to workspace 1 where your nvim lives. Want isolation instead? Set `ZYN_SCOPE=mux,wm` and the same repo opened in two workspaces gets two independent editors: one per workspace, no cross-talk.

### Either way

- Run `rg TODO` in the terminal, click any hit → nvim opens at the match.
- `cargo test` fails at `src/handler.rs:99` → click the path, nvim jumps there.
- ESLint warns about `app/page.tsx:14:7` in your dev server output → same nvim, same session.
- Press `e` on a file in lazygit → opens in your nvim, ready to edit.

## The missing layer

How many different terminal editor instances do you have open right now? How many of them did you actually mean to open?

Every modern IDE is a container. The terminal, the coding agent, the editor — all live inside it. VS Code, Cursor, Zed: the IDE owns the wall, and routing file-opens is bookkeeping within it.

zyn is the inverse topology. There is no wall — your terminal, your coding agent, your editor are siblings in your WM or multiplexer. What an IDE achieves by _containment_, zyn achieves by _designation_: one sibling is the master editor, and every other tool routes into it.

zyn is the coordination layer. `zyn -s` in one pane promotes the master editor; `$EDITOR=zyn` everywhere else routes into it. One session per project. About 550 lines of Python, one direct dependency (`typer`), plus a tiny rust companion (`zyn-probe`) that gives the yazi opener a sub-10ms session check for flash-free routing. The first implementation routes to nvim.

## What zyn replaces

| Approach                                          | What it does                                                | Where zyn differs                                                                                                  |
| ------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Naive `$EDITOR=nvim`                              | Every tool spawns its own nvim                              | zyn keeps one session per project; every tool routes into it instead of spawning                                   |
| nvim `--server` / `--remote-send`                 | Send commands to a known nvim socket                        | zyn discovers the socket for you, scopes by multiplexer/WM, and handles concurrent `--start` races                 |
| Hand-rolled `tmux send-keys` / zellij glue        | Wire one specific tool into one specific pane with a script | zyn is multiplexer-agnostic (works without one), covers every `$EDITOR` caller at once, and survives crashed nvims |
| [yazelix](https://github.com/luccahuguet/yazelix) | All-in-one Nix flake bundling yazi + zellij + helix/nvim    | One Python tool, no Nix; bring your own stack; works on Hyprland, sway, tmux, or none of the above                 |
| VS Code / Cursor terminal integration             | IDE is primary; routing happens inside the wrapper          | Inverted: the terminal is primary; the terminal editor is the session master                                       |

## The protocol

zyn defines two things.

**A session** is keyed by the project root, plus an optional scope: the active multiplexer pane (zellij, tmux), the active WM workspace (Hyprland, sway), or both. The default keys on project root only, so one repo means one session everywhere you call into it from.

**An editor backend** is any editor that exposes remote commands over a Unix socket. nvim does (`--server` / `--remote-send`). Kakoune already supports it. Helix will, once its socket work lands. A backend lives behind the `Editor` ABC in `editors.py`.

Today there's one backend: nvim. Kakoune and Helix are next. The session model and routing are editor-agnostic; only the wire format (how you tell the editor to open a file at a line) is editor-specific.

## Commands

From anywhere in your repo, `zyn src/app.py:42` opens that file in your nvim session, at line 42.

```sh
zyn src/app.py:42:5         # open at line 42, column 5
zyn a.py b.py c.py:99       # multiple files; cursor lands on the last
zyn --reveal                # focus the editor pane without opening a file
zyn --detached notes.md     # raw editor, ignores any session
zyn -w ~/other file.py      # attach to a session at a specific root
```

zyn understands the `path:line:col` convention emitted by Claude Code, ripgrep, grep, ESLint, gcc, and most clickable-path terminal integrations. For the full surface, run `zyn --help`.

## The nvim companion: zyn.nvim

Each backend may have its own companion plugin that closes the loop on the editor side. For the nvim backend, that's [`zyn.nvim`](https://github.com/keyvanm/zyn.nvim).

zyn delivers the file to the right nvim; zyn.nvim's hook focuses that pane or window so you actually _see_ it. For multiplexer users it's a polish layer: the calling pane stays focused otherwise, one extra keypress away. For Hyprland and sway users on default scoping, it's load-bearing: one editor session covers every workspace, so a click in workspace 10 has to bring you to the nvim on workspace 1, and the hook is what does that.

```lua
-- in ~/.config/nvim/init.lua or any file under ~/.config/nvim/plugin/
vim.pack.add({ "https://github.com/keyvanm/zyn.nvim" })
```

Requires nvim 0.12+ for `vim.pack`. For older versions, use your plugin manager of choice.

## Bundles

Each integration ships as a **bundle** — a stow package under `bundles/<name>/` that symlinks the files into `~/.config/`.

```sh
# install just + stow first (the bundle install mechanism)
brew install just stow                  # macOS
sudo pacman -S just stow                # Arch
sudo apt install just stow              # Debian/Ubuntu
sudo dnf install just stow              # Fedora

# wire one bundle and install its upstream tools
just fresh-install gatzi
just pkg gatzi

# or take everything
just fresh-install-all                  # zyn CLI + all bundle configs
just pkg-all                            # all upstream tools
```

### Anatomy of `just`

| Verb                          | What it does                                                               |
| ----------------------------- | -------------------------------------------------------------------------- |
| `just install <bundle>`       | Symlink the bundle into `~/.config/` via stow. Fails on conflict.          |
| `just fresh-install <bundle>` | Backup → clear → install. Use this if you already have configs in the way. |
| `just uninstall <bundle>`     | Remove zyn's symlinks. Your own files stay.                                |
| `just pkg <bundle>`           | Install upstream tools from `deps.txt`. Auto-detects pacman, apt, dnf, brew. |

Append `-all` to any verb to batch across the full catalog: `just fresh-install-all`, `just uninstall-all`, `just pkg-all`, etc.

Backups land in `~/.local/share/zyn/backups/` as timestamped tarballs. Restore by extracting.

Prefer to integrate manually? Each bundle in `bundles/<name>/` is a stow package. Cherry-pick files into your existing config, or run `stow` yourself.

| Bundle      | What it does                                                                                                                                                                                                                                                                                                                                                                 | Upstream deps       |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| **gatzi**   | yazi + lazygit wiring; yazi git-status indicator; `gi` keybind to launch lazygit from yazi. Post-install runs `ya pkg install` to fetch the yazi plugins it depends on.                                                                                                                                                                                                      | yazi, lazygit, git  |
| **zennij**  | Two zellij layouts: `zyn` (desktop), `zynm` (mobile/stacked)                                                                                                                                                                                                                                                                                                                 | zellij              |
| **gigazyn** | nvim pack manifest loading [`giga.nvim`](https://github.com/keyvanm/giga.nvim) and [`zyn.nvim`](https://github.com/keyvanm/zyn.nvim). Replaces a standalone zyn.nvim install. giga.nvim's language pack expects formatters and LSPs (ruff, ty, marksman, stylua, etc.). See giga.nvim's [Requirements](https://github.com/keyvanm/giga.nvim#requirements) for the full list. | neovim, tree-sitter |
| **kitty**   | kitty config that routes clicked file:// URLs and OSC 8 hyperlinks to zyn, plus a `ctrl+shift+p` hints kitten for keyboard-driven path picking of plain `path:line:col` text.                                                                                                                                                                                                | kitty               |

## Coming from VS Code or Cursor?

Congrats on making the decision to craft your own dev environment. Install nvim, set `$EDITOR=zyn`, then pick your tiling:

- **Without a tiling WM**: run `just fresh-install-all` then `just pkg-all`. You get yazi + nvim + terminal in one `--layout zyn` window.
- **Hyprland or sway**: skip zellij, your WM already tiles. Run `just fresh-install gatzi && just pkg gatzi` (yazi/lazygit wiring) and `just fresh-install gigazyn && just pkg gigazyn` (nvim plugin pack). One editor per repo follows you across every workspace.

## What's next

If zyn saves you a context switch today:

- ⭐ **Star the repo** to help prioritize a PyPI release
- 🐛 **[Open an issue](https://github.com/keyvanm/zyn/issues)** for anything broken
- 💬 **Tell us how you use it**. We're still figuring out who else needs this

**Today**: nvim backend; scoping by multiplexer pane or WM workspace; cross-workspace focus via `zyn.nvim`; `path:line:col` parsing; multi-file open. Bundles: `gatzi`, `zennij`, `gigazyn`, `kitty`.

**Next**: `tmux` bundle, `hyprland` bundle, PyPI release. With those, the bundle catalog is closed.

**Open invitations** (community-shaped, not on the critical path): additional editor backends. Helix and Kakoune are the obvious candidates — see the `Editor` ABC in `editors.py`.
