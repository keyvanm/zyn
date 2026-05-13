import contextlib
import hashlib
import itertools
import json
import os
import socket as _socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

STALE_LOCK_AGE_SECONDS = 60.0
DEFAULT_WAIT_TIMEOUT = 10.0

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
    def lock_path_for(cls, root: Path, scope: SessionScope = SessionScope()) -> Path:
        return cls.get_socket_for(root, scope).with_suffix(".lock")

    @classmethod
    def is_session_pending(cls, root: Path, scope: SessionScope = SessionScope()) -> bool:
        """True iff a `--start` is in flight for (root, scope) — a lock is held
        with no live socket yet. Auto-removes stale locks (older than
        STALE_LOCK_AGE_SECONDS with no live socket)."""
        lock = cls.lock_path_for(root, scope)
        if not lock.is_dir():
            return False
        if cls.has_live_session(root, scope):
            return False  # lock is incidental; live socket already exists
        try:
            age = time.time() - lock.stat().st_mtime
        except OSError:
            return False
        if age > STALE_LOCK_AGE_SECONDS:
            with contextlib.suppress(OSError):
                lock.rmdir()
            return False
        return True

    @classmethod
    def acquire_start_lock(
        cls, root: Path, scope: SessionScope = SessionScope()
    ) -> Path | None:
        """Atomic mkdir-based lock. Returns the lock path on success, None if
        another --start is already in flight at (root, scope)."""
        lock = cls.lock_path_for(root, scope)
        cls.is_session_pending(root, scope)  # may clean up a stale lock
        try:
            lock.mkdir(parents=True, exist_ok=False)
            return lock
        except FileExistsError:
            return None

    @staticmethod
    def release_start_lock(lock: Path) -> None:
        with contextlib.suppress(OSError):
            lock.rmdir()

    @classmethod
    def wait_for_session(
        cls,
        root: Path,
        scope: SessionScope = SessionScope(),
        timeout: float = DEFAULT_WAIT_TIMEOUT,
    ) -> bool:
        """Poll for a live session at (root, scope). Bails early if the lock
        disappears (holder gave up) or timeout expires."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cls.has_live_session(root, scope):
                return True
            if not cls.is_session_pending(root, scope):
                return False
            time.sleep(0.1)
        return False

    @classmethod
    def attach(cls, root: Path, scope: SessionScope = SessionScope()) -> Self | None:
        """Attach to an existing session at exactly `root` within `scope`."""
        if not cls.has_live_session(root, scope):
            return None
        return cls(root=root, session_socket=cls.get_socket_for(root, scope))

    @classmethod
    def discover(
        cls,
        path: Path,
        scope: SessionScope = SessionScope(),
        *,
        wait_pending: bool = False,
        wait_timeout: float = DEFAULT_WAIT_TIMEOUT,
    ) -> Self | None:
        """Walk up from `path` looking for a live session within `scope`.

        When `wait_pending=True`, also waits on a `--start` in flight at any
        walk-up level, attaching once the session becomes live.
        """
        dir_path = path if path.is_dir() else path.parent
        for directory in itertools.chain([dir_path], dir_path.parents):
            if cls.has_live_session(directory, scope):
                return cls(
                    root=directory.resolve(),
                    session_socket=cls.get_socket_for(directory, scope),
                )
            if wait_pending and cls.is_session_pending(directory, scope):
                if cls.wait_for_session(directory, scope, wait_timeout):
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

    def launch(self, targets: list[Target] | None = None):
        """Start a new editor process listening on session_socket; optionally open targets."""
        raise NotImplementedError

    def open(self, targets: list[Target], focus: bool = True):
        """Route targets to the existing session at session_socket.

        `focus` triggers an editor-side hook (e.g. `Zyn.focus()` in nvim)
        that brings the editor's pane to the foreground if a multiplexer
        plugin is installed. No-op otherwise.
        """
        raise NotImplementedError

    def detached(self, targets: list[Target]):
        """Run the editor with no session machinery."""
        raise NotImplementedError

    def focus(self):
        """Trigger the editor-side focus hook without opening any file.

        For session-routable editors, sends a no-op-but-for-focus message to
        the existing session at session_socket. Subclasses that don't support
        focus-only routing can leave this as the default NotImplementedError.
        """
        raise NotImplementedError


def _vim_cursor_arg(target: Target) -> str | None:
    if target.line and target.col:
        return f"+call cursor({target.line},{target.col})"
    if target.line:
        return f"+{target.line}"
    return None


def _vim_cursor_ex(target: Target) -> str | None:
    """Cursor positioning as a bare ex command (no leading `+`), for chaining via `|`."""
    if target.line and target.col:
        return f"call cursor({target.line},{target.col})"
    if target.line:
        return str(target.line)
    return None


def _escape_vim_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace(" ", r"\ ")


def _build_nvim_file_args(targets: list[Target]) -> list[str]:
    """Build the file/tab/cursor portion of an nvim argv. Always uses `-p`
    so each target gets a tab, and any cursor positioning lands on the
    *last* target (which becomes the visible tab via `tablast`)."""
    if not targets:
        return []
    args = ["-p", *[str(t.path) for t in targets]]
    cursor_ex = _vim_cursor_ex(targets[-1])
    if cursor_ex:
        args.extend(["-c", f"tablast | {cursor_ex}"])
    return args


class Neovim(Editor):
    def launch(self, targets: list[Target] | None = None):
        if not self.session_socket:
            raise ValueError("launch requires a session_socket")
        args = ["nvim", "--listen", str(self.session_socket)]
        if not targets and self.root:
            targets = [Target(self.root)]
        args.extend(_build_nvim_file_args(targets or []))
        subprocess.run(args)

    def open(self, targets: list[Target], focus: bool = True):
        if not self.session_socket:
            raise ValueError("open requires a session_socket; use detached() for raw editor")
        if not targets:
            raise ValueError("open requires at least one target")
        parts = [f"tab drop {_escape_vim_path(t.path)}" for t in targets]
        cursor_ex = _vim_cursor_ex(targets[-1])
        if cursor_ex:
            parts.append(cursor_ex)
        if focus:
            parts.append("lua if type(Zyn)=='table' then Zyn.focus() end")
        payload = f"<Esc>:{' | '.join(parts)}<CR>"
        subprocess.run(
            ["nvim", "--server", str(self.session_socket), "--remote-send", payload]
        )

    def detached(self, targets: list[Target]):
        if not targets:
            raise ValueError("detached requires at least one target")
        args = ["nvim", *_build_nvim_file_args(targets)]
        subprocess.run(args)

    def focus(self):
        if not self.session_socket:
            raise ValueError("focus requires a session_socket")
        payload = "<Esc>:lua if type(Zyn)=='table' then Zyn.focus() end<CR>"
        subprocess.run(
            ["nvim", "--server", str(self.session_socket), "--remote-send", payload]
        )
