import contextlib
import hashlib
import itertools
import json
import os
import socket as _socket
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

SOCKETS_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "zyn"


@dataclass(frozen=True)
class SessionScope:
    """Discriminators that scope a session beyond just the workspace root.

    Empty scope (all None) collapses to plain `hash(root)` keying — the
    no-multiplexer, no-WM-detection baseline.
    """

    multiplexer: str | None = None
    wm_workspace: str | None = None

    def key_components(self) -> list[str]:
        parts = []
        if self.multiplexer:
            parts.append(f"mux:{self.multiplexer}")
        if self.wm_workspace:
            parts.append(f"wm:{self.wm_workspace}")
        return parts


def detect_multiplexer() -> str | None:
    if name := os.environ.get("ZELLIJ_SESSION_NAME"):
        return f"zellij:{name}"
    if os.environ.get("TMUX"):
        try:
            r = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True,
                text=True,
                check=True,
                timeout=1,
            )
            return f"tmux:{r.stdout.strip()}"
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            return None
    return None


def detect_wm_workspace() -> str | None:
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        try:
            r = subprocess.run(
                ["hyprctl", "activeworkspace", "-j"],
                capture_output=True,
                text=True,
                check=True,
                timeout=1,
            )
            ws = json.loads(r.stdout)
            return f"hyprland:{ws['id']}"
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            KeyError,
        ):
            return None
    if os.environ.get("SWAYSOCK"):
        try:
            r = subprocess.run(
                ["swaymsg", "-t", "get_workspaces"],
                capture_output=True,
                text=True,
                check=True,
                timeout=1,
            )
            for ws in json.loads(r.stdout):
                if ws.get("focused"):
                    return f"sway:{ws['name']}"
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
        ):
            return None
    return None


AVAILABLE_SCOPES: tuple[str, ...] = ("mux", "wm")
DEFAULT_SCOPE: str = "mux"


def parse_scope(raw: str) -> tuple[str, ...]:
    """Parse `--scope` value: 'all', 'none', or comma-list like 'mux,wm'."""
    raw = raw.strip()
    if raw in ("", "none"):
        return ()
    if raw == "all":
        return AVAILABLE_SCOPES
    parts = tuple(p.strip() for p in raw.split(",") if p.strip())
    invalid = [p for p in parts if p not in AVAILABLE_SCOPES]
    if invalid:
        raise ValueError(
            f"unknown scope dimension(s): {', '.join(invalid)}. "
            f"Available: {', '.join(AVAILABLE_SCOPES)}, all, none"
        )
    return parts


def build_scope(enabled: tuple[str, ...]) -> SessionScope:
    """Detect requested scope dimensions; others left None."""
    return SessionScope(
        multiplexer=detect_multiplexer() if "mux" in enabled else None,
        wm_workspace=detect_wm_workspace() if "wm" in enabled else None,
    )


@dataclass(frozen=True)
class Target:
    """A file to open, optionally with a cursor position."""

    path: Path
    line: int | None = None
    col: int | None = None

    @classmethod
    def parse(cls, raw: str) -> "Target":
        """Parse `path`, `path:line`, or `path:line:col`.

        Trailing `:digit` segments are treated as line/col. Anything else
        (including filenames literally containing colons) is taken as the
        full path — matches helix/sublime convention.
        """
        parts = raw.rsplit(":", 2)
        if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            return cls(Path(parts[0]), int(parts[1]), int(parts[2]))
        parts = raw.rsplit(":", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return cls(Path(parts[0]), int(parts[1]))
        return cls(Path(raw))


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
    def get_socket_for(path: Path, scope: SessionScope = SessionScope()) -> Path:
        SOCKETS_DIR.mkdir(parents=True, exist_ok=True)
        components = [str(path.resolve()), *scope.key_components()]
        key = hashlib.md5("|".join(components).encode()).hexdigest()
        return SOCKETS_DIR / f"{key}.sock"

    @classmethod
    def has_live_session(cls, root: Path, scope: SessionScope = SessionScope()) -> bool:
        """True iff a live session exists at root within scope. Unlinks stale socket files."""
        sock = cls.get_socket_for(root, scope)
        if _is_live_socket(sock):
            return True
        if sock.is_socket():
            with contextlib.suppress(OSError):
                sock.unlink()
        return False

    @classmethod
    def attach(cls, root: Path, scope: SessionScope = SessionScope()) -> Self | None:
        """Attach to an existing session at exactly `root` within `scope`."""
        if not cls.has_live_session(root, scope):
            return None
        return cls(root=root, session_socket=cls.get_socket_for(root, scope))

    @classmethod
    def discover(
        cls, path: Path, scope: SessionScope = SessionScope()
    ) -> Self | None:
        """Walk up from `path` looking for a live session within `scope`."""
        dir_path = path if path.is_dir() else path.parent
        for directory in itertools.chain([dir_path], dir_path.parents):
            if cls.has_live_session(directory, scope):
                return cls(
                    root=directory.resolve(),
                    session_socket=cls.get_socket_for(directory, scope),
                )
        return None

    @classmethod
    def create_session(
        cls, root: Path, scope: SessionScope = SessionScope()
    ) -> Self:
        """Configure a new session at `root` within `scope`. Use as a context manager."""
        instance = cls(root=root, session_socket=cls.get_socket_for(root, scope))
        instance._owns_socket = True
        return instance

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_) -> None:
        if self.session_socket and self._owns_socket:
            self.session_socket.unlink(missing_ok=True)

    def launch(self, target: Target | None = None):
        """Start a new editor process listening on session_socket; optionally open target."""
        raise NotImplementedError

    def open(self, target: Target):
        """Route target to the existing session at session_socket."""
        raise NotImplementedError

    def detached(self, target: Target):
        """Run the editor with no session machinery."""
        raise NotImplementedError


def _vim_cursor_arg(target: Target) -> str | None:
    if target.line and target.col:
        return f"+call cursor({target.line},{target.col})"
    if target.line:
        return f"+{target.line}"
    return None


class Neovim(Editor):
    def launch(self, target: Target | None = None):
        if not self.session_socket:
            raise ValueError("launch requires a session_socket")
        args = ["nvim", "--listen", str(self.session_socket)]
        if target is None and self.root:
            target = Target(self.root)
        if target:
            cursor = _vim_cursor_arg(target)
            if cursor:
                args.append(cursor)
            args.append(str(target.path))
        subprocess.run(args)

    def open(self, target: Target):
        if not self.session_socket:
            raise ValueError("open requires a session_socket; use detached() for raw editor")
        args = ["nvim", "--server", str(self.session_socket), "--remote"]
        cursor = _vim_cursor_arg(target)
        if cursor:
            args.append(cursor)
        args.append(str(target.path))
        subprocess.run(args)

    def detached(self, target: Target):
        args = ["nvim"]
        cursor = _vim_cursor_arg(target)
        if cursor:
            args.append(cursor)
        args.append(str(target.path))
        subprocess.run(args)
