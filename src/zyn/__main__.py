import enum
from pathlib import Path
from typing import Annotated

import typer

from zyn.editors import (
    DEFAULT_SCOPE,
    Editor,
    Neovim,
    Target,
    build_scope,
    parse_scope,
)

app = typer.Typer()


class EditorName(str, enum.Enum):
    nvim = "nvim"


EDITORS: dict[EditorName, type[Editor]] = {
    EditorName.nvim: Neovim,
}


@app.command()
def main(
    targets: Annotated[
        list[Target] | None,
        typer.Argument(
            parser=Target.parse,
            help="One or more files to open, each optionally with :line or :line:col",
        ),
    ] = None,
    editor: Annotated[
        EditorName, typer.Option("-e", "--editor", envvar="ZYN_EDITOR")
    ] = EditorName.nvim,
    start: Annotated[
        bool,
        typer.Option(
            "-s", "--start", help="Bootstrap a new session at the resolved root"
        ),
    ] = False,
    detached: Annotated[
        bool,
        typer.Option(
            "-d", "--detached", help="Skip discovery, run editor without a session"
        ),
    ] = False,
    workspace: Annotated[
        Path | None,
        typer.Option("-w", "--workspace", help="Use ROOT as session root, no walk-up"),
    ] = None,
    scope: Annotated[
        str,
        typer.Option(
            "--scope",
            envvar="ZYN_SCOPE",
            help="Scope dimensions: comma-list of mux,wm — or 'all'/'none'",
        ),
    ] = DEFAULT_SCOPE,
    no_focus: Annotated[
        bool,
        typer.Option(
            "--no-focus",
            envvar="ZYN_NO_FOCUS",
            help="Don't trigger editor-side focus after routing",
        ),
    ] = False,
) -> None:
    if start and detached:
        raise typer.BadParameter("--start and --detached are mutually exclusive")

    try:
        session_scope = build_scope(parse_scope(scope))
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--scope") from e

    if not targets:
        targets = [Target(Path.cwd())]

    editor_cls = EDITORS[editor]
    primary = targets[0].path

    if detached:
        editor_cls().detached(targets)
        return

    if start:
        root = workspace or (primary if primary.is_dir() else primary.parent)
        if Editor.has_live_session(root, session_scope):
            raise typer.BadParameter(f"session already exists at {root}")
        lock = Editor.acquire_start_lock(root, session_scope)
        if lock is None:
            raise typer.BadParameter(
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
        editor_cls.attach(workspace, session_scope)
        if workspace
        else editor_cls.discover(primary, session_scope, wait_pending=True)
    )
    if instance:
        instance.open(targets, focus=not no_focus)
    else:
        editor_cls().detached(targets)


if __name__ == "__main__":
    app()
