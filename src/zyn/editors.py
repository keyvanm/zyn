import subprocess
from pathlib import Path
from typing import Protocol


class Editor(Protocol):
    def open(self, socket: Path, file: Path) -> None: ...
    def start(self, socket: Path, file: Path) -> None: ...


class Neovim:
    def open(self, socket: Path, file: Path) -> None:
        subprocess.run(["nvim", "--server", str(socket), "--remote", str(file)])

    def start(self, socket: Path, file: Path) -> None:
        subprocess.run(["nvim", "--listen", str(socket), str(file)])


EDITORS: dict[str, Editor] = {
    "nvim": Neovim(),
}
