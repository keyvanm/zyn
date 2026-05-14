# Zyn

> **Click a file path anywhere in your terminal — it lands in your editor, at the right line, every time.**

Zyn sits between your terminal and your editor. Every tool that opens a file opens it in the same editor instance per workspace, at the right cursor position.

## The Problem

Every tool in your terminal acts on its own when opening a file.

Click `src/app.py:42` in Claude Code's output — a new nvim opens somewhere. Select a file in yazi — another one. Lazygit's edit action — another one. Each tool invokes `$EDITOR` independently, unaware of the session already running in the next pane.

You end up navigating back to the right editor more often than reading the file.

Zyn fixes this by being the one `$EDITOR` that knows where your editor actually lives.

Unlike yazelix, which depends on Nix and locks you into Zellij, Zyn is a single Python tool that works inside any multiplexer — or none — and extends to Hyprland and sway workspaces.
