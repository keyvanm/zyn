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
    """An interface to a Zyn compatible editor"""

    root: Path | None = field(default=None)
    """The workspace root, a dir, could be empty to indicate not being tied to a workspace"""
    session_socket: Path | None = field(default=None)
    """If this instance is assosiated with a session, here's the socket"""

    @staticmethod
    def get_socket_for(path: Path) -> Path:
        key = hashlib.md5(str(path.resolve()).encode()).hexdigest()
        return SOCKETS_DIR / f"{key}.sock"

    @classmethod
    def _discover_active_workspace_session(cls, path: Path) -> tuple[Path, Path | None]:
        dir_path = path if path.is_dir() else path.parent
        for directory in itertools.chain([dir_path], dir_path.parents):
            sock = cls.get_socket_for(directory)
            if sock.is_socket():  # TODO: We should also check if the socket isn't stale
                return directory, sock
        return dir_path, None

    @classmethod
    def discover(cls, path: Path) -> Self | None:
        directory, socket = cls._discover_active_workspace_session(path)
        return cls(root=directory.resolve(), session_socket=socket)

    def convert_to_session(self):
        if not self.root:
            raise ValueError("Needs to be rooted")

        self.session_socket = self.get_socket_for(self.root)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_) -> None:
        if self.session_socket:
            self.session_socket.unlink(missing_ok=True)

    def launch(self):
        raise NotImplementedError()

    def open(self, path: Path):
        raise NotImplementedError


class Neovim(Editor):
    def launch(self):
        args = ["nvim"]

        if self.session_socket:
            args.extend(("--server", str(self.session_socket)))

        if self.root:
            args.extend(("--remote", str(self.root)))

        subprocess.run(args)

    def open(self, path: Path):
        args = ["nvim"]
        if self.session_socket:
            if self.session_socket:
                args.extend(("--server", str(self.session_socket)))
        subprocess.run([*args, str(path)])
