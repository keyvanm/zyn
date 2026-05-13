# Zyn

Route edit intents to your workspace's master editor

Zyn routes edit intents — a file path with an optional cursor location — to the master editor of the current workspace. The master editor is whichever editor instance you launched first in that context; its launch directory becomes the workspace root.

Open a file in Yazi, click a file link in a Claude Code terminal, or follow any path reference — Zyn walks up the directory tree to find the nearest registered root and delivers the intent to its editor. If no master editor is running, Zyn opens one and it becomes the master for that root.

Works across Zellij tabs, tmux windows, Hyprland workspaces, and virtual desktops on KDE, GNOME, and macOS.
