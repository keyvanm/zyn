import os
from pathlib import Path
from typing import Annotated

import typer

from zyn.editors import Editor, Neovim

app = typer.Typer()

EDITORS: dict[str, type[Editor]] = {
    "nvim": Neovim,
}


@app.command()
def main(file: Annotated[Path, typer.Argument()]) -> None:
    file = file.resolve()
    editor_name = os.environ.get("ZYN_EDITOR", "nvim")
    editor_cls = EDITORS.get(editor_name)
    if editor_cls is None:
        raise typer.BadParameter(
            f"unsupported editor: {editor_name}", param_hint="ZYN_EDITOR"
        )

    editor = editor_cls.find(file)
    if editor:
        editor.open(file)
    else:
        root = file if file.is_dir() else file.parent
        with editor_cls(root=root) as editor:
            editor.start(file)


if __name__ == "__main__":
    app()
