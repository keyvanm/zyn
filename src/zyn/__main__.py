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
    target: Annotated[
        Target,
        typer.Argument(
            parser=Target.parse,
            default_factory=lambda: Target(Path.cwd()),
            help="File to open, optionally with :line or :line:col",
        ),
    ],
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

    editor_cls = EDITORS[editor]

    if detached:
        editor_cls().detached(target)
        return

    if start:
        root = workspace or (target.path if target.path.is_dir() else target.path.parent)
        if Editor.has_live_session(root, session_scope):
            raise typer.BadParameter(f"session already exists at {root}")
        with editor_cls.create_session(root, session_scope) as e:
            e.launch(target)
        return

    instance = (
        editor_cls.attach(workspace, session_scope)
        if workspace
        else editor_cls.discover(target.path, session_scope)
    )
    if instance:
        instance.open(target, focus=not no_focus)
    else:
        editor_cls().detached(target)


if __name__ == "__main__":
    app()
