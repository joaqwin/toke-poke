"""Rastreador de tokens de Claude Code.

Escanea de forma incremental los transcripts JSONL de `%USERPROFILE%\\.claude\\projects`
y calcula los tokens consumidos (entrada, salida y caché) por cada respuesta del asistente.

- `TokenScanner`: lógica pura (sin Qt), reutilizable en tests.
- `TrackerThread`: `QThread` que sondea periódicamente y emite los tokens nuevos.
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Iterable

USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)
ENV_CLAUDE_DIR = "TOKE_POKE_CLAUDE_DIR"
RECENT_IDS = 64  # ids de mensaje recordados por archivo para deduplicar bloques repetidos


def default_claude_dir() -> Path:
    override = os.environ.get(ENV_CLAUDE_DIR)
    if override:
        return Path(override)
    profile = os.environ.get("USERPROFILE")
    base = Path(profile) if profile else Path.home()
    return base / ".claude"


def usage_tokens(usage: dict | None) -> int:
    if not isinstance(usage, dict):
        return 0
    total = 0
    for key in USAGE_KEYS:
        value = usage.get(key)
        if isinstance(value, (int, float)):
            total += int(value)
    return total


def record_usage(record: dict) -> tuple[int, str | None]:
    """Devuelve (tokens, id de mensaje) para un registro de transcript, o (0, None)."""
    if not isinstance(record, dict) or record.get("type") != "assistant":
        return 0, None
    message = record.get("message")
    if not isinstance(message, dict):
        return 0, None
    tokens = usage_tokens(message.get("usage"))
    if tokens <= 0:
        return 0, None
    msg_id = message.get("id") or record.get("requestId") or record.get("uuid")
    return tokens, str(msg_id) if msg_id else None


class TokenScanner:
    """Lee transcripts de forma incremental y acumula tokens nuevos."""

    def __init__(self, claude_dir: Path | str | None = None, offsets: dict | None = None):
        self.claude_dir = Path(claude_dir) if claude_dir else default_claude_dir()
        self._offsets: dict[str, dict] = {}
        self._recent: dict[str, deque] = {}
        self._lock = threading.Lock()
        if offsets:
            self.load_offsets(offsets)

    # ---- offsets persistibles -------------------------------------------
    def load_offsets(self, offsets: dict) -> None:
        with self._lock:
            for key, info in (offsets or {}).items():
                if not isinstance(info, dict):
                    continue
                self._offsets[str(key)] = {
                    "offset": int(info.get("offset") or 0),
                    "size": int(info.get("size") or 0),
                    "mtime": float(info.get("mtime") or 0.0),
                }
                self._recent[str(key)] = deque(info.get("last_ids") or [], maxlen=RECENT_IDS)

    def snapshot_offsets(self) -> dict:
        with self._lock:
            return {
                key: {**info, "last_ids": list(self._recent.get(key, ()))}
                for key, info in self._offsets.items()
            }

    # ---- descubrimiento ---------------------------------------------------
    def transcript_files(self) -> list[Path]:
        root = self.claude_dir / "projects"
        if not root.is_dir():
            root = self.claude_dir
        if not root.is_dir():
            return []
        try:
            return sorted(p for p in root.rglob("*.jsonl") if p.is_file())
        except OSError:
            return []

    # ---- escaneo -----------------------------------------------------------
    def scan(self) -> int:
        """Procesa las líneas nuevas de todos los transcripts y devuelve tokens nuevos."""
        added = 0
        for path in self.transcript_files():
            try:
                added += self._scan_file(path)
            except OSError:
                continue
        return added

    def _scan_file(self, path: Path) -> int:
        key = str(path)
        stat = path.stat()
        with self._lock:
            info = self._offsets.setdefault(key, {"offset": 0, "size": 0, "mtime": 0.0})
            recent = self._recent.setdefault(key, deque(maxlen=RECENT_IDS))
            offset = int(info["offset"])
            if stat.st_size < offset:  # archivo truncado o reemplazado
                offset = 0
                recent.clear()
            if stat.st_size == offset and stat.st_mtime == info.get("mtime"):
                return 0

        added = 0
        with path.open("rb") as fh:
            fh.seek(offset)
            while True:
                line = fh.readline()
                if not line:
                    break
                if not line.endswith(b"\n"):
                    break  # línea incompleta: se leerá cuando termine de escribirse
                offset += len(line)
                added += self._count_line(line, recent)

        with self._lock:
            info.update({"offset": offset, "size": stat.st_size, "mtime": stat.st_mtime})
        return added

    @staticmethod
    def _count_line(line: bytes, recent: deque) -> int:
        stripped = line.strip()
        if not stripped or b'"usage"' not in stripped:
            return 0
        try:
            record = json.loads(stripped.decode("utf-8", errors="replace"))
        except ValueError:
            return 0
        tokens, msg_id = record_usage(record)
        if tokens <= 0:
            return 0
        if msg_id:
            if msg_id in recent:
                return 0
            recent.append(msg_id)
        return tokens


def scan_all(claude_dir: Path | str | None = None) -> int:
    """Utilidad: cuenta todos los tokens históricos (escaneo completo)."""
    return TokenScanner(claude_dir).scan()


# ---------------------------------------------------------------------------
# Hilo Qt
# ---------------------------------------------------------------------------
try:
    from PySide6.QtCore import QThread, Signal
except ImportError:  # pragma: no cover - permite importar el módulo sin Qt
    QThread = object  # type: ignore
    Signal = None  # type: ignore


if Signal is not None:

    class TrackerThread(QThread):
        """Sondea los transcripts en segundo plano sin bloquear la interfaz.

        Señales:
            tokens_added(int added, dict offsets, bool initial): tokens nuevos detectados.
                `initial` es True para el primer escaneo tras arrancar (tokens consumidos
                mientras la app estaba cerrada o histórico en la primera ejecución).
            scan_error(str): error no fatal durante el escaneo.
        """

        tokens_added = Signal(int, dict, bool)
        scan_error = Signal(str)

        def __init__(
            self,
            claude_dir: Path | str | None = None,
            offsets: dict | None = None,
            interval_ms: int = 2000,
            parent=None,
        ):
            super().__init__(parent)
            self.scanner = TokenScanner(claude_dir, offsets)
            self.interval_ms = max(100, int(interval_ms))
            self._stop = threading.Event()

        @property
        def claude_dir(self) -> Path:
            return self.scanner.claude_dir

        def stop(self, wait_ms: int = 3000) -> None:
            self._stop.set()
            self.wait(wait_ms)

        def run(self) -> None:  # noqa: D401
            initial = True
            while not self._stop.is_set():
                try:
                    added = self.scanner.scan()
                    if added > 0 or initial:
                        self.tokens_added.emit(added, self.scanner.snapshot_offsets(), initial)
                except Exception as exc:  # pragma: no cover - robustez ante archivos raros
                    self.scan_error.emit(str(exc))
                initial = False
                self._stop.wait(self.interval_ms / 1000.0)
