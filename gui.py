"""Widget flotante en modo oscuro que muestra el Pokémon activo y su progreso."""
from __future__ import annotations

import queue
import threading
from collections import deque
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pokemon_manager import STARTERS, PokemonManager, format_tokens, name_of
from tracker import TrackerThread

# Paleta modo oscuro
BG = QColor(24, 25, 32, 238)
BORDER = QColor(62, 66, 84)
TEXT = "#e8e9f0"
MUTED = "#9aa0b4"
ACCENT = "#ffcb05"
ACCENT_2 = "#3b82f6"
WIDGET_WIDTH = 270
SPRITE_SIZE = 144


# ---------------------------------------------------------------------------
# Descarga de sprites en segundo plano
# ---------------------------------------------------------------------------
class SpriteLoader(QThread):
    sprite_ready = Signal(int, str)
    sprite_failed = Signal(int, str)

    def __init__(self, manager: PokemonManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._queue: "queue.Queue[int | None]" = queue.Queue()
        self._pending: set[int] = set()
        self._lock = threading.Lock()

    def request(self, pids) -> None:
        for pid in pids:
            pid = int(pid)
            with self._lock:
                if pid in self._pending:
                    continue
                self._pending.add(pid)
            self._queue.put(pid)

    def stop(self, wait_ms: int = 3000) -> None:
        self._queue.put(None)
        self.wait(wait_ms)

    def run(self) -> None:
        while True:
            pid = self._queue.get()
            if pid is None:
                return
            try:
                path = self.manager.sprites.download(pid)
                self.sprite_ready.emit(pid, str(path))
            except Exception as exc:
                self.sprite_failed.emit(pid, str(exc))
            finally:
                with self._lock:
                    self._pending.discard(pid)


def load_sprite(path: Path | str, size: int = SPRITE_SIZE) -> QPixmap | None:
    pix = QPixmap(str(path))
    if pix.isNull():
        return None
    return pix.scaled(QSize(size, size), Qt.KeepAspectRatio, Qt.FastTransformation)


# ---------------------------------------------------------------------------
# Diálogo de selección de inicial
# ---------------------------------------------------------------------------
class StarterDialog(QDialog):
    def __init__(self, manager: PokemonManager, loader: SpriteLoader | None = None, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.choice: int | None = None
        self.setWindowTitle("Elige tu Pokémon inicial")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(
            f"QDialog {{ background: #181920; }}"
            f"QLabel {{ color: {TEXT}; font-family: 'Segoe UI'; }}"
            "QPushButton { background: #262833; border: 2px solid #3e4254; border-radius: 12px;"
            f" color: {TEXT}; padding: 8px; font-family: 'Segoe UI'; font-weight: 600; }}"
            f"QPushButton:hover {{ border-color: {ACCENT}; background: #2e3140; }}"
        )
        root = QVBoxLayout(self)
        title = QLabel("¿Con quién quieres empezar?")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)
        row = QHBoxLayout()
        self._buttons: dict[int, QPushButton] = {}
        for pid in STARTERS:
            btn = QPushButton(name_of(pid))
            btn.setMinimumSize(110, 130)
            btn.setIconSize(QSize(80, 80))
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _=False, p=pid: self._pick(p))
            self._buttons[pid] = btn
            self._set_icon(pid)
            row.addWidget(btn)
        root.addLayout(row)
        if loader is not None:
            loader.sprite_ready.connect(self._on_sprite)
            loader.request(STARTERS)

    def _set_icon(self, pid: int) -> None:
        if self.manager.sprites.has(pid):
            pix = load_sprite(self.manager.sprite_path(pid), 80)
            if pix:
                self._buttons[pid].setIcon(QIcon(pix))

    def _on_sprite(self, pid: int, _path: str) -> None:
        if pid in self._buttons:
            self._set_icon(pid)

    def _pick(self, pid: int) -> None:
        self.choice = pid
        self.accept()


# ---------------------------------------------------------------------------
# Widget principal
# ---------------------------------------------------------------------------
class PokeWidget(QWidget):
    tokens_updated = Signal(int, int)  # (sesión, total)
    evolution_played = Signal(int, int)  # (origen, destino) al terminar la animación

    def __init__(
        self,
        manager: PokemonManager | None = None,
        claude_dir: Path | str | None = None,
        poll_interval_ms: int = 2000,
        start_tracker: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.manager = manager or PokemonManager()
        self._first_run = not self.manager.has_starter
        # En la primera ejecución el histórico previo va al total pero no da XP.
        self._skip_initial_xp = self._first_run
        self.session_tokens = 0
        self._drag_offset: QPoint | None = None
        self._evo_queue: deque[tuple[int, int]] = deque()
        self._evo_running = False
        self.evolutions_played: list[tuple[int, int]] = []
        self._auto_start_tracker = start_tracker
        self._tracker_started = False

        self.setWindowTitle("Toke-Poke")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(WIDGET_WIDTH)
        self._build_ui()

        self.loader = SpriteLoader(self.manager)
        self.loader.sprite_ready.connect(self._on_sprite_ready)
        self.loader.sprite_failed.connect(self._on_sprite_failed)
        self.loader.start()

        self.tracker = TrackerThread(
            claude_dir=claude_dir,
            offsets=self.manager.state.get("file_offsets") or {},
            interval_ms=poll_interval_ms,
        )
        self.tracker.tokens_added.connect(self._on_tokens_added)
        self.tracker.scan_error.connect(lambda msg: self._set_status(f"⚠ {msg}"))

        self._build_tray()
        self._restore_position()
        self.refresh()
        self.loader.request(self.manager.sprites_needed())

    # ---- construcción de UI ----------------------------------------------
    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"QLabel {{ color: {TEXT}; font-family: 'Segoe UI'; }}"
            "QToolButton { color: #9aa0b4; background: transparent; border: none; font-size: 14px; }"
            f"QToolButton:hover {{ color: {TEXT}; }}"
            "QProgressBar { background: #2a2d3a; border: 1px solid #3e4254; border-radius: 7px; height: 14px; }"
            "QProgressBar::chunk { border-radius: 6px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
            f" stop:0 {ACCENT_2}, stop:1 {ACCENT}); }}"
            f"QMenu {{ background: #1f2129; color: {TEXT}; border: 1px solid #3e4254; }}"
            "QMenu::item:selected { background: #2e3140; }"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 12)
        root.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("TOKE-POKE")
        title.setStyleSheet(f"color: {ACCENT}; font-weight: 700; letter-spacing: 2px; font-size: 11px;")
        header.addWidget(title)
        header.addStretch()
        menu_btn = QToolButton()
        menu_btn.setText("⋯")
        menu_btn.setToolTip("Menú")
        menu_btn.clicked.connect(lambda: self._open_menu(QCursor.pos()))
        header.addWidget(menu_btn)
        close_btn = QToolButton()
        close_btn.setText("✕")
        close_btn.setToolTip("Salir")
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        root.addLayout(header)

        self.sprite_label = QLabel("?")
        self.sprite_label.setAlignment(Qt.AlignCenter)
        self.sprite_label.setFixedSize(SPRITE_SIZE + 8, SPRITE_SIZE + 8)
        self.sprite_label.setStyleSheet(f"color: {MUTED}; font-size: 48px;")
        sprite_row = QHBoxLayout()
        sprite_row.addStretch()
        sprite_row.addWidget(self.sprite_label)
        sprite_row.addStretch()
        root.addLayout(sprite_row)

        self.name_label = QLabel("—")
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFont(QFont("Segoe UI", 15, QFont.Bold))
        root.addWidget(self.name_label)

        self.level_label = QLabel("")
        self.level_label.setAlignment(Qt.AlignCenter)
        self.level_label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        root.addWidget(self.level_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(14)
        root.addWidget(self.progress)
        self._progress_anim = QPropertyAnimation(self.progress, b"value", self)
        self._progress_anim.setDuration(650)
        self._progress_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.next_label = QLabel("")
        self.next_label.setAlignment(Qt.AlignCenter)
        self.next_label.setStyleSheet(f"color: {MUTED}; font-size: 11px;")
        root.addWidget(self.next_label)

        counters = QHBoxLayout()
        self.session_label = QLabel("Sesión: 0")
        self.session_label.setStyleSheet("font-size: 12px;")
        self.total_label = QLabel("Total: 0")
        self.total_label.setStyleSheet("font-size: 12px;")
        self.total_label.setAlignment(Qt.AlignRight)
        counters.addWidget(self.session_label)
        counters.addStretch()
        counters.addWidget(self.total_label)
        root.addLayout(counters)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        # Banner de evolución (superpuesto)
        self.banner = QLabel(self)
        self.banner.setAlignment(Qt.AlignCenter)
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet(
            f"background: rgba(255, 203, 5, 235); color: #1a1a1a; border-radius: 10px;"
            " font-weight: 700; font-size: 12px; padding: 6px;"
        )
        self.banner.hide()

        # Destello blanco (superpuesto)
        self.flash = QWidget(self)
        self.flash.setStyleSheet("background: white; border-radius: 16px;")
        self._flash_effect = QGraphicsOpacityEffect(self.flash)
        self._flash_effect.setOpacity(0.0)
        self.flash.setGraphicsEffect(self._flash_effect)
        self.flash.hide()

        self.adjustSize()

    def _build_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("Toke-Poke")
        menu = QMenu()
        show_action = QAction("Mostrar / ocultar", menu)
        show_action.triggered.connect(self._toggle_visible)
        quit_action = QAction("Salir", menu)
        quit_action.triggered.connect(self.close)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self._toggle_visible() if reason == QSystemTrayIcon.Trigger else None
        )
        self._update_tray_icon()
        self.tray.show()

    def _update_tray_icon(self) -> None:
        pid = self.manager.active
        pix = None
        if pid is not None and self.manager.sprites.has(pid):
            pix = load_sprite(self.manager.sprite_path(pid), 64)
        if pix is not None:
            icon = QIcon(pix)
        else:
            icon = QApplication.windowIcon()  # Pokébola (icono de la aplicación)
            if icon.isNull():
                fallback = QPixmap(64, 64)
                fallback.fill(QColor(ACCENT))
                icon = QIcon(fallback)
        if self.tray is not None:
            self.tray.setIcon(icon)

    # ---- ciclo de vida ------------------------------------------------------
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._tracker_started and self._auto_start_tracker:
            self._tracker_started = True
            if self._first_run:
                QTimer.singleShot(0, self._first_run_flow)
            else:
                self.start_tracking()

    def start_tracking(self) -> None:
        if not self.tracker.isRunning():
            self.tracker.start()
            self._set_status(f"Observando {self.tracker.claude_dir}")

    def _first_run_flow(self) -> None:
        dialog = StarterDialog(self.manager, self.loader, self)
        pid = STARTERS[0]
        if dialog.exec() == QDialog.Accepted and dialog.choice:
            pid = dialog.choice
        self.set_starter(pid)
        self.start_tracking()

    def set_starter(self, pid: int) -> None:
        self.manager.choose_starter(pid)
        self._first_run = False
        self.loader.request(self.manager.sprites_needed())
        self.refresh()

    def closeEvent(self, event) -> None:
        self._save_position()
        try:
            self.tracker.stop()
        except Exception:
            pass
        try:
            self.loader.stop()
        except Exception:
            pass
        self.manager.save()
        if self.tray is not None:
            self.tray.hide()
        super().closeEvent(event)
        QApplication.instance().quit()

    # ---- posición y arrastre ------------------------------------------------
    def _restore_position(self) -> None:
        pos = self.manager.state.get("window_pos")
        screen = QApplication.primaryScreen()
        if isinstance(pos, list) and len(pos) == 2 and screen is not None:
            geo = screen.availableGeometry()
            if geo.contains(QPoint(int(pos[0]) + 20, int(pos[1]) + 20)):
                self.move(int(pos[0]), int(pos[1]))
                return
        if screen is not None:
            geo = screen.availableGeometry()
            self.adjustSize()
            self.move(geo.right() - self.width() - 24, geo.bottom() - self.height() - 24)

    def _save_position(self) -> None:
        self.manager.state["window_pos"] = [self.x(), self.y()]

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self._save_position()
            self.manager.save()

    def contextMenuEvent(self, event) -> None:
        self._open_menu(event.globalPos())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)
        painter.fillPath(path, BG)
        painter.setPen(QPen(BORDER, 1.5))
        painter.drawPath(path)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.flash.setGeometry(self.rect())
        self.banner.setGeometry(12, 8, self.width() - 24, 44)

    # ---- menú ------------------------------------------------------------------
    def _open_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        starter_menu = menu.addMenu("Elegir Pokémon inicial")
        for pid in STARTERS:
            action = starter_menu.addAction(name_of(pid))
            if self.manager.sprites.has(pid):
                pix = load_sprite(self.manager.sprite_path(pid), 32)
                if pix:
                    action.setIcon(QIcon(pix))
            action.triggered.connect(lambda _=False, p=pid: self._confirm_starter(p))

        dex = menu.addMenu("Evoluciones desbloqueadas")
        unlocked = self.manager.unlocked
        if not unlocked:
            dex.addAction("(ninguna)").setEnabled(False)
        for pid in unlocked:
            a = dex.addAction(f"#{pid:03d} {name_of(pid)}")
            a.setEnabled(False)

        menu.addSeparator()
        on_top = menu.addAction("Siempre visible")
        on_top.setCheckable(True)
        on_top.setChecked(bool(self.manager.state.get("always_on_top", True)))
        on_top.toggled.connect(self._set_always_on_top)
        menu.addAction("Reiniciar progreso", self._confirm_reset)
        menu.addSeparator()
        menu.addAction("Salir", self.close)
        menu.exec(global_pos)

    def _confirm_starter(self, pid: int) -> None:
        if self.manager.has_starter:
            ok = QMessageBox.question(
                self,
                "Cambiar inicial",
                f"Cambiar a {name_of(pid)} reinicia el progreso de evolución. ¿Continuar?",
            )
            if ok != QMessageBox.Yes:
                return
        self.set_starter(pid)

    def _confirm_reset(self) -> None:
        ok = QMessageBox.question(self, "Reiniciar", "¿Borrar el Pokémon activo y su progreso?")
        if ok == QMessageBox.Yes:
            self.manager.reset()
            self._first_run = True
            self.refresh()
            QTimer.singleShot(0, self._first_run_flow)

    def _set_always_on_top(self, enabled: bool) -> None:
        self.manager.state["always_on_top"] = bool(enabled)
        self.manager.save()
        flags = Qt.FramelessWindowHint | Qt.Tool
        if enabled:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _toggle_visible(self) -> None:
        self.setVisible(not self.isVisible())

    # ---- actualización de datos ----------------------------------------------
    def _on_tokens_added(self, added: int, offsets: dict, initial: bool) -> None:
        self.manager.state["file_offsets"] = offsets
        count_xp = not (initial and self._skip_initial_xp)
        events = self.manager.add_tokens(added, count_xp=count_xp)
        if not initial:
            self.session_tokens += added
        self.manager.save()
        self.refresh()
        self.tokens_updated.emit(self.session_tokens, self.manager.total_tokens)
        for evo in events:
            self._evo_queue.append((evo.source, evo.target))
        self.loader.request(self.manager.sprites_needed())
        self._play_next_evolution()

    def refresh(self) -> None:
        m = self.manager
        pid = m.active
        if pid is None:
            self.name_label.setText("Sin Pokémon")
            self.level_label.setText("Elige un inicial en el menú ⋯")
            self.next_label.setText("")
            self._animate_progress(0)
        else:
            self.name_label.setText(f"{name_of(pid)}")
            self.level_label.setText(f"#{pid:03d}  ·  Nv. {m.level}")
            done, needed, frac = m.progress()
            candidates = m.next_pokemon_candidates()
            if needed:
                target = " / ".join(name_of(c) for c in candidates)
                self.next_label.setText(f"{format_tokens(done)} / {format_tokens(needed)} → {target}")
            else:
                self.next_label.setText("Forma final alcanzada ★")
            self._animate_progress(int(frac * 1000))
        self._set_sprite(pid)
        self.session_label.setText(f"Sesión: {format_tokens(self.session_tokens)}")
        self.total_label.setText(f"Total: {format_tokens(m.total_tokens)}")
        self.session_label.setToolTip(f"{self.session_tokens:,} tokens en esta sesión")
        self.total_label.setToolTip(f"{m.total_tokens:,} tokens acumulados")

    def _animate_progress(self, value: int) -> None:
        self._progress_anim.stop()
        self._progress_anim.setStartValue(self.progress.value())
        self._progress_anim.setEndValue(max(0, min(1000, value)))
        self._progress_anim.start()

    def _set_sprite(self, pid: int | None) -> None:
        if pid is None:
            self.sprite_label.setPixmap(QPixmap())
            self.sprite_label.setText("?")
            return
        if self.manager.sprites.has(pid):
            pix = load_sprite(self.manager.sprite_path(pid))
            if pix is not None:
                self.sprite_label.setText("")
                self.sprite_label.setPixmap(pix)
                self._update_tray_icon()
                return
        self.sprite_label.setPixmap(QPixmap())
        self.sprite_label.setText("…")

    def _on_sprite_ready(self, pid: int, _path: str) -> None:
        if pid == self.manager.active:
            self._set_sprite(pid)

    def _on_sprite_failed(self, pid: int, error: str) -> None:
        self._set_status(f"No se pudo descargar el sprite #{pid}: {error[:60]}")

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    # ---- animación de evolución ----------------------------------------------
    def _play_next_evolution(self) -> None:
        if self._evo_running or not self._evo_queue:
            return
        self._evo_running = True
        source, target = self._evo_queue.popleft()

        # 1) temblor del sprite
        base = self.sprite_label.pos()
        shake = QSequentialAnimationGroup(self)
        for i, dx in enumerate((-6, 6, -5, 5, -3, 3, 0)):
            anim = QPropertyAnimation(self.sprite_label, b"pos", shake)
            anim.setDuration(55)
            anim.setEndValue(base + QPoint(dx, 0))
            shake.addAnimation(anim)

        # 2) destello blanco: entra, se cambia el sprite, sale
        fade_in = QPropertyAnimation(self._flash_effect, b"opacity", self)
        fade_in.setDuration(260)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.InQuad)
        fade_out = QPropertyAnimation(self._flash_effect, b"opacity", self)
        fade_out.setDuration(900)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.OutCubic)

        def show_flash():
            self.flash.setGeometry(self.rect())
            self.flash.show()
            self.flash.raise_()

        def swap():
            self._set_sprite(target)
            self.refresh()
            self.banner.setText(f"¡{name_of(source)} evolucionó a {name_of(target)}!")
            self.banner.show()
            self.banner.raise_()

        def finish():
            self.flash.hide()
            self.evolutions_played.append((source, target))
            self.evolution_played.emit(source, target)
            QTimer.singleShot(3500, self.banner.hide)
            self._evo_running = False
            self._play_next_evolution()

        sequence = QSequentialAnimationGroup(self)
        sequence.addAnimation(shake)
        sequence.addAnimation(fade_in)
        sequence.addAnimation(fade_out)
        shake.finished.connect(show_flash)
        fade_in.finished.connect(swap)
        sequence.finished.connect(finish)
        sequence.start(QPropertyAnimation.DeleteWhenStopped)
