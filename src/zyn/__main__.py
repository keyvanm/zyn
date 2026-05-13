import hashlib
import itertools
import os
import subprocess
from pathlib import Path

import typer

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
    editor = os.environ.get("ZYN_EDITOR", "nvim")
    socket = find_socket(file)

    if socket:
        subprocess.run([editor, "--server", str(socket), "--remote", file])
    else:
        get_sockets_dir().mkdir(parents=True, exist_ok=True)
        sock = get_socket_for_root(file if file.is_dir() else file.parent)
        subprocess.run([editor, "--listen", str(sock), file])


if __name__ == "__main__":
    app()
