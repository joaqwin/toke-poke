# -*- mode: python ; coding: utf-8 -*-
"""Especificación de PyInstaller: `pyinstaller toke_poke.spec`.

Genera dist/TokePoke/TokePoke.exe (onedir, sin consola) con el icono de Pokébola
y los sprites ya descargados incluidos como recursos.
"""
from pathlib import Path

ROOT = Path(SPECPATH)
ICON = str(ROOT / "assets" / "icon" / "pokeball.ico")

datas = [
    (str(ROOT / "assets" / "icon"), "assets/icon"),
    (str(ROOT / "assets" / "pokemon"), "assets/pokemon"),
]

# Paquetes Python que la app no usa. `cryptography` lo arrastra el análisis de ssl,
# pero la app valida certificados con truststore (almacén de Windows) o curl.exe.
EXCLUDED_MODULES = [
    "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtMultimedia",
    "PySide6.QtSql", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets", "PySide6.QtSvg", "PySide6.QtSvgWidgets", "PySide6.Qt3DCore",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtBluetooth",
    "PySide6.QtPositioning", "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtTest",
    "PySide6.QtXml", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools",
    "cryptography", "requests", "urllib3", "certifi", "idna", "charset_normalizer",
    "tkinter", "unittest", "pydoc", "pytest", "setuptools", "pip",
]

# DLLs de Qt que no se cargan nunca en una app de widgets sencilla.
# opengl32sw.dll (20 MB) es el rasterizador OpenGL por software: Qt solo lo usa si se
# pide un contexto OpenGL, y este widget se pinta con el motor raster.
EXCLUDED_BINARIES = {
    "opengl32sw.dll",
    "qt6quick.dll", "qt6qml.dll", "qt6qmlmodels.dll", "qt6qmlmeta.dll",
    "qt6qmlworkerscript.dll", "qt6quickwidgets.dll",
    "qt6pdf.dll", "qt6opengl.dll", "qt6network.dll", "qt6virtualkeyboard.dll",
}

# Plugins de Qt innecesarios: solo se conservan platforms, styles, iconengines
# y los formatos de imagen que la app abre (PNG e ICO los trae Qt de serie).
EXCLUDED_PLUGIN_DIRS = ("platforminputcontexts", "generic")


def keep_binary(entry) -> bool:
    dest = entry[0].replace("\\", "/")
    if Path(dest).name.lower() in EXCLUDED_BINARIES:
        return False
    return not any(f"plugins/{d}/" in dest.lower() for d in EXCLUDED_PLUGIN_DIRS)


a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["truststore"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDED_MODULES,
    noarchive=False,
)
a.binaries = TOC([e for e in a.binaries if keep_binary(e)])
a.datas = TOC([e for e in a.datas if keep_binary(e)])

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TokePoke",
    icon=ICON,
    version=str(ROOT / "version_info.txt"),
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="TokePoke",
)
