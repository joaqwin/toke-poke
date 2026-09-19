"""Punto de entrada: `python main.py` (o `TokePoke.exe` una vez empaquetado)."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

APP_NAME = "Toke-Poke"
APP_VERSION = "1.0.0"
PROJECT_DIR = Path(__file__).resolve().parent
FROZEN = bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    """Carpeta con los recursos empaquetados (assets/icon, sprites iniciales)."""
    return Path(getattr(sys, "_MEIPASS", PROJECT_DIR))


def data_dir() -> Path:
    """Carpeta de datos escribible: el proyecto en desarrollo, %LOCALAPPDATA%\\TokePoke instalado."""
    if not FROZEN:
        return PROJECT_DIR
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "TokePoke"


def seed_bundled_sprites(target: Path) -> None:
    """Copia los sprites incluidos en el paquete si aún no existen en la carpeta de datos."""
    source = resource_dir() / "assets" / "pokemon"
    if not source.is_dir():
        return
    target.mkdir(parents=True, exist_ok=True)
    for png in source.glob("*.png"):
        dest = target / png.name
        if not dest.exists():
            try:
                shutil.copyfile(png, dest)
            except OSError:
                pass


def app_icon() -> QIcon:
    ico = resource_dir() / "assets" / "icon" / "pokeball.ico"
    if ico.is_file():
        return QIcon(str(ico))
    png = resource_dir() / "assets" / "icon" / "pokeball.png"
    return QIcon(str(png)) if png.is_file() else QIcon()


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("TokePoke")
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)

    if FROZEN:
        # Windows agrupa la ventana en la barra de tareas con este identificador y usa su icono.
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TokePoke.App")
        except Exception:
            pass

    from gui import PokeWidget
    from pokemon_manager import PokemonManager

    data = data_dir()
    data.mkdir(parents=True, exist_ok=True)
    sprites_dir = data / "assets" / "pokemon"
    seed_bundled_sprites(sprites_dir)
    os.chdir(data)

    manager = PokemonManager(data / "state.json", sprites_dir)
    widget = PokeWidget(manager)
    widget.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
