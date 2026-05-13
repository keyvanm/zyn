import hashlib
import itertools
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self


@dataclass
class Editor:
    root: Path
    socket: Path | None = field(default=None)

    @staticmethod
    def sockets_dir() -> Path:
        runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
        return Path(runtime) / "zyn"

    def socket_path(self) -> Path:
        key = hashlib.md5(str(self.root).encode()).hexdigest()
        return self.sockets_dir() / f"{key}.sock"

    @classmethod
    def find(cls, path: Path) -> Self | None:
        dir_path = path if path.is_dir() else path.parent
        for directory in itertools.chain([dir_path], dir_path.parents):
            sock = cls(root=directory).socket_path()
            if sock.is_socket():
                return cls(root=directory, socket=sock)
        return None

    def ensure_socket(self) -> Path:
        self.sockets_dir().mkdir(parents=True, exist_ok=True)
        if self.socket is None:
            self.socket = self.socket_path()
        return self.socket

    def open(self, file: Path) -> None:
        raise NotImplementedError()

    def start(self, file: Path) -> None:
        raise NotImplementedError()


class Neovim(Editor):
    def open(self, file: Path) -> None:
        assert self.socket
        subprocess.run(["nvim", "--server", str(self.socket), "--remote", str(file)])

    def start(self, file: Path) -> None:
        sock = self.ensure_socket()
        subprocess.run(["nvim", "--listen", str(sock), str(file)])
