"""Punto de entrada: `python main.py`."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

PROJECT_DIR = Path(__file__).resolve().parent


def main() -> int:
    # Trabajar siempre relativo a la carpeta del proyecto (state.json y assets/).
    os.chdir(PROJECT_DIR)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Toke-Poke")
    app.setQuitOnLastWindowClosed(False)

    from gui import PokeWidget
    from pokemon_manager import PokemonManager

    manager = PokemonManager(PROJECT_DIR / "state.json", PROJECT_DIR / "assets" / "pokemon")
    widget = PokeWidget(manager)
    widget.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
