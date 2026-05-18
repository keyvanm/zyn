import argparse
import os
import subprocess
import sys
from pathlib import Path

SHELL_CONFIGS: dict[str, tuple[str, str]] = {
    "bash": (".bashrc", "export EDITOR=zyn"),
    "zsh": (".zshrc", "export EDITOR=zyn"),
    "fish": (".config/fish/config.fish", "set -gx EDITOR zyn"),
}


def _setup_shell(args) -> int:
    shell_path = os.environ.get("SHELL", "")
    shell = Path(shell_path).name if shell_path else ""

    if shell not in SHELL_CONFIGS:
        sys.stderr.write(
            f"Unsupported shell: {shell or '(SHELL env not set)'}.\n"
            f"Supported: bash, zsh, fish.\n"
            f"Add `export EDITOR=zyn` (or `set -gx EDITOR zyn` for fish) "
            f"to your shell's startup file manually.\n"
        )
        return 1

    relative_path, line = SHELL_CONFIGS[shell]
    target = Path.home() / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)

    existing = target.read_text() if target.exists() else ""
    if line in existing:
        print(f"EDITOR=zyn already in {target} — nothing to do.")
        return 0

    with target.open("a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(f"\n# Added by `zyn-cli setup-shell`\n{line}\n")

    print(f"Appended `{line}` to {target}.")
    print(f"Open a new terminal or run `source {target}` to apply.")
    return 0


def _probe(args) -> int:
    try:
        result = subprocess.run(
            ["zyn-probe", str(args.path), "--scope", args.scope],
            check=False,
        )
    except FileNotFoundError:
        sys.stderr.write(
            "zyn-probe is not installed.\n"
            "Install it with: cargo install --git https://github.com/keyvanm/zyn zyn-probe\n"
        )
        return 127
    return result.returncode


def app(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="zyn-cli",
        description="zyn auxiliary commands (shell setup, session probe).",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    subparsers.add_parser(
        "setup-shell",
        help="Append EDITOR=zyn to your shell startup file. Detects bash, zsh, fish. Idempotent.",
    )

    probe_parser = subparsers.add_parser(
        "probe",
        help="Check if a live zyn session exists for PATH. Exits 0 if yes, 1 if no.",
    )
    probe_parser.add_argument(
        "path",
        type=Path,
        help="Path to check for a live zyn session (walks up parents).",
    )
    probe_parser.add_argument(
        "--scope",
        default=os.environ.get("ZYN_SCOPE", "mux"),
        help="Scope dims: comma list of mux,wm — or 'all'/'none' (env: ZYN_SCOPE).",
    )

    args = parser.parse_args(argv)

    if args.command == "setup-shell":
        sys.exit(_setup_shell(args))
    elif args.command == "probe":
        sys.exit(_probe(args))


if __name__ == "__main__":
    app()
