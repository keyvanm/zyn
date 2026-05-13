import hashlib
import itertools
import os
from pathlib import Path

import typer

from zyn.editors import EDITORS

app = typer.Typer()


def get_sockets_dir() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return Path(runtime) / "zyn"


def get_socket_for_root(path: Path) -> Path:
    key = hashlib.md5(str(path).encode()).hexdigest()
    return get_sockets_dir() / f"{key}.sock"


def find_socket(path: Path) -> Path | None:
    dir_path = path if path.is_dir() else path.parent
    for directory in itertools.chain([dir_path], dir_path.parents):
        sock = get_socket_for_root(directory)
        if sock.is_socket():
            return sock
    return None


@app.command()
def main(file: Path = Path.cwd()) -> None:
    editor_name = os.environ.get("ZYN_EDITOR", "nvim")
    editor = EDITORS.get(editor_name)
    if editor is None:
        raise typer.BadParameter(f"unsupported editor: {editor_name}", param_hint="ZYN_EDITOR")

    socket = find_socket(file)

    if socket:
        editor.open(socket, file)
    else:
        get_sockets_dir().mkdir(parents=True, exist_ok=True)
        sock = get_socket_for_root(file if file.is_dir() else file.parent)
        editor.start(sock, file)


if __name__ == "__main__":
    app()
