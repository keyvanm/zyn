import contextlib
import hashlib
import itertools
import os
import socket as _socket
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

SOCKETS_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "zyn"


def _is_live_socket(path: Path) -> bool:
    """True if `path` is a socket file with a live listener accepting connections."""
    if not path.is_socket():
        return False
    try:
        with _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            s.connect(str(path))
        return True
    except OSError:
        return False


@dataclass
class Editor:
    """An interface to a Zyn compatible editor"""

    root: Path | None = field(default=None)
    """The workspace root, a dir, could be empty to indicate not being tied to a workspace"""
    session_socket: Path | None = field(default=None)
    """If this instance is associated with a session, here's the socket"""
    _owns_socket: bool = field(default=False, init=False, repr=False)
    """True only when this instance created the socket; gates cleanup so attached
    editors never delete a socket they don't own."""

    @staticmethod
    def get_socket_for(path: Path) -> Path:
        SOCKETS_DIR.mkdir(parents=True, exist_ok=True)
        key = hashlib.md5(str(path.resolve()).encode()).hexdigest()
        return SOCKETS_DIR / f"{key}.sock"

    @classmethod
    def has_live_session(cls, root: Path) -> bool:
        """True iff a live session exists at root. Cleans up stale socket files as a side effect."""
        sock = cls.get_socket_for(root)
        if _is_live_socket(sock):
            return True
        if sock.is_socket():
            with contextlib.suppress(OSError):
                sock.unlink()
        return False

    @classmethod
    def _discover_active_workspace_session(cls, path: Path) -> tuple[Path, Path | None]:
        dir_path = path if path.is_dir() else path.parent
        for directory in itertools.chain([dir_path], dir_path.parents):
            if cls.has_live_session(directory):
                return directory, cls.get_socket_for(directory)
        return dir_path, None

    @classmethod
    def discover(cls, path: Path) -> Self | None:
        directory, sock = cls._discover_active_workspace_session(path)
        if sock is None:
            return None
        return cls(root=directory.resolve(), session_socket=sock)

    def convert_to_session(self):
        if not self.root:
            raise ValueError("Needs to be rooted")
        self.session_socket = self.get_socket_for(self.root)
        self._owns_socket = True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_) -> None:
        if self.session_socket and self._owns_socket:
            self.session_socket.unlink(missing_ok=True)

    def launch(self, path: Path | None = None):
        """Start a new editor session listening on session_socket; optionally open path."""
        raise NotImplementedError

    def open(self, path: Path):
        """Open path in the existing session at session_socket, or detached if none."""
        raise NotImplementedError


class Neovim(Editor):
    def launch(self, path: Path | None = None):
        args = ["nvim"]
        if self.session_socket:
            args.extend(("--listen", str(self.session_socket)))
        target = path or self.root
        if target:
            args.append(str(target))
        subprocess.run(args)

    def open(self, path: Path):
        args = ["nvim"]
        if self.session_socket:
            args.extend(("--server", str(self.session_socket), "--remote", str(path)))
        else:
            args.append(str(path))
        subprocess.run(args)
