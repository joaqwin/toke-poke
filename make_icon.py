"""Genera el icono de Pokébola de la aplicación (PNG + ICO multi-tamaño).

    python make_icon.py

Escribe `assets/icon/pokeball.png` (256x256) y `assets/icon/pokeball.ico`
(16, 24, 32, 48, 64, 128 y 256 px). No requiere Pillow: usa QPainter.
"""
from __future__ import annotations

import io
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QImage, QPainter, QPen, QRadialGradient

ICON_DIR = Path(__file__).resolve().parent / "assets" / "icon"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def draw_pokeball(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)

    margin = size * 0.04
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    center = rect.center()
    radius = rect.width() / 2
    outline = max(1.0, size * 0.07)
    band = max(1.0, size * 0.075)

    # Mitad superior roja con un leve brillo, mitad inferior blanca.
    red = QRadialGradient(QPointF(center.x() - radius * 0.35, center.y() - radius * 0.55), radius * 1.4)
    red.setColorAt(0.0, QColor("#ff6b6b"))
    red.setColorAt(0.45, QColor("#e3350d"))
    red.setColorAt(1.0, QColor("#a31d05"))
    white = QRadialGradient(QPointF(center.x() - radius * 0.3, center.y() + radius * 0.2), radius * 1.5)
    white.setColorAt(0.0, QColor("#ffffff"))
    white.setColorAt(1.0, QColor("#d9dbe3"))

    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(red))
    p.drawPie(rect, 0 * 16, 180 * 16)
    p.setBrush(QBrush(white))
    p.drawPie(rect, 180 * 16, 180 * 16)

    # Banda central negra.
    p.setBrush(QColor("#1b1b1f"))
    p.drawRect(QRectF(rect.left(), center.y() - band / 2, rect.width(), band))

    # Botón central.
    button_r = radius * 0.3
    p.setBrush(QColor("#1b1b1f"))
    p.drawEllipse(center, button_r + band * 0.9, button_r + band * 0.9)
    p.setBrush(QColor("#ffffff"))
    p.drawEllipse(center, button_r, button_r)
    p.setBrush(QColor("#d9dbe3"))
    p.drawEllipse(center, button_r * 0.55, button_r * 0.55)

    # Contorno exterior.
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor("#1b1b1f"), outline))
    p.drawEllipse(rect.adjusted(outline / 2, outline / 2, -outline / 2, -outline / 2))
    p.end()
    return img


def image_png_bytes(img: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def write_ico(path: Path, images: list[QImage]) -> None:
    """ICO con entradas PNG (soportado desde Windows Vista)."""
    blobs = [image_png_bytes(img) for img in images]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries = b""
    for img, blob in zip(images, blobs):
        w = img.width() if img.width() < 256 else 0
        h = img.height() if img.height() < 256 else 0
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    path.write_bytes(header + entries + b"".join(blobs))


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841 - necesario para QPainter
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    base = draw_pokeball(256)
    base.save(str(ICON_DIR / "pokeball.png"), "PNG")
    images = [draw_pokeball(s) for s in SIZES]
    write_ico(ICON_DIR / "pokeball.ico", images)
    print(f"Icono escrito en {ICON_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
