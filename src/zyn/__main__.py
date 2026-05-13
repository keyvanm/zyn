import enum
from pathlib import Path
from typing import Annotated

import typer

from zyn.editors import Editor, Neovim

app = typer.Typer()


class EditorName(str, enum.Enum):
    nvim = "nvim"


EDITORS: dict[EditorName, type[Editor]] = {
    EditorName.nvim: Neovim,
}


@app.command()
def main(
    path: Annotated[Path, typer.Argument(default_factory=Path.cwd)],
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
        editor_cls().open(path)
        return

    if start:
        root = workspace or (path if path.is_dir() else path.parent)
        if Editor.get_socket_for(root).is_socket():
            raise typer.BadParameter(f"session already exists at {root}")
        with editor_cls(root=root) as e:
            e.convert_to_session()
            e.launch()
        return

    if workspace:
        sock = Editor.get_socket_for(workspace)
        instance = (
            editor_cls(root=workspace, session_socket=sock)
            if sock.is_socket()
            else None
        )
    else:
        candidate = editor_cls.discover(path)
        instance = candidate if candidate and candidate.session_socket else None

    if instance:
        instance.open(path)
    else:
        editor_cls().open(path)


if __name__ == "__main__":
    app()
