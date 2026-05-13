import socket as _socket
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from zyn.__main__ import app
from zyn.editors import (
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
    path: Path, line: int | None = None, col: int | None = None, focus: bool = True
) -> str:
    """Build the --remote-send payload Neovim.open should emit for a target."""
    escaped = str(path.resolve()).replace("\\", "\\\\").replace(" ", r"\ ")
    cmd = f"tab drop {escaped}"
    if line and col:
        cmd += f" | call cursor({line},{col})"
    elif line:
        cmd += f" | {line}"
    if focus:
        cmd += " | lua if type(Zyn)=='table' then Zyn.focus() end"
    return f"<Esc>:{cmd}<CR>"


runner = CliRunner()


# --- CLI: default mode (discover + attach, else detached) ---


def test_default_no_session_runs_detached(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, [str(f)])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(["nvim", str(f)])


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
    mock_run.assert_called_once_with(["nvim", str(f)])
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
    mock_run.assert_called_once_with(["nvim", "--listen", str(sock_path), str(f)])


def test_start_with_directory_uses_dir_as_root(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    sock_path = Editor.get_socket_for(project)
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, ["-s", str(project)])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(["nvim", "--listen", str(sock_path), str(project)])


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
    mock_run.assert_called_once_with(["nvim", "--listen", str(sock_path), str(f)])


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
        mock_run.assert_called_once_with(["nvim", str(f)])
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
        mock_run.assert_called_once_with(["nvim", str(f)])
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
    mock_run.assert_called_once_with(["nvim", "--listen", str(sock_path), str(f)])


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


def test_cli_detached_with_line_emits_plus_lineno(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, [f"{f}:42"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(["nvim", "+42", str(f)])


def test_cli_detached_with_line_and_col_emits_cursor_call(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, [f"{f}:42:5"])
    assert result.exit_code == 0
    mock_run.assert_called_once_with(
        ["nvim", "+call cursor(42,5)", str(f)]
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
        ["nvim", "--listen", str(sock_path), "+42", str(f)]
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
        mock_run.assert_called_once_with(["nvim", str(f)])
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
        ["nvim", "--listen", str(scoped_sock), str(f)]
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
