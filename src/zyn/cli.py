import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(help="zyn auxiliary commands (shell setup, session probe).")

SHELL_CONFIGS: dict[str, tuple[str, str]] = {
    "bash": (".bashrc", "export EDITOR=zyn"),
    "zsh": (".zshrc", "export EDITOR=zyn"),
    "fish": (".config/fish/config.fish", "set -gx EDITOR zyn"),
}


@app.command()
def setup_shell() -> None:
    """Append EDITOR=zyn to your shell startup file. Detects bash, zsh, fish. Idempotent."""
    shell_path = os.environ.get("SHELL", "")
    shell = Path(shell_path).name if shell_path else ""

    if shell not in SHELL_CONFIGS:
        sys.stderr.write(
            f"Unsupported shell: {shell or '(SHELL env not set)'}.\n"
            f"Supported: bash, zsh, fish.\n"
            f"Add `export EDITOR=zyn` (or `set -gx EDITOR zyn` for fish) "
            f"to your shell's startup file manually.\n"
        )
        raise typer.Exit(1)

    relative_path, line = SHELL_CONFIGS[shell]
    target = Path.home() / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)

    existing = target.read_text() if target.exists() else ""
    if line in existing:
        print(f"EDITOR=zyn already in {target} — nothing to do.")
        return

    with target.open("a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(f"\n# Added by `zyn-cli setup-shell`\n{line}\n")

    print(f"Appended `{line}` to {target}.")
    print(f"Open a new terminal or run `source {target}` to apply.")


@app.command()
def probe(
    path: Annotated[
        Path,
        typer.Argument(help="Path to check for a live zyn session (walks up parents)."),
    ],
    scope: Annotated[
        str,
        typer.Option(
            "--scope",
            envvar="ZYN_SCOPE",
            help="Scope dims: comma list of mux,wm — or 'all'/'none'.",
        ),
    ] = "mux",
) -> None:
    """Check if a live zyn session exists for PATH. Exits 0 if yes, 1 if no.

    Thin Python wrapper around the `zyn-probe` Rust binary; useful for scripts
    that already shell out to zyn and want a single binary surface.
    """
    try:
        result = subprocess.run(
            ["zyn-probe", str(path), "--scope", scope],
            check=False,
        )
    except FileNotFoundError:
        sys.stderr.write(
            "zyn-probe is not installed.\n"
            "Install it with: cargo install --git https://github.com/keyvanm/zyn zyn-probe\n"
        )
        raise typer.Exit(127)
    raise typer.Exit(result.returncode)


if __name__ == "__main__":
    app()
