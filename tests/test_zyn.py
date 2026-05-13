import os
import socket as _socket
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from zyn.__main__ import app
from zyn.editors import (
    STALE_LOCK_AGE_SECONDS,
    Editor,
    Neovim,
    SessionScope,
    Target,
    detect_multiplexer,
    detect_wm_workspace,
    parse_scope,
)


@pytest.fixture(autouse=True)
def clean_scope_env(monkeypatch):
    """Strip env vars that would leak host scope detection into tests."""
    for var in (
        "ZELLIJ_SESSION_NAME",
        "TMUX",
        "HYPRLAND_INSTANCE_SIGNATURE",
        "SWAYSOCK",
        "ZYN_SCOPE",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def sockets_dir(tmp_path, monkeypatch):
    d = tmp_path / "zyn"
    d.mkdir()
    monkeypatch.setattr("zyn.editors.SOCKETS_DIR", d)
    return d


def make_live_socket(path: Path) -> _socket.socket:
    s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    s.bind(str(path))
    s.listen(1)
    return s


def make_stale_socket(path: Path) -> None:
    s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    s.bind(str(path))
    s.close()


def expected_open_payload(
    target_or_path,
    line: int | None = None,
    col: int | None = None,
    focus: bool = True,
) -> str:
    """Build the --remote-send payload Neovim.open should emit.

    Accepts either a single Path (with optional line/col kwargs) or a
    list[Target] for multi-file payloads.
    """
    if isinstance(target_or_path, list):
        targets = target_or_path
    else:
        targets = [Target(target_or_path, line, col)]
    parts = []
    for t in targets:
        escaped = str(t.path.resolve()).replace("\\", "\\\\").replace(" ", r"\ ")
        parts.append(f"tab drop {escaped}")
    last = targets[-1]
    if last.line and last.col:
        parts.append(f"call cursor({last.line},{last.col})")
    elif last.line:
        parts.append(str(last.line))
    if focus:
        parts.append("lua if type(Zyn)=='table' then Zyn.focus() end")
    return f"<Esc>:{' | '.join(parts)}<CR>"


def expected_nvim_files_argv(
    target_or_path,
    line: int | None = None,
    col: int | None = None,
) -> list[str]:
    """Build the trailing portion of `nvim`/`nvim --listen` argv (-p tabs +
    optional `-c "tablast | <cursor>"`)."""
    if isinstance(target_or_path, list):
        targets = target_or_path
    else:
        targets = [Target(target_or_path, line, col)]
    args = ["-p", *[str(t.path) for t in targets]]
    last = targets[-1]
    if last.line and last.col:
        args.extend(["-c", f"tablast | call cursor({last.line},{last.col})"])
    elif last.line:
        args.extend(["-c", f"tablast | {last.line}"])
    return args


runner = CliRunner()


# --- CLI: default mode (discover + attach, else detached) ---


def test_default_no_session_runs_detached(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, [str(f)])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(["nvim", *expected_nvim_files_argv(f)])


def test_default_attaches_to_session_at_parent(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, [str(f)])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["nvim", "--server", str(sock_path), "--remote-send", expected_open_payload(f)]
        )
    finally:
        s.close()


def test_default_walks_up_to_ancestor_session(sockets_dir, tmp_path):
    project = tmp_path / "project"
    sub = project / "deep" / "sub"
    sub.mkdir(parents=True)
    f = sub / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, [str(f)])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["nvim", "--server", str(sock_path), "--remote-send", expected_open_payload(f)]
        )
    finally:
        s.close()


def test_default_stale_socket_falls_back_to_detached(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    make_stale_socket(sock_path)
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, [str(f)])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(["nvim", *expected_nvim_files_argv(f)])
    assert not sock_path.exists()


# --- CLI: --start ---


def test_start_no_session_creates_session(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, ["-s", str(f)])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["nvim", "--listen", str(sock_path), *expected_nvim_files_argv(f)]
    )


def test_start_with_directory_uses_dir_as_root(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    sock_path = Editor.get_socket_for(project)
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, ["-s", str(project)])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["nvim", "--listen", str(sock_path), *expected_nvim_files_argv(project)]
    )


def test_start_errors_when_live_session_exists(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        result = runner.invoke(app, ["-s", str(f)])
        assert result.exit_code != 0
        assert "already exists" in result.output
    finally:
        s.close()


def test_start_treats_stale_socket_as_no_session(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    make_stale_socket(sock_path)
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, ["-s", str(f)])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["nvim", "--listen", str(sock_path), *expected_nvim_files_argv(f)]
    )


# --- CLI: --detached ---


def test_detached_ignores_existing_session(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    s = make_live_socket(Editor.get_socket_for(project))
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, ["-d", str(f)])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(["nvim", *expected_nvim_files_argv(f)])
    finally:
        s.close()


# --- CLI: --workspace ---


def test_workspace_attaches_at_exact_root(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = tmp_path / "elsewhere.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, ["-w", str(project), str(f)])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["nvim", "--server", str(sock_path), "--remote-send", expected_open_payload(f)]
        )
    finally:
        s.close()


def test_workspace_does_not_walk_up(sockets_dir, tmp_path):
    project = tmp_path / "project"
    sub = project / "sub"
    sub.mkdir(parents=True)
    f = sub / "file.txt"
    f.touch()
    s = make_live_socket(Editor.get_socket_for(project))
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, ["-w", str(sub), str(f)])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(["nvim", *expected_nvim_files_argv(f)])
    finally:
        s.close()


def test_workspace_with_start_uses_workspace_as_root(sockets_dir, tmp_path):
    project = tmp_path / "project"
    deep = project / "deep"
    deep.mkdir(parents=True)
    f = deep / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, ["-w", str(project), "-s", str(f)])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["nvim", "--listen", str(sock_path), *expected_nvim_files_argv(f)]
    )


# --- CLI: error cases ---


def test_start_and_detached_are_mutex(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    result = runner.invoke(app, ["-s", "-d", str(f)])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


def test_invalid_editor_name_errors(sockets_dir, tmp_path, monkeypatch):
    monkeypatch.setenv("ZYN_EDITOR", "emacs")
    f = tmp_path / "file.txt"
    f.touch()
    result = runner.invoke(app, [str(f)])
    assert result.exit_code != 0


# --- Editor.discover ---


def test_discover_returns_none_when_no_session(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    assert Editor.discover(f) is None


def test_discover_finds_session_at_exact_dir(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        result = Editor.discover(f)
        assert result is not None
        assert result.root == project
        assert result.session_socket == sock_path
    finally:
        s.close()


def test_discover_walks_up_to_ancestor(sockets_dir, tmp_path):
    project = tmp_path / "project"
    sub = project / "deep" / "sub"
    sub.mkdir(parents=True)
    f = sub / "file.txt"
    f.touch()
    s = make_live_socket(Editor.get_socket_for(project))
    try:
        result = Editor.discover(f)
        assert result is not None
        assert result.root == project
    finally:
        s.close()


def test_discover_ignores_unrelated_sibling_session(sockets_dir, tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    f = b / "file.txt"
    f.touch()
    s = make_live_socket(Editor.get_socket_for(a))
    try:
        assert Editor.discover(f) is None
    finally:
        s.close()


# --- Editor.has_live_session ---


def test_has_live_session_true_when_listener_present(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    s = make_live_socket(Editor.get_socket_for(project))
    try:
        assert Editor.has_live_session(project) is True
    finally:
        s.close()


def test_has_live_session_false_and_unlinks_when_stale(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    sock_path = Editor.get_socket_for(project)
    make_stale_socket(sock_path)
    assert sock_path.exists()
    assert Editor.has_live_session(project) is False
    assert not sock_path.exists()


def test_has_live_session_false_when_missing(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    assert Editor.has_live_session(project) is False


# --- Editor cleanup semantics ---


def test_create_session_unlinks_socket_on_exit(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    sock_path = Editor.get_socket_for(project)
    sock_path.touch()
    with Neovim.create_session(project):
        assert sock_path.exists()
    assert not sock_path.exists()


def test_create_session_unlinks_socket_on_exception(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    sock_path = Editor.get_socket_for(project)
    sock_path.touch()
    with pytest.raises(RuntimeError):
        with Neovim.create_session(project):
            raise RuntimeError("boom")
    assert not sock_path.exists()


def test_attached_editor_does_not_unlink_socket(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        editor = Neovim.attach(project)
        assert editor is not None
        with editor:
            pass
        assert sock_path.exists()
    finally:
        s.close()


# --- Target.parse ---


def test_target_parse_path_only():
    t = Target.parse("src/app.py")
    assert t == Target(Path("src/app.py"))


def test_target_parse_with_line():
    t = Target.parse("src/app.py:42")
    assert t == Target(Path("src/app.py"), 42)


def test_target_parse_with_line_and_col():
    t = Target.parse("src/app.py:42:5")
    assert t == Target(Path("src/app.py"), 42, 5)


def test_target_parse_filename_with_colons_no_digits():
    t = Target.parse("weird:name.txt")
    assert t == Target(Path("weird:name.txt"))


def test_target_parse_absolute_path_with_line():
    t = Target.parse("/tmp/foo/file.py:99")
    assert t == Target(Path("/tmp/foo/file.py"), 99)


# --- CLI: line/col routing ---


def test_cli_detached_with_line_uses_tablast_cursor(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, [f"{f}:42"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["nvim", *expected_nvim_files_argv(f, line=42)]
    )


def test_cli_detached_with_line_and_col_uses_tablast_cursor(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, [f"{f}:42:5"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["nvim", *expected_nvim_files_argv(f, line=42, col=5)]
    )


def test_cli_attach_with_line_passes_cursor_arg(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, [f"{f}:42:5"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            [
                "nvim",
                "--server",
                str(sock_path),
                "--remote-send",
                expected_open_payload(f, line=42, col=5),
            ]
        )
    finally:
        s.close()


def test_cli_start_with_line_creates_session_and_jumps(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, ["-s", f"{f}:42"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["nvim", "--listen", str(sock_path), *expected_nvim_files_argv(f, line=42)]
    )


# --- SessionScope key derivation ---


def test_empty_scope_yields_no_components():
    assert SessionScope().key_components() == []


def test_scope_components_include_set_dimensions():
    s = SessionScope(multiplexer="zellij:foo", wm_workspace="hyprland:1")
    assert s.key_components() == ["mux:zellij:foo", "wm:hyprland:1"]


def test_socket_path_differs_when_scope_differs(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    plain = Editor.get_socket_for(project)
    scoped = Editor.get_socket_for(project, SessionScope(multiplexer="zellij:foo"))
    assert plain != scoped


def test_socket_path_differs_per_wm_workspace(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    ws1 = Editor.get_socket_for(project, SessionScope(wm_workspace="hyprland:1"))
    ws2 = Editor.get_socket_for(project, SessionScope(wm_workspace="hyprland:2"))
    assert ws1 != ws2


# --- parse_scope ---


def test_parse_scope_default():
    assert parse_scope("mux") == ("mux",)


def test_parse_scope_all():
    assert parse_scope("all") == ("mux", "wm")


def test_parse_scope_none_and_empty():
    assert parse_scope("none") == ()
    assert parse_scope("") == ()


def test_parse_scope_comma_list():
    assert parse_scope("mux,wm") == ("mux", "wm")


def test_parse_scope_strips_whitespace():
    assert parse_scope(" mux , wm ") == ("mux", "wm")


def test_parse_scope_rejects_unknown():
    with pytest.raises(ValueError, match="unknown scope dimension"):
        parse_scope("mux,bogus")


# --- detection ---


def test_detect_multiplexer_zellij(monkeypatch):
    monkeypatch.setenv("ZELLIJ_SESSION_NAME", "myproj")
    assert detect_multiplexer() == "zellij:myproj"


def test_detect_multiplexer_tmux(monkeypatch):
    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1234,0")
    fake_run = patch(
        "zyn.editors.subprocess.run",
        return_value=type("R", (), {"stdout": "work\n"})(),
    )
    with fake_run:
        assert detect_multiplexer() == "tmux:work"


def test_detect_multiplexer_none_when_no_env():
    assert detect_multiplexer() is None


def test_detect_wm_workspace_hyprland(monkeypatch):
    monkeypatch.setenv("HYPRLAND_INSTANCE_SIGNATURE", "abc123")
    fake_run = patch(
        "zyn.editors.subprocess.run",
        return_value=type("R", (), {"stdout": '{"id": 3, "name": "web"}'})(),
    )
    with fake_run:
        assert detect_wm_workspace() == "hyprland:3"


def test_detect_wm_workspace_none_when_no_env():
    assert detect_wm_workspace() is None


# --- CLI: scope-driven session isolation ---


def test_cli_session_in_zellij_isolated_from_plain(sockets_dir, tmp_path, monkeypatch):
    """Same root + different scope = different socket = different session."""
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()

    # Live socket exists for the plain (no-scope) key
    plain_sock = Editor.get_socket_for(project)
    s = make_live_socket(plain_sock)
    try:
        # Invoke from inside zellij — scope=mux is default, so the plain
        # socket shouldn't match. Falls through to detached.
        monkeypatch.setenv("ZELLIJ_SESSION_NAME", "myproj")
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, [str(f)])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(["nvim", *expected_nvim_files_argv(f)])
    finally:
        s.close()


def test_cli_scope_none_ignores_zellij_env(sockets_dir, tmp_path, monkeypatch):
    """--scope none should attach to the plain socket even from inside zellij."""
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    plain_sock = Editor.get_socket_for(project)
    s = make_live_socket(plain_sock)
    try:
        monkeypatch.setenv("ZELLIJ_SESSION_NAME", "myproj")
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, ["--scope", "none", str(f)])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["nvim", "--server", str(plain_sock), "--remote-send", expected_open_payload(f)]
        )
    finally:
        s.close()


def test_cli_start_creates_session_at_scoped_key(sockets_dir, tmp_path, monkeypatch):
    """--start in a zellij session uses the scoped socket path, not the plain one."""
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    monkeypatch.setenv("ZELLIJ_SESSION_NAME", "myproj")
    scoped_sock = Editor.get_socket_for(
        project, SessionScope(multiplexer="zellij:myproj")
    )
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, ["-s", str(f)])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["nvim", "--listen", str(scoped_sock), *expected_nvim_files_argv(f)]
    )


def test_cli_invalid_scope_errors(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    result = runner.invoke(app, ["--scope", "bogus", str(f)])
    assert result.exit_code != 0
    assert "unknown scope dimension" in result.output


# --- Focus trigger ---


def test_attach_payload_includes_focus_trigger_by_default(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, [str(f)])
        assert result.exit_code == 0
        payload = mock_run.call_args[0][0][-1]
        assert "lua if type(Zyn)=='table' then Zyn.focus() end" in payload
    finally:
        s.close()


def test_no_focus_flag_omits_focus_trigger(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, ["--no-focus", str(f)])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            [
                "nvim",
                "--server",
                str(sock_path),
                "--remote-send",
                expected_open_payload(f, focus=False),
            ]
        )
    finally:
        s.close()


def test_zyn_no_focus_env_omits_focus_trigger(sockets_dir, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        monkeypatch.setenv("ZYN_NO_FOCUS", "1")
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, [str(f)])
        assert result.exit_code == 0
        payload = mock_run.call_args[0][0][-1]
        assert "Zyn.focus()" not in payload
    finally:
        s.close()


def test_open_payload_escapes_spaces_in_path(sockets_dir, tmp_path):
    project = tmp_path / "weird name"
    project.mkdir()
    f = project / "file with spaces.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, [str(f)])
        assert result.exit_code == 0
        payload = mock_run.call_args[0][0][-1]
        # spaces escaped with backslash inside the :tab drop arg
        assert r"weird\ name" in payload
        assert r"file\ with\ spaces.txt" in payload
    finally:
        s.close()


# --- Race handling: lock acquire/release ---


def test_acquire_lock_returns_path_first_then_none(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    lock1 = Editor.acquire_start_lock(project)
    assert lock1 is not None and lock1.is_dir()
    lock2 = Editor.acquire_start_lock(project)
    assert lock2 is None
    Editor.release_start_lock(lock1)


def test_release_unblocks_subsequent_acquire(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    lock1 = Editor.acquire_start_lock(project)
    Editor.release_start_lock(lock1)
    lock2 = Editor.acquire_start_lock(project)
    assert lock2 is not None
    Editor.release_start_lock(lock2)


def test_acquire_lock_cleans_up_stale_and_succeeds(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    lock = Editor.lock_path_for(project)
    lock.mkdir(parents=True)
    # Backdate the lock so it looks stale
    old = time.time() - (STALE_LOCK_AGE_SECONDS + 5)
    os.utime(lock, (old, old))
    fresh = Editor.acquire_start_lock(project)
    assert fresh is not None
    Editor.release_start_lock(fresh)


def test_is_session_pending_false_when_live_socket_exists(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    sock_path = Editor.get_socket_for(project)
    lock = Editor.acquire_start_lock(project)
    s = make_live_socket(sock_path)
    try:
        assert Editor.is_session_pending(project) is False
    finally:
        s.close()
        Editor.release_start_lock(lock)


def test_is_session_pending_true_when_lock_held_no_socket(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    lock = Editor.acquire_start_lock(project)
    try:
        assert Editor.is_session_pending(project) is True
    finally:
        Editor.release_start_lock(lock)


# --- Race handling: wait_for_session ---


def test_wait_for_session_returns_true_when_socket_binds(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    sock_path = Editor.get_socket_for(project)
    lock = Editor.acquire_start_lock(project)
    bound = []

    def bind_after_delay():
        time.sleep(0.15)
        bound.append(make_live_socket(sock_path))

    t = threading.Thread(target=bind_after_delay)
    t.start()
    try:
        assert Editor.wait_for_session(project, timeout=2.0) is True
    finally:
        t.join()
        for s in bound:
            s.close()
        Editor.release_start_lock(lock)


def test_wait_for_session_bails_when_lock_disappears(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    lock = Editor.acquire_start_lock(project)

    def release_after_delay():
        time.sleep(0.15)
        Editor.release_start_lock(lock)

    t = threading.Thread(target=release_after_delay)
    t.start()
    try:
        assert Editor.wait_for_session(project, timeout=2.0) is False
    finally:
        t.join()


def test_wait_for_session_returns_false_on_timeout(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    lock = Editor.acquire_start_lock(project)
    try:
        # Lock held, no socket, never binds — should time out
        assert Editor.wait_for_session(project, timeout=0.3) is False
    finally:
        Editor.release_start_lock(lock)


# --- Race handling: CLI integration ---


def test_cli_start_errors_when_lock_already_held(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    lock = Editor.acquire_start_lock(project)
    try:
        result = runner.invoke(app, ["-s", str(f)])
        assert result.exit_code != 0
        assert "creation in progress" in result.output
    finally:
        Editor.release_start_lock(lock)


def test_cli_default_waits_for_pending_then_attaches(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.get_socket_for(project)
    lock = Editor.acquire_start_lock(project)
    bound = []

    def bind_async():
        time.sleep(0.15)
        bound.append(make_live_socket(sock_path))

    t = threading.Thread(target=bind_async)
    t.start()
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, [str(f)])
        assert result.exit_code == 0
        # Should have attached (--remote-send), not detached (just `nvim file`)
        argv = mock_run.call_args[0][0]
        assert "--remote-send" in argv
    finally:
        t.join()
        for s in bound:
            s.close()
        Editor.release_start_lock(lock)


# --- --reveal ---


REVEAL_PAYLOAD = "<Esc>:lua if type(Zyn)=='table' then Zyn.focus() end<CR>"


def test_reveal_focuses_existing_session(sockets_dir, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, ["--reveal"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["nvim", "--server", str(sock_path), "--remote-send", REVEAL_PAYLOAD]
        )
    finally:
        s.close()


def test_reveal_walks_up_to_ancestor_session(sockets_dir, tmp_path, monkeypatch):
    project = tmp_path / "project"
    sub = project / "deep" / "sub"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, ["--reveal"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["nvim", "--server", str(sock_path), "--remote-send", REVEAL_PAYLOAD]
        )
    finally:
        s.close()


def test_reveal_with_workspace_attaches_at_exact_root(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, ["--reveal", "-w", str(project)])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["nvim", "--server", str(sock_path), "--remote-send", REVEAL_PAYLOAD]
        )
    finally:
        s.close()


def test_reveal_errors_when_no_live_session(sockets_dir, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    result = runner.invoke(app, ["--reveal"])
    assert result.exit_code != 0
    assert "no live session" in result.output


def test_reveal_rejects_file_argument(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    result = runner.invoke(app, ["--reveal", str(f)])
    assert result.exit_code != 0
    assert "does not take file arguments" in result.output


def test_reveal_mutex_with_start(sockets_dir, tmp_path):
    result = runner.invoke(app, ["--reveal", "--start"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


def test_reveal_mutex_with_detached(sockets_dir, tmp_path):
    result = runner.invoke(app, ["--reveal", "--detached"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output


# --- Multi-file ---


def test_cli_multi_file_detached(sockets_dir, tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.touch()
    f2.touch()
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, [str(f1), str(f2)])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["nvim", *expected_nvim_files_argv([Target(f1), Target(f2)])]
    )


def test_cli_multi_file_cursor_lands_on_last(sockets_dir, tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.touch()
    f2.touch()
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, [str(f1), f"{f2}:42:5"])
    assert result.exit_code == 0
    argv = mock_run.call_args[0][0]
    # cursor is on the last file via -c "tablast | call cursor(...)"
    assert "-c" in argv
    c_idx = argv.index("-c")
    assert argv[c_idx + 1] == "tablast | call cursor(42,5)"


def test_cli_multi_file_attach_chains_tab_drop(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f1 = project / "a.txt"
    f2 = project / "b.txt"
    f1.touch()
    f2.touch()
    sock_path = Editor.get_socket_for(project)
    s = make_live_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, [str(f1), f"{f2}:42"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            [
                "nvim",
                "--server",
                str(sock_path),
                "--remote-send",
                expected_open_payload([Target(f1), Target(f2, 42)]),
            ]
        )
    finally:
        s.close()


def test_cli_multi_file_start_loads_all_with_cursor_on_last(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f1 = project / "a.txt"
    f2 = project / "b.txt"
    f1.touch()
    f2.touch()
    sock_path = Editor.get_socket_for(project)
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, ["-s", str(f1), f"{f2}:42:5"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        [
            "nvim",
            "--listen",
            str(sock_path),
            *expected_nvim_files_argv([Target(f1), Target(f2, 42, 5)]),
        ]
    )


def test_cli_default_falls_to_detached_when_lock_holder_gives_up(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    lock = Editor.acquire_start_lock(project)

    def release_async():
        time.sleep(0.15)
        Editor.release_start_lock(lock)

    t = threading.Thread(target=release_async)
    t.start()
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, [str(f)])
        assert result.exit_code == 0
        argv = mock_run.call_args[0][0]
        assert argv == ["nvim", *expected_nvim_files_argv(f)]  # detached fallback
    finally:
        t.join()
