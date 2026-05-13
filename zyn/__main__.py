#!/usr/bin/env python3

import hashlib
import os
import subprocess
import sys
from pathlib import Path


def zyn_dir() -> Path:
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return Path(runtime) / "zyn"


def socket_path(root: Path) -> Path:
    key = hashlib.md5(str(root).encode()).hexdigest()
    return zyn_dir() / f"{key}.sock"


def find_socket() -> Path | None:
    for directory in [Path.cwd().resolve(), *Path.cwd().resolve().parents]:
        sock = socket_path(directory)
        if sock.is_socket():
            return sock
    return None


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: zyn <file>", file=sys.stderr)
        sys.exit(1)

    file = sys.argv[1]
    editor = os.environ.get("ZYN_EDITOR", "nvim")
    socket = find_socket()

    if socket:
        subprocess.run([editor, "--server", str(socket), "--remote", file])
    else:
        zyn_dir().mkdir(parents=True, exist_ok=True)
        sock = socket_path(Path.cwd().resolve())
        subprocess.run([editor, "--listen", str(sock), file])


if __name__ == "__main__":
    main()
