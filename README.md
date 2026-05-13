# Zyn

> Abandon your IDE, and tie a master terminal editor to a workspace root.

Zyn keeps a master terminal editor synced to a workspace root. Click a file path in your Claude Code terminal, select a file in Yazi, follow any reference — it lands in your master editor for that workspace, at the right line, not in a new pane or window.

Set `$EDITOR=zyn` and `$ZYN_EDITOR=nvim`. Bootstrap a session at your workspace root with `zyn --start`; from then on, every `zyn <file>` inside that tree routes into the same editor. No wiring per tool, no configuration per workspace.

Made primarily for terminal editors, with GUI editor support on the roadmap.

## Usage

```sh
cd ~/projects/myrepo
zyn --start              # bootstrap a session rooted here

zyn src/app.py           # routes into the session (from anywhere inside the tree)
zyn --detached notes.md  # one-off raw editor, ignores any session
zyn -w ~/other file.py   # attach to a session at a specific root
```
