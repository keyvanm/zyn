# Zyn

> Abandon your IDE and use a master terminal editor tied to a workspace root.

Zyn designates a terminal editor as the master synced to a workspace root, and optionally a multiplexer session, Hyprland workspace or both. Click a file path in your Claude Code terminal, select a file in Yazi, follow any reference — it lands in your master editor for that workspace, at the right line, not in a new pane or window.

Set `$EDITOR=zyn` and `$ZYN_EDITOR=nvim`. Bootstrap a session at your workspace root with `zyn --start`; from then on, every `zyn <file>` inside that tree routes into the same editor. No wiring per tool, no configuration per workspace.

Made primarily for terminal editors, with GUI editor support on the roadmap.

## Usage

```sh
cd ~/projects/myrepo
zyn --start                # bootstrap a session here

zyn src/app.py             # opens in the session (from anywhere in the tree)
zyn src/app.py:42:5        # opens at line 42, column 5
zyn a.py b.py c.py:99      # multiple files; cursor lands on the last
zyn --detached notes.md    # raw editor, ignores any session
zyn -w ~/other file.py     # attach to a session at a specific root
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

## Status

Today: nvim sessions with zellij/tmux scoping, hyprland focus, `path:line:col` parsing, multi-file open, race-safe sibling-pane handoff.

Roadmap: VSCode/Codium/Helix support, sway focus, yazi/zellij/tmux config bundles.
