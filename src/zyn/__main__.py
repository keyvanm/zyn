import argparse
import enum
import os
from pathlib import Path

from zyn.editors import (
    DEFAULT_SCOPE,
    Editor,
    Neovim,
    Target,
    build_scope,
    parse_scope,
)


class EditorName(str, enum.Enum):
    nvim = "nvim"


EDITORS: dict[EditorName, type[Editor]] = {
    EditorName.nvim: Neovim,
}

_VALID_EDITORS = {e.value for e in EditorName}


def app(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="zyn",
        description="Route file-open requests to one master editor session per workspace.",
    )
    parser.add_argument(
        "targets",
        nargs="*",
        type=Target.parse,
        metavar="TARGET",
        help="One or more files to open, each optionally with :line or :line:col",
    )
    parser.add_argument(
        "-e", "--editor",
        default=os.environ.get("ZYN_EDITOR", EditorName.nvim.value),
        metavar="{" + ",".join(e.value for e in EditorName) + "}",
        help="Editor to use (env: ZYN_EDITOR)",
    )
    parser.add_argument(
        "-s", "--start",
        action="store_true",
        help="Bootstrap a new session at the resolved root",
    )
    parser.add_argument(
        "-d", "--detached",
        action="store_true",
        help="Skip discovery, run editor without a session",
    )
    parser.add_argument(
        "-w", "--workspace",
        type=Path,
        metavar="ROOT",
        help="Use ROOT as session root, no walk-up",
    )
    parser.add_argument(
        "--scope",
        default=os.environ.get("ZYN_SCOPE", DEFAULT_SCOPE),
        help="Scope dimensions: comma-list of mux,wm — or 'all'/'none' (env: ZYN_SCOPE)",
    )
    parser.add_argument(
        "--no-focus",
        action="store_true",
        default=bool(os.environ.get("ZYN_NO_FOCUS")),
        help="Don't trigger editor-side focus after routing (env: ZYN_NO_FOCUS)",
    )
    parser.add_argument(
        "-r", "--reveal",
        action="store_true",
        help="Focus the editor pane without opening a file",
    )

    args = parser.parse_args(argv)

    if args.editor not in _VALID_EDITORS:
        parser.error(f"invalid value for --editor: {args.editor!r} (valid: {', '.join(sorted(_VALID_EDITORS))})")

    mutex = [n for n, on in [("--start", args.start), ("--detached", args.detached), ("--reveal", args.reveal)] if on]
    if len(mutex) > 1:
        parser.error(f"{', '.join(mutex)} are mutually exclusive")
    if args.reveal and args.targets:
        parser.error("--reveal does not take file arguments")

    try:
        session_scope = build_scope(parse_scope(args.scope))
    except ValueError as e:
        parser.error(f"--scope: {e}")

    editor_cls = EDITORS[EditorName(args.editor)]
    targets = args.targets or None

    if args.reveal:
        ref_path = args.workspace or Path.cwd()
        instance = (
            editor_cls.attach(args.workspace, session_scope)
            if args.workspace
            else editor_cls.discover(ref_path, session_scope)
        )
        if not instance:
            parser.error(f"no live session for {ref_path}")
        instance.focus()
        return

    if not targets:
        targets = [Target(Path.cwd())]

    primary = targets[0].path

    if args.detached:
        editor_cls().detached(targets)
        return

    if args.start:
        root = args.workspace or (primary if primary.is_dir() else primary.parent)
        if Editor.has_live_session(root, session_scope):
            parser.error(f"session already exists at {root}")
        lock = Editor.acquire_start_lock(root, session_scope)
        if lock is None:
            parser.error(
                f"session creation in progress at {root}; "
                f"drop --start to wait and attach"
            )
        try:
            with editor_cls.create_session(root, session_scope) as e:
                e.launch(targets)
        finally:
            Editor.release_start_lock(lock)
        return

    instance = (
        editor_cls.attach(args.workspace, session_scope)
        if args.workspace
        else editor_cls.discover(primary, session_scope, wait_pending=True)
    )
    if instance:
        instance.open(targets, focus=not args.no_focus)
    else:
        editor_cls().detached(targets)


if __name__ == "__main__":
    app()
