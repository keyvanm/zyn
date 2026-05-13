import socket as _socket
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from zyn.__main__ import app
from zyn.editors import Editor, Neovim


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
            ["nvim", "--server", str(sock_path), "--remote", str(f)]
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
            ["nvim", "--server", str(sock_path), "--remote", str(f)]
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
            ["nvim", "--server", str(sock_path), "--remote", str(f)]
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
