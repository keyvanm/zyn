import hashlib
import itertools
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

SOCKETS_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "zyn"


@dataclass
class Editor:
    root: Path
    socket: Path | None = field(default=None)

    @staticmethod
    def socket_path_for(root: Path) -> Path:
        key = hashlib.md5(str(root.resolve()).encode()).hexdigest()
        return SOCKETS_DIR / f"{key}.sock"

    @classmethod
    def discover(cls, path: Path) -> Self | None:
        dir_path = path if path.is_dir() else path.parent
        for directory in itertools.chain([dir_path], dir_path.parents):
            sock = cls.socket_path_for(directory)
            if sock.is_socket():
                return cls(root=directory.resolve(), socket=sock)
        return None

    def ensure_socket(self) -> Path:
        SOCKETS_DIR.mkdir(parents=True, exist_ok=True)
        if self.socket is None:
            self.socket = self.socket_path_for(self.root)
        return self.socket

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_) -> None:
        if self.socket:
            self.socket.unlink(missing_ok=True)

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
