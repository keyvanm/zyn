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


@app.callback()
def callback(
    ctx: typer.Context,
    editor: Annotated[
        EditorName, typer.Option(envvar="ZYN_EDITOR")
    ] = EditorName.nvim,
):
    ctx.obj = EDITORS[editor]


@app.command()
def start(
    ctx: typer.Context,
    workspace_root: Annotated[
        Path | None, typer.Option("-w", "--workspace", default_factory=Path.cwd)
    ],
):
    editor_cls: type[Editor] = ctx.obj
    editor_cls(root=workspace_root)


@app.command()
def main(ctx: typer.Context, file: Annotated[Path, typer.Argument()]) -> None:
    editor_cls: type[Editor] = ctx.obj

    editor = editor_cls.discover(file)
    print(editor)
    if editor:
        editor.open(file)
    else:
        root = file if file.is_dir() else file.parent
        with editor_cls(root=root) as editor:
            editor.start(file)


if __name__ == "__main__":
    app()
