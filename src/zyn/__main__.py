import enum
from pathlib import Path
from typing import Annotated

import typer

from zyn.editors import Editor, Neovim, Target

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
) -> None:
    if start and detached:
        raise typer.BadParameter("--start and --detached are mutually exclusive")

    editor_cls = EDITORS[editor]

    if detached:
        editor_cls().detached(target)
        return

    if start:
        root = workspace or (target.path if target.path.is_dir() else target.path.parent)
        if Editor.has_live_session(root):
            raise typer.BadParameter(f"session already exists at {root}")
        with editor_cls.create_session(root) as e:
            e.launch(target)
        return

    instance = (
        editor_cls.attach(workspace)
        if workspace
        else editor_cls.discover(target.path)
    )
    if instance:
        instance.open(target)
    else:
        editor_cls().detached(target)


if __name__ == "__main__":
    app()
