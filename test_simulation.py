"""Simulación de extremo a extremo.

Escribe un transcript JSONL ficticio (mismo formato que Claude Code), arranca el widget
apuntando a esa carpeta y comprueba que:

* el rastreador cuenta tokens nuevos (y deduplica bloques repetidos / líneas incompletas),
* la UI actualiza contadores y barra de progreso,
* la evolución se dispara y la animación termina sin bloquear el bucle de eventos,
* el estado se persiste en state.json y los sprites se descargan a assets/pokemon.

Uso:
    python test_simulation.py            # sin ventana (QT_QPA_PLATFORM=offscreen)
    python test_simulation.py --visible  # muestra la ventana durante la simulación

Todos los archivos temporales se eliminan al terminar.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):  # consolas Windows con cp1252
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

VISIBLE = "--visible" in sys.argv
if not VISIBLE:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui import PokeWidget  # noqa: E402
from pokemon_manager import PokemonManager, name_of  # noqa: E402
from tracker import TokenScanner  # noqa: E402

TOKENS_PER_LEVEL = 1_000  # Bulbasaur evoluciona a 16k, Ivysaur a 32k
POLL_MS = 150
SLOW = 1.2 if VISIBLE else 0.0

_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, bool(ok), detail))
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def make_record(tokens: int, msg_id: str | None = None) -> dict:
    msg_id = msg_id or f"msg_{uuid.uuid4().hex[:16]}"
    return {
        "parentUuid": None,
        "isSidechain": False,
        "type": "assistant",
        "uuid": str(uuid.uuid4()),
        "timestamp": "2026-09-18T20:00:00.000Z",
        "sessionId": "simulated-session",
        "message": {
            "model": "claude-fable-5-1",
            "id": msg_id,
            "role": "assistant",
            "content": [{"type": "text", "text": "simulación"}],
            "usage": {
                "input_tokens": tokens // 4,
                "cache_creation_input_tokens": tokens // 4,
                "cache_read_input_tokens": tokens // 4,
                "output_tokens": tokens - 3 * (tokens // 4),
            },
        },
    }


def append_lines(path: Path, records: list[dict], newline: bool = True) -> None:
    with path.open("a", encoding="utf-8") as fh:
        for i, rec in enumerate(records):
            fh.write(json.dumps(rec, ensure_ascii=False))
            if newline or i < len(records) - 1:
                fh.write("\n")


def wait_until(app: QApplication, predicate, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    app.processEvents()
    return predicate()


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="toke_poke_test_"))
    claude_dir = tmp / ".claude"
    log_dir = claude_dir / "projects" / "C--Users-test-project"
    log_dir.mkdir(parents=True)
    log_path = log_dir / f"{uuid.uuid4()}.jsonl"
    state_path = tmp / "state.json"
    assets_dir = tmp / "assets" / "pokemon"

    print(f"Carpeta temporal: {tmp}")
    app = QApplication.instance() or QApplication(sys.argv)
    widget: PokeWidget | None = None
    try:
        # --- rutas Windows ------------------------------------------------
        if os.name == "nt":
            check("rutas con separador Windows (\\)", "\\" in str(log_path) and "\\" in str(state_path), str(log_path))
        else:
            check("rutas POSIX", "/" in str(log_path))

        # --- tokens históricos previos al primer arranque -------------------
        append_lines(log_path, [make_record(1_000) for _ in range(5)])
        check("escaneo completo cuenta histórico", TokenScanner(claude_dir).scan() == 5_000)

        manager = PokemonManager(state_path, assets_dir, tokens_per_level=TOKENS_PER_LEVEL)
        widget = PokeWidget(manager, claude_dir=claude_dir, poll_interval_ms=POLL_MS, start_tracker=False)
        widget.show()
        app.processEvents()

        updates: list[tuple[int, int]] = []
        widget.tokens_updated.connect(lambda s, t: updates.append((s, t)))
        evolutions: list[tuple[int, int]] = []
        widget.evolution_played.connect(lambda a, b: evolutions.append((a, b)))

        widget.set_starter(1)  # Bulbasaur
        widget.start_tracking()
        check("hilo rastreador corriendo (QThread)", widget.tracker.isRunning())

        ok = wait_until(app, lambda: manager.total_tokens == 5_000)
        check("primer escaneo suma al total sin dar XP", ok and manager.xp_tokens == 0,
              f"total={manager.total_tokens} xp={manager.xp_tokens}")
        check("contador de sesión en 0 tras el escaneo inicial", widget.session_tokens == 0)
        time.sleep(SLOW)

        # --- tokens nuevos → UI --------------------------------------------
        append_lines(log_path, [make_record(1_000) for _ in range(6)])
        ok = wait_until(app, lambda: manager.xp_tokens == 6_000)
        check("tokens nuevos suman XP", ok, f"xp={manager.xp_tokens}")
        check("contador de sesión actualizado", widget.session_tokens == 6_000, widget.session_label.text())
        check("etiqueta sesión muestra 6.0k", "6.0k" in widget.session_label.text(), widget.session_label.text())
        check("etiqueta total muestra 11.0k", "11.0k" in widget.total_label.text(), widget.total_label.text())
        ok = wait_until(app, lambda: widget.progress.value() >= 370, timeout=3)
        check("barra de progreso animada (~37.5%)", ok, f"valor={widget.progress.value()}/1000")
        check("etiqueta de siguiente evolución", "Ivysaur" in widget.next_label.text(), widget.next_label.text())
        time.sleep(SLOW)

        # --- deduplicación y línea incompleta --------------------------------
        dup_id = "msg_duplicado_0001"
        append_lines(log_path, [make_record(500, dup_id), make_record(500, dup_id)])
        ok = wait_until(app, lambda: manager.xp_tokens == 6_500)
        time.sleep(0.5)
        app.processEvents()
        check("bloques con mismo message.id se cuentan una vez", ok and manager.xp_tokens == 6_500,
              f"xp={manager.xp_tokens}")

        append_lines(log_path, [make_record(700)], newline=False)  # línea a medio escribir
        time.sleep(0.6)
        app.processEvents()
        check("línea incompleta no se cuenta todavía", manager.xp_tokens == 6_500, f"xp={manager.xp_tokens}")
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write("\n")
        ok = wait_until(app, lambda: manager.xp_tokens == 7_200)
        check("línea completada se cuenta después", ok, f"xp={manager.xp_tokens}")
        time.sleep(SLOW)

        # --- evolución 1: Bulbasaur → Ivysaur (16k) ----------------------------
        append_lines(log_path, [make_record(3_000) for _ in range(3)])  # xp = 16.2k
        ok = wait_until(app, lambda: len(evolutions) >= 1, timeout=10)
        check("evolución disparada y animación completada", ok and evolutions[:1] == [(1, 2)], str(evolutions))
        check("Pokémon activo es Ivysaur", manager.active == 2, name_of(manager.active or 0))
        check("nombre en la UI actualizado", widget.name_label.text() == "Ivysaur", widget.name_label.text())
        check("Ivysaur desbloqueado en el estado", 2 in manager.unlocked, str(manager.unlocked))
        check("UI responde durante la animación", app.processEvents() is None)
        time.sleep(SLOW)

        # --- evolución 2: Ivysaur → Venusaur (32k) -------------------------------
        append_lines(log_path, [make_record(4_000) for _ in range(4)])  # xp = 32.2k
        ok = wait_until(app, lambda: len(evolutions) >= 2, timeout=10)
        check("segunda evolución a Venusaur", ok and evolutions[1:2] == [(2, 3)], str(evolutions))
        check("forma final indicada", "final" in widget.next_label.text().lower(), widget.next_label.text())
        ok = wait_until(app, lambda: widget.progress.value() == 1000, timeout=3)
        check("barra llena en forma final", ok, f"valor={widget.progress.value()}")
        time.sleep(SLOW)

        # --- persistencia ---------------------------------------------------------
        reloaded = PokemonManager(state_path, assets_dir)
        check("state.json persiste el Pokémon activo", reloaded.active == 3)
        check("state.json persiste tokens", reloaded.total_tokens == manager.total_tokens and reloaded.xp_tokens == 32_200,
              f"total={reloaded.total_tokens} xp={reloaded.xp_tokens}")
        check("state.json persiste offsets del rastreador", str(log_path) in (reloaded.state.get("file_offsets") or {}))
        check("state.json persiste evoluciones", reloaded.unlocked == [1, 2, 3], str(reloaded.unlocked))

        # --- sprites ------------------------------------------------------------
        ok = wait_until(app, lambda: manager.sprites.has(3), timeout=25)
        if ok:
            check("sprite descargado a assets/pokemon/3.png", manager.sprites.path(3).stat().st_size > 0,
                  str(manager.sprites.path(3)))
        else:
            print("  [WARN] no se pudo descargar el sprite (¿sin conexión?): " + widget.status_label.text())

    finally:
        if widget is not None:
            widget.tracker.stop()
            widget.loader.stop()
            widget.hide()
            widget.deleteLater()
            app.processEvents()
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"Archivos de prueba eliminados: {not tmp.exists()}")

    failed = [r for r in _results if not r[1]]
    print(f"\n{len(_results) - len(failed)}/{len(_results)} comprobaciones correctas")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
