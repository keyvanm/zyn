import hashlib
import itertools
import os
import subprocess
from pathlib import Path

import typer

app = typer.Typer()


def zyn_dir() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return Path(runtime) / "zyn"


def socket_path(root: Path) -> Path:
    key = hashlib.md5(str(root).encode()).hexdigest()
    return zyn_dir() / f"{key}.sock"


def find_socket(path: Path) -> Path | None:
    dir_path = path if path.is_dir() else path.parent
    for directory in itertools.chain([dir_path], dir_path.parents):
        sock = socket_path(directory)
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
        zyn_dir().mkdir(parents=True, exist_ok=True)
        sock = socket_path(Path.cwd().resolve())
        subprocess.run([editor, "--listen", str(sock), file])


if __name__ == "__main__":
    app()
