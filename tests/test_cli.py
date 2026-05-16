import subprocess

import pytest
from typer.testing import CliRunner

from zyn.cli import app


runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_scope_env(monkeypatch):
    """Don't let host ZYN_SCOPE leak into tests that exercise probe."""
    monkeypatch.delenv("ZYN_SCOPE", raising=False)


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Isolate HOME so setup-shell writes into tmp_path, not the real config."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


# --- setup-shell ---


class TestSetupShell:
    @pytest.mark.parametrize(
        "shell,target_rel,line",
        [
            ("/bin/bash", ".bashrc", "export EDITOR=zyn"),
            ("/usr/bin/zsh", ".zshrc", "export EDITOR=zyn"),
            ("/usr/bin/fish", ".config/fish/config.fish", "set -gx EDITOR zyn"),
        ],
        ids=["bash", "zsh", "fish"],
    )
    def test_appends_to_correct_file(
        self, fake_home, monkeypatch, shell, target_rel, line
    ):
        monkeypatch.setenv("SHELL", shell)
        result = runner.invoke(app, ["setup-shell"])
        assert result.exit_code == 0
        content = (fake_home / target_rel).read_text()
        assert line in content
        assert "Added by `zyn-cli setup-shell`" in content

    def test_creates_fish_parent_directory(self, fake_home, monkeypatch):
        monkeypatch.setenv("SHELL", "/usr/bin/fish")
        assert not (fake_home / ".config" / "fish").exists()
        result = runner.invoke(app, ["setup-shell"])
        assert result.exit_code == 0
        assert (fake_home / ".config" / "fish" / "config.fish").exists()

    def test_idempotent(self, fake_home, monkeypatch):
        monkeypatch.setenv("SHELL", "/usr/bin/zsh")
        first = runner.invoke(app, ["setup-shell"])
        assert first.exit_code == 0
        first_content = (fake_home / ".zshrc").read_text()

        second = runner.invoke(app, ["setup-shell"])
        assert second.exit_code == 0
        assert "already in" in second.output
        assert (fake_home / ".zshrc").read_text() == first_content

    def test_preserves_existing_content(self, fake_home, monkeypatch):
        monkeypatch.setenv("SHELL", "/usr/bin/zsh")
        zshrc = fake_home / ".zshrc"
        zshrc.write_text("# existing line\nalias gs='git status'\n")
        result = runner.invoke(app, ["setup-shell"])
        assert result.exit_code == 0
        content = zshrc.read_text()
        assert "# existing line" in content
        assert "alias gs='git status'" in content
        assert "export EDITOR=zyn" in content

    def test_adds_separator_when_file_lacks_trailing_newline(
        self, fake_home, monkeypatch
    ):
        monkeypatch.setenv("SHELL", "/usr/bin/zsh")
        zshrc = fake_home / ".zshrc"
        zshrc.write_text("# no trailing newline")
        result = runner.invoke(app, ["setup-shell"])
        assert result.exit_code == 0
        content = zshrc.read_text()
        # Existing content stays on its own line, not glued to the marker
        assert content.startswith("# no trailing newline\n")
        assert "export EDITOR=zyn" in content

    def test_unsupported_shell_exits_one(self, fake_home, monkeypatch):
        monkeypatch.setenv("SHELL", "/usr/local/bin/nushell")
        result = runner.invoke(app, ["setup-shell"])
        assert result.exit_code == 1
        assert "Unsupported shell" in result.output
        assert "nushell" in result.output

    def test_missing_shell_env_exits_one(self, fake_home, monkeypatch):
        monkeypatch.delenv("SHELL", raising=False)
        result = runner.invoke(app, ["setup-shell"])
        assert result.exit_code == 1
        assert "Unsupported shell" in result.output


# --- probe ---


def _scope_arg(cmd: list[str]) -> str:
    """Pull the value following `--scope` out of a captured argv."""
    return cmd[cmd.index("--scope") + 1]


class TestProbe:
    def test_forwards_exit_code_success(self, monkeypatch):
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, check=False):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = runner.invoke(app, ["probe", "/some/path"])
        assert result.exit_code == 0
        assert captured["cmd"][0] == "zyn-probe"
        assert "/some/path" in captured["cmd"]

    def test_forwards_nonzero_exit_code(self, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda cmd, check=False: subprocess.CompletedProcess(cmd, 1),
        )
        result = runner.invoke(app, ["probe", "/some/path"])
        assert result.exit_code == 1

    def test_default_scope_is_mux(self, monkeypatch):
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, check=False):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        runner.invoke(app, ["probe", "/p"])
        assert _scope_arg(captured["cmd"]) == "mux"

    def test_explicit_scope_overrides_default(self, monkeypatch):
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, check=False):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        runner.invoke(app, ["probe", "/p", "--scope", "all"])
        assert _scope_arg(captured["cmd"]) == "all"

    def test_zyn_scope_envvar_used(self, monkeypatch):
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, check=False):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setenv("ZYN_SCOPE", "wm")
        runner.invoke(app, ["probe", "/p"])
        assert _scope_arg(captured["cmd"]) == "wm"

    def test_missing_zyn_probe_binary(self, monkeypatch):
        def fake_run(cmd, check=False):
            raise FileNotFoundError(2, "No such file", "zyn-probe")

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = runner.invoke(app, ["probe", "/some/path"])
        assert result.exit_code == 127
        assert "zyn-probe is not installed" in result.output
