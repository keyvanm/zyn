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

    def __post_init__(self) -> None:
        self.root = self.root.resolve()

    @property
    def default_socket_path(self) -> Path:
        key = hashlib.md5(str(self.root).encode()).hexdigest()
        return SOCKETS_DIR / f"{key}.sock"

    @classmethod
    def discover(cls, path: Path) -> Self | None:
        dir_path = path if path.is_dir() else path.parent
        for directory in itertools.chain([dir_path], dir_path.parents):
            sock = cls(root=directory).default_socket_path
            if sock.is_socket():
                return cls(root=directory, socket=sock)
        return None

    def ensure_socket(self) -> Path:
        SOCKETS_DIR.mkdir(parents=True, exist_ok=True)
        if self.socket is None:
            self.socket = self.default_socket_path
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
