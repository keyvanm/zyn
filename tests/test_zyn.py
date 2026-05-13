import socket as _socket
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from zyn.__main__ import app
from zyn.editors import Editor, Neovim


def make_unix_socket(path: Path) -> _socket.socket:
    s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    s.bind(str(path))
    return s


@pytest.fixture
def sockets_dir(tmp_path, monkeypatch):
    d = tmp_path / "zyn"
    d.mkdir()
    monkeypatch.setattr("zyn.editors.SOCKETS_DIR", d)
    return d


# --- socket_path_for ---


def test_socket_path_in_sockets_dir(sockets_dir, tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    assert Editor.socket_path_for(root).parent == sockets_dir


def test_socket_path_resolves_relative(sockets_dir, tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.chdir(root)
    assert Editor.socket_path_for(Path(".")) == Editor.socket_path_for(root)


def test_different_roots_give_different_paths(sockets_dir, tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert Editor.socket_path_for(a) != Editor.socket_path_for(b)


# --- discover ---


def test_discover_no_socket_returns_none(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    assert Editor.discover(f) is None


def test_discover_finds_socket_for_exact_dir(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    s = make_unix_socket(Editor.socket_path_for(project))
    try:
        result = Editor.discover(f)
        assert result is not None
        assert result.root == project
        assert result.socket == Editor.socket_path_for(project)
    finally:
        s.close()


def test_discover_traverses_to_parent(sockets_dir, tmp_path):
    project = tmp_path / "project"
    sub = project / "deep" / "sub"
    sub.mkdir(parents=True)
    f = sub / "file.txt"
    f.touch()
    s = make_unix_socket(Editor.socket_path_for(project))
    try:
        result = Editor.discover(f)
        assert result is not None
        assert result.root == project
    finally:
        s.close()


def test_discover_ignores_unrelated_socket(sockets_dir, tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    f = b / "file.txt"
    f.touch()
    s = make_unix_socket(Editor.socket_path_for(a))
    try:
        assert Editor.discover(f) is None
    finally:
        s.close()


def test_discover_with_relative_path(sockets_dir, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    monkeypatch.chdir(project)
    s = make_unix_socket(Editor.socket_path_for(project))
    try:
        result = Editor.discover(Path("file.txt"))
        assert result is not None
        assert result.root == project
    finally:
        s.close()


# --- context manager ---


def test_context_manager_deletes_socket_on_exit(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    editor = Neovim(root=project)
    sock = editor.ensure_socket()
    sock.touch()
    with editor:
        assert sock.exists()
    assert not sock.exists()


def test_context_manager_deletes_socket_on_exception(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    editor = Neovim(root=project)
    sock = editor.ensure_socket()
    sock.touch()
    with pytest.raises(RuntimeError):
        with editor:
            raise RuntimeError("boom")
    assert not sock.exists()


def test_context_manager_no_socket_no_error(tmp_path):
    with Neovim(root=tmp_path):
        pass


# --- Neovim.start ---


def test_neovim_start_calls_nvim_listen(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    editor = Neovim(root=project)
    with patch("zyn.editors.subprocess.run") as mock_run:
        editor.start(f)
    mock_run.assert_called_once_with(["nvim", "--listen", str(editor.socket), str(f)])


# --- Neovim.open ---


def test_neovim_open_calls_nvim_remote(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = sockets_dir / "existing.sock"
    editor = Neovim(root=project, socket=sock_path)
    with patch("zyn.editors.subprocess.run") as mock_run:
        editor.open(f)
    mock_run.assert_called_once_with(
        ["nvim", "--server", str(sock_path), "--remote", str(f)]
    )


# --- CLI (main) ---

runner = CliRunner()


def test_cli_starts_new_editor_when_none_running(sockets_dir, tmp_path):
    f = tmp_path / "file.txt"
    f.touch()
    with patch("zyn.editors.subprocess.run") as mock_run:
        result = runner.invoke(app, [str(f)])
    assert result.exit_code == 0
    args = mock_run.call_args[0][0]
    assert args[:2] == ["nvim", "--listen"]


def test_cli_opens_in_existing_editor(sockets_dir, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    sock_path = Editor.socket_path_for(project)
    s = make_unix_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, [str(f)])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            ["nvim", "--server", str(sock_path), "--remote", str(f)]
        )
    finally:
        s.close()


def test_cli_relative_path_matches_existing_editor(sockets_dir, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    f = project / "file.txt"
    f.touch()
    monkeypatch.chdir(project)
    sock_path = Editor.socket_path_for(project)
    s = make_unix_socket(sock_path)
    try:
        with patch("zyn.editors.subprocess.run") as mock_run:
            result = runner.invoke(app, ["file.txt"])
        assert result.exit_code == 0
        args = mock_run.call_args[0][0]
        assert args[:2] == ["nvim", "--server"]
    finally:
        s.close()


def test_cli_unknown_editor_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("ZYN_EDITOR", "emacs")
    f = tmp_path / "file.txt"
    f.touch()
    result = runner.invoke(app, [str(f)])
    assert result.exit_code != 0
