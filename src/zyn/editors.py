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
    session_socket: Path | None = field(default=None)
    _owns_socket: bool = field(default=False, init=False, repr=False)

    @staticmethod
    def get_socket_for(path: Path) -> Path:
        SOCKETS_DIR.mkdir(parents=True, exist_ok=True)
        key = hashlib.md5(str(path.resolve()).encode()).hexdigest()
        return SOCKETS_DIR / f"{key}.sock"

    @classmethod
    def has_live_session(cls, root: Path) -> bool:
        """True iff a live session exists at root. Unlinks stale socket files."""
        sock = cls.get_socket_for(root)
        if _is_live_socket(sock):
            return True
        if sock.is_socket():
            with contextlib.suppress(OSError):
                sock.unlink()
        return False

    @classmethod
    def attach(cls, root: Path) -> Self | None:
        """Attach to an existing session at exactly `root`."""
        if not cls.has_live_session(root):
            return None
        return cls(root=root, session_socket=cls.get_socket_for(root))

    @classmethod
    def discover(cls, path: Path) -> Self | None:
        """Walk up from `path` looking for a live session and attach to it."""
        dir_path = path if path.is_dir() else path.parent
        for directory in itertools.chain([dir_path], dir_path.parents):
            if cls.has_live_session(directory):
                return cls(
                    root=directory.resolve(),
                    session_socket=cls.get_socket_for(directory),
                )
        return None

    @classmethod
    def create_session(cls, root: Path) -> Self:
        """Configure a new session at `root`. Use as a context manager for cleanup."""
        instance = cls(root=root, session_socket=cls.get_socket_for(root))
        instance._owns_socket = True
        return instance

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_) -> None:
        if self.session_socket and self._owns_socket:
            self.session_socket.unlink(missing_ok=True)

    def launch(self, path: Path | None = None):
        """Start a new editor process listening on session_socket; optionally open path."""
        raise NotImplementedError

    def open(self, path: Path):
        """Route path to the existing session at session_socket."""
        raise NotImplementedError

    def detached(self, path: Path):
        """Run the editor with no session machinery."""
        raise NotImplementedError


class Neovim(Editor):
    def launch(self, path: Path | None = None):
        if not self.session_socket:
            raise ValueError("launch requires a session_socket")
        args = ["nvim", "--listen", str(self.session_socket)]
        target = path or self.root
        if target:
            args.append(str(target))
        subprocess.run(args)

    def open(self, path: Path):
        if not self.session_socket:
            raise ValueError("open requires a session_socket; use detached() for raw editor")
        subprocess.run(
            ["nvim", "--server", str(self.session_socket), "--remote", str(path)]
        )

    def detached(self, path: Path):
        subprocess.run(["nvim", str(path)])
