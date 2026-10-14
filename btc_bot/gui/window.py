"""Главное окно: подключение телефона, настройки и запуск бота.

Всё, что ходит в adb, выполняется в фоновых потоках. Результат возвращается
в окно сигналом Bridge.call: Qt сам доставит его в главный поток.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QFont, QFontDatabase, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, imaging
from ..adb import AdbError, Device
from ..campaign import CampaignBot, RunResult
from ..cli import STOP_TITLES, resolve_package, session_dir
from ..config import Config
from ..notify import notify
from ..paths import DATA_DIR
from ..platform_tools import download_platform_tools, find_adb
from ..screens import Classifier
from ..vision import TemplateLibrary, normalize
from . import theme
from .icons import icon

log = logging.getLogger("btc_bot")

REPO_URL = "https://github.com/xvin84/tk_btc_assistant"
SETTINGS_PATH = DATA_DIR / "gui.json"
TICK_MS = 250
PREVIEW_EVERY = 1.0  # как часто обновлять картинку экрана во время работы, с
PREVIEW_MAX_WIDTH = 960  # крупнее картинку в окне не показываем
HERO_SUB_MAX = 70  # длиннее подпись в карточке статуса обрезается

SCREEN_NAMES = {
    "map_start": "карта кампании, есть «Старт»",
    "map_claim_all": "карта кампании, «Получить все»",
    "map": "карта кампании",
    "team_setup": "расстановка",
    "battle": "бой",
    "battle_won": "победа в бою",
    "victory": "итоги: победа",
    "result_unknown": "итоги боя",
    "defeat": "поражение",
    "loading": "загрузка",
    "chain_reaction": "цепная реакция",
    "level_cleared": "уровень пройден",
    "rewards_popup": "полученные награды",
    "depth_up": "повышение глубины",
    "unknown": "не распознан",
}

# Заголовок карточки статуса и цвет точки после остановки
RESULT_STATE = {
    "done": ("Готово", theme.OK),
    "no_stamina": ("Закончилась стамина", theme.OK),
    "defeat": ("Поражение", theme.BAD),
    "error": ("Ошибка", theme.BAD),
    "stopped": ("Остановлено", theme.IDLE),
}

RISK_TEXT = (
    "Это неофициальная программа. Она нажимает на экран вместо тебя, а "
    "автоматизация нарушает правила большинства игр.\n\n"
    "Бот не лезет в клиент игры и не трогает трафик, но риск блокировки "
    "аккаунта не нулевой. Пользуясь программой, ты принимаешь этот риск."
)

HELP_TEXT = """\
<p><b>1. Режим разработчика.</b> Настройки → О телефоне → 7 раз нажми «Номер сборки».</p>
<p><b>2. Отладка по USB.</b> Настройки → Для разработчиков → «Отладка по USB».<br>
• Xiaomi/POCO: ещё «Отладка по USB (настройки безопасности)», иначе нажатия не пройдут.<br>
• OnePlus/realme/OPPO: если нажатия не проходят, включи «Отключить мониторинг разрешений».<br>
Там же включи «Не выключать экран» и держи телефон на зарядке.</p>
<p><b>3. Кабель.</b> Режим USB: «Передача файлов». На телефоне появится окно
«Разрешить отладку по USB?». Нажми «Разрешить», лучше с галочкой «Всегда разрешать».</p>
<p><b>4. Игра.</b> Язык игры: русский. Открой карту цепной кампании, где видна кнопка
«Старт», и нажми «Проверить» на вкладке «Телефон».</p>
<p><b>5. Первый запуск.</b> Включи «Пробный режим» в настройках и пройди один забег
руками: в журнале будет видно, что бот распознаёт и куда нажал бы. Если всё верно,
выключи пробный режим и нажми «Запустить».</p>
<p>Пока бот работает, телефон лучше не трогать.</p>
<p>Без кабеля (Android 11+): «Для разработчиков» → «Беспроводная отладка», затем в
командной строке <code>adb pair IP:порт</code> и <code>adb connect IP:порт</code>.</p>
"""


# --- мелкие помощники -----------------------------------------------------

class Bridge(QObject):
    """Сигналы из фоновых потоков в окно."""

    call = Signal(object, object)  # (функция, значение)
    line = Signal(str)


class SignalLogHandler(logging.Handler):
    def __init__(self, bridge: Bridge):
        super().__init__()
        self.bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        self.bridge.line.emit(self.format(record))


class Preview(QLabel):
    """Картинка экрана телефона: рамка в пропорциях экрана игры, картинка вписана в неё."""

    ASPECT = 582 / 1280  # высота к ширине у рабочего кадра

    def __init__(self):
        super().__init__("Нет картинки")
        self.setObjectName("preview")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Ширину не берём из картинки, иначе окно растёт само; высота следует за шириной
        policy = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumWidth(320)
        self._pixmap: QPixmap | None = None

    def hasHeightForWidth(self) -> bool:  # noqa: N802 — имя из Qt
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 — имя из Qt
        return round(width * self.ASPECT)

    def resizeEvent(self, event) -> None:  # noqa: N802 — имя из Qt
        super().resizeEvent(event)
        self.setFixedHeight(self.heightForWidth(self.width()))
        self._rescale()

    def set_frame(self, frame: np.ndarray) -> None:
        h, w = frame.shape[:2]
        if w > PREVIEW_MAX_WIDTH:
            height = max(1, round(h * PREVIEW_MAX_WIDTH / w))
            frame = imaging.resize(frame, PREVIEW_MAX_WIDTH, height)
            h, w = frame.shape[:2]
        rgb = np.ascontiguousarray(frame[:, :, ::-1])
        image = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        self._pixmap = QPixmap.fromImage(image)
        self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        size = self.size() - QSize(4, 4)
        self.setPixmap(self._pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))


class StatusRow:
    """Строка проверки: цветная точка, название и пояснение."""

    def __init__(self, grid: QGridLayout, row: int, title: str):
        self.dot = QLabel("●")
        self.dot.setObjectName("heroDot")
        self.dot.setStyleSheet("font-size: 14px;")
        name = QLabel(title)
        self.text = QLabel("—")
        self.text.setObjectName("dim")
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        grid.addWidget(self.dot, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(name, row, 1, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(self.text, row, 2)
        self.set(theme.IDLE, "—")

    def set(self, color: str, text: str) -> None:
        self.dot.setStyleSheet(f"font-size: 14px; color: {color};")
        self.text.setText(text)


def load_gui_settings() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_gui_settings(data: dict) -> None:
    try:
        SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    except OSError as e:
        log.warning("Не удалось сохранить настройки окна: %s", e)


def open_path(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 — открыть папку в проводнике
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def _page(*widgets: QWidget) -> QScrollArea:
    body = QWidget()
    lay = QVBoxLayout(body)
    lay.setContentsMargins(0, 0, 6, 0)
    for w in widgets:
        lay.addWidget(w)
    lay.addStretch(1)
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(body)
    return area


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("hintLabel")
    label.setWordWrap(True)
    return label


# --- окно -----------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.settings = load_gui_settings()
        self.bridge = Bridge()
        self.bridge.call.connect(lambda fn, value: fn(value))

        self.classifier = Classifier(TemplateLibrary.load())
        self.adb_path = find_adb(cfg.device.adb)
        self.serial: str | None = cfg.device.serial or None
        self.phone_ready = False
        self.checking = False

        self.bot: CampaignBot | None = None
        self.started_at = 0.0
        self.last_preview = 0.0
        self.last_screen: str | None = None
        self.session: Path | None = None
        self.file_handler: logging.Handler | None = None

        self.setWindowTitle("Помощник Break the Chains")
        self.setWindowIcon(icon("chain", theme.ACCENT))
        self.resize(1100, 680)
        self.setMinimumSize(960, 600)
        self._build_ui()
        self._setup_logging()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(TICK_MS)

    # --- построение -----------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(0)
        title = QLabel("Break the Chains")
        title.setObjectName("appTitle")
        version = QLabel(f"Помощник · v{__version__}")
        version.setObjectName("appVersion")
        left.addWidget(title)
        left.addWidget(version)
        self.nav = QListWidget()
        self.nav.setObjectName("sidebar")
        self.nav.setFixedWidth(170)
        self.nav.setIconSize(QSize(20, 20))
        for icon_name, label in (("phone", "Телефон"), ("sliders", "Настройки"),
                                 ("help", "Справка")):
            self.nav.addItem(QListWidgetItem(icon(icon_name), label))
        left.addWidget(self.nav, 1)

        self.pages = QStackedWidget()
        self.pages.addWidget(_page(self._group_connection(), self._hint_game()))
        self.pages.addWidget(_page(self._group_runs(), self._group_behavior()))
        self.pages.addWidget(_page(self._group_help(), self._group_about()))
        self.pages.setMinimumWidth(340)
        self.pages.setMaximumWidth(430)
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(self._hero())
        self.preview = Preview()
        right.addWidget(self.preview)
        self.screen_label = QLabel("Распознано: —")
        self.screen_label.setObjectName("dim")
        self.screen_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.screen_label)
        right.addLayout(self._stats())
        right.addWidget(self._log_card(), 1)

        root.addLayout(left, 0)
        root.addWidget(self.pages, 0)
        root.addLayout(right, 1)
        self.setCentralWidget(central)

    def _hero(self) -> QFrame:
        hero = QFrame()
        hero.setObjectName("hero")
        lay = QHBoxLayout(hero)
        lay.setContentsMargins(14, 10, 14, 10)
        self.hero_dot = QLabel("●")
        self.hero_dot.setObjectName("heroDot")
        text = QVBoxLayout()
        text.setSpacing(0)
        self.hero_state = QLabel()
        self.hero_state.setObjectName("heroState")
        self.hero_sub = QLabel()
        self.hero_sub.setObjectName("heroSub")
        text.addWidget(self.hero_state)
        text.addWidget(self.hero_sub)
        self.start_btn = QPushButton()
        self.start_btn.setMinimumWidth(150)
        self.start_btn.clicked.connect(self.toggle_run)
        lay.addWidget(self.hero_dot)
        lay.addLayout(text, 1)
        lay.addWidget(self.start_btn)
        self._set_start_button(running=False)
        self._set_hero("Не готово", "Подключи телефон и нажми «Проверить»", theme.IDLE)
        return hero

    def _stats(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        self.stat_runs = self._stat(row, "забегов пройдено")
        self.stat_depth = self._stat(row, "повышений глубины")
        self.stat_time = self._stat(row, "время работы")
        self.stat_time.setText("0:00")
        return row

    def _stat(self, row: QHBoxLayout, caption: str) -> QLabel:
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 8, 14, 10)
        lay.setSpacing(0)
        value = QLabel("0")
        value.setObjectName("statValue")
        label = QLabel(caption)
        label.setObjectName("dim")
        lay.addWidget(value)
        lay.addWidget(label)
        row.addWidget(card, 1)
        return value

    def _group_connection(self) -> QGroupBox:
        box = QGroupBox("Подключение")
        lay = QVBoxLayout(box)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(2, 1)
        self.row_adb = StatusRow(grid, 0, "ADB")
        self.row_phone = StatusRow(grid, 1, "Телефон")
        self.row_game = StatusRow(grid, 2, "Игра")
        lay.addLayout(grid)

        self.device_box = QComboBox()
        self.device_box.setToolTip("Подключено несколько устройств: выбери нужное")
        self.device_box.activated.connect(self._on_device_selected)
        self.device_box.hide()
        lay.addWidget(self.device_box)

        buttons = QHBoxLayout()
        self.check_btn = QPushButton(icon("refresh"), "Проверить")
        self.check_btn.clicked.connect(self.check_connection)
        self.download_btn = QPushButton(icon("download"), "Скачать adb")
        self.download_btn.setToolTip("Официальный набор Android platform-tools с сайта Google, "
                                     "около 7 МБ")
        self.download_btn.clicked.connect(self.download_adb)
        self.download_btn.hide()
        buttons.addWidget(self.check_btn)
        buttons.addWidget(self.download_btn)
        buttons.addStretch(1)
        lay.addLayout(buttons)
        return box

    def _hint_game(self) -> QLabel:
        return _hint("Открой в игре карту цепной кампании, где видна кнопка «Старт», и "
                     "нажми «Проверить». Как подготовить телефон, написано в «Справке».")

    def _group_runs(self) -> QGroupBox:
        s = self.settings
        c = self.cfg.campaign
        box = QGroupBox("Сколько забегов")
        lay = QVBoxLayout(box)
        self.radio_all = QRadioButton("Пока есть стамина")
        self.radio_limit = QRadioButton("Не больше")
        group = QButtonGroup(box)
        group.addButton(self.radio_all)
        group.addButton(self.radio_limit)
        limit_mode = s.get("limit_mode", "limit" if c.max_runs else "all")
        (self.radio_limit if limit_mode == "limit" else self.radio_all).setChecked(True)
        self.max_runs = QSpinBox()
        self.max_runs.setRange(1, 999)
        self.max_runs.setValue(int(s.get("max_runs", c.max_runs or 5)))
        limit_row = QHBoxLayout()
        limit_row.addWidget(self.radio_limit)
        limit_row.addWidget(self.max_runs)
        limit_row.addStretch(1)
        lay.addWidget(self.radio_all)
        lay.addLayout(limit_row)
        note = QLabel("Забег — один этап кампании: бои подряд до экрана «ПОБЕДА». "
                      "Сколько в нём боёв, боту неважно.")
        note.setObjectName("dim")
        note.setWordWrap(True)
        lay.addWidget(note)

        self.radio_all.toggled.connect(self._on_settings_changed)
        self.max_runs.valueChanged.connect(self._on_settings_changed)
        self._sync_limit()
        return box

    def _group_behavior(self) -> QGroupBox:
        s = self.settings
        c = self.cfg.campaign
        box = QGroupBox("Поведение")
        lay = QVBoxLayout(box)
        self.exit_on_defeat = QCheckBox("Закрыть игру при поражении")
        self.exit_on_defeat.setChecked(bool(s.get("exit_on_defeat", c.exit_game_on_defeat)))
        # Пробный режим не запоминаем: включённый «навсегда», он выглядит как поломка
        self.dry_run = QCheckBox("Пробный режим (ничего не нажимать)")
        self.dry_run.setToolTip("Бот только смотрит и пишет в журнал, куда нажал бы. "
                                "Играешь ты сам.")
        self.save_frames = QCheckBox("Сохранять кадры (для отчёта об ошибке)")
        self.save_frames.setToolTip("Кадр при каждой смене экрана попадёт в папку с логами")
        self.save_frames.setChecked(bool(s.get("save_frames", c.save_frames)))
        for w in (self.exit_on_defeat, self.dry_run, self.save_frames):
            lay.addWidget(w)
        self.exit_on_defeat.toggled.connect(self._on_settings_changed)
        self.save_frames.toggled.connect(self._on_settings_changed)
        self.settings_widgets = [self.radio_all, self.radio_limit, self.max_runs,
                                 self.exit_on_defeat, self.dry_run, self.save_frames]
        return box

    def _log_card(self) -> QWidget:
        box = QGroupBox("Журнал")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(6, 6, 6, 6)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        # Моноширинные шрифты с кириллицей; системный по умолчанию её может не иметь
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setFamilies(["Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono",
                          "Liberation Mono", mono.family()])
        mono.setPointSize(max(8, QFont().pointSize() - 1))
        self.log_view.setFont(mono)
        self.log_view.setMinimumHeight(90)
        lay.addWidget(self.log_view, 1)
        open_btn = QPushButton(icon("folder"), "Открыть папку с логами")
        open_btn.clicked.connect(self.open_logs)
        lay.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignLeft)
        return box

    def _group_help(self) -> QGroupBox:
        box = QGroupBox("Как подготовить телефон")
        lay = QVBoxLayout(box)
        text = QLabel(HELP_TEXT)
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(text)
        return box

    def _group_about(self) -> QGroupBox:
        box = QGroupBox("О программе")
        lay = QVBoxLayout(box)
        text = QLabel(RISK_TEXT.replace("\n\n", "<br><br>"))
        text.setWordWrap(True)
        text.setObjectName("dim")
        lay.addWidget(text)
        link = QPushButton(icon("link"), "Страница на GitHub")
        link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        lay.addWidget(link, 0, Qt.AlignmentFlag.AlignLeft)
        return box

    # --- журнал ---------------------------------------------------------

    def _setup_logging(self) -> None:
        root_log = logging.getLogger("btc_bot")
        root_log.setLevel(logging.INFO)
        root_log.handlers.clear()
        handler = SignalLogHandler(self.bridge)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        root_log.addHandler(handler)
        self.log_handler = handler
        self.bridge.line.connect(self.log_view.appendPlainText)

    # --- фоновая работа -------------------------------------------------

    def _bg(self, fn, done, fail=None) -> None:
        def work():
            try:
                result = fn()
            except Exception as e:  # noqa: BLE001 — любую ошибку показываем в окне
                self.bridge.call.emit(fail or self._bg_failed, e)
            else:
                self.bridge.call.emit(done, result)

        threading.Thread(target=work, daemon=True).start()

    def _bg_failed(self, error: Exception) -> None:
        log.error("Ошибка: %s", error)

    # --- карточка статуса -----------------------------------------------

    def _set_hero(self, state: str, sub: str, color: str) -> None:
        self.hero_state.setText(state)
        # Одна строка: длинная ошибка целиком видна в подсказке и в журнале
        short = sub if len(sub) <= HERO_SUB_MAX else sub[:HERO_SUB_MAX - 1].rstrip() + "…"
        self.hero_sub.setText(short)
        self.hero_sub.setToolTip(sub if short != sub else "")
        self.hero_dot.setStyleSheet(f"color: {color};")

    def _set_start_button(self, running: bool) -> None:
        if running:
            self.start_btn.setText("■  Остановить")
            self.start_btn.setStyleSheet(theme.BTN_STOP_QSS)
        else:
            self.start_btn.setText("▶  Запустить")
            self.start_btn.setStyleSheet(theme.BTN_START_QSS)

    def _refresh_start(self) -> None:
        self.start_btn.setEnabled(self.bot is not None or self.phone_ready)

    # --- проверка подключения -------------------------------------------

    def check_connection(self) -> None:
        if self.checking or self.bot is not None:
            return
        self.checking = True
        self.check_btn.setEnabled(False)
        self.check_btn.setText("Проверяю…")
        self._set_hero("Проверяю телефон…", "Связываюсь через adb", theme.WARN)
        self._bg(self._probe, self._probe_done, self._probe_failed)

    def _probe(self) -> dict:
        info: dict = {"adb": find_adb(self.cfg.device.adb)}
        if not info["adb"]:
            return info
        capture = self.cfg.device.capture
        rows = Device(adb=info["adb"], capture=capture).devices()
        ready = [serial for serial, state in rows if state == "device"]
        info["ready"] = ready
        serial = self.serial if self.serial in ready else None
        if serial is None and len(ready) == 1:
            serial = ready[0]
        if serial is None and len(ready) > 1:
            info["choose"] = True
            return info
        device = Device(serial=serial, adb=info["adb"], capture=capture)
        try:
            info["serial"] = device.ensure_ready()
        except AdbError as e:
            info["phone_error"] = str(e)
            return info
        info["model"] = device.shell("getprop ro.product.model").strip()
        frame = device.screenshot()
        info["frame"] = frame
        info["screen"] = self.classifier.classify(normalize(frame)[0]).screen
        return info

    def _probe_finished(self) -> None:
        self.checking = False
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Проверить")

    def _probe_done(self, info: dict) -> None:
        self._probe_finished()
        self.adb_path = info["adb"]
        self.phone_ready = False
        self.device_box.hide()

        if not self.adb_path:
            self.row_adb.set(theme.BAD, "не найден. Скачай его кнопкой ниже: это "
                                        "официальный набор Android platform-tools")
            self.row_phone.set(theme.IDLE, "—")
            self.row_game.set(theme.IDLE, "—")
            self.download_btn.show()
            self._set_hero("Нужен adb", "Через него программа видит экран и нажимает",
                           theme.BAD)
            self._refresh_start()
            return
        self.download_btn.hide()
        self.row_adb.set(theme.OK, self.adb_path)

        ready = info.get("ready", [])
        if len(ready) > 1:
            self.device_box.clear()
            self.device_box.addItems(ready)
            self.device_box.show()
        if info.get("choose"):
            self.device_box.setCurrentIndex(-1)
            self.row_phone.set(theme.WARN, "подключено несколько устройств, выбери нужное")
            self.row_game.set(theme.IDLE, "—")
            self._set_hero("Выбери телефон", "Подключено несколько устройств", theme.WARN)
            self._refresh_start()
            return
        if "phone_error" in info:
            self.row_phone.set(theme.BAD, info["phone_error"])
            self.row_game.set(theme.IDLE, "—")
            self._set_hero("Телефон не готов", "Подсказка на вкладке «Телефон»", theme.BAD)
            self._refresh_start()
            return

        self.serial = info["serial"]
        if len(ready) > 1:
            self.device_box.setCurrentText(self.serial)
        self.phone_ready = True
        model = info.get("model") or ""
        self.row_phone.set(theme.OK, f"{model} ({self.serial})" if model else self.serial)
        screen = info["screen"]
        self._show_frame(info["frame"], screen)
        if screen == "map_start":
            self.row_game.set(theme.OK, SCREEN_NAMES[screen])
            self._set_hero("Готов к запуску", "Нажми «Запустить»", theme.OK)
        else:
            self.row_game.set(theme.WARN, f"{SCREEN_NAMES.get(screen, screen)}. Открой карту "
                                          "цепной кампании с кнопкой «Старт» и проверь ещё раз")
            self._set_hero("Телефон подключён", "Открой карту цепной кампании", theme.WARN)
        self._refresh_start()

    def _probe_failed(self, error: Exception) -> None:
        self._probe_finished()
        self.phone_ready = False
        self.row_phone.set(theme.BAD, str(error))
        self._set_hero("Нет связи с телефоном", str(error), theme.BAD)
        self._refresh_start()

    def _on_device_selected(self, _index: int) -> None:
        self.serial = self.device_box.currentText() or None
        self.check_connection()

    # --- скачивание adb -------------------------------------------------

    def download_adb(self) -> None:
        self.download_btn.setEnabled(False)
        self.download_btn.setText("Скачиваю…")

        def progress(got: int, total: int) -> None:
            self.bridge.call.emit(self._download_progress, (got, total))

        self._bg(lambda: download_platform_tools(progress), self._download_done,
                 self._download_failed)

    def _download_progress(self, value: tuple[int, int]) -> None:
        got, total = value
        self.download_btn.setText(f"Скачиваю… {got * 100 // total}%" if total
                                  else f"Скачиваю… {got // 1024} КБ")

    def _download_finished(self) -> None:
        self.download_btn.setEnabled(True)
        self.download_btn.setText("Скачать adb")

    def _download_done(self, adb: str) -> None:
        self._download_finished()
        log.info("adb скачан: %s", adb)
        self.check_connection()

    def _download_failed(self, error: Exception) -> None:
        self._download_finished()
        log.error("Не удалось скачать adb: %s", error)
        QMessageBox.critical(
            self, "Не удалось скачать adb",
            f"{error}\n\nМожно скачать вручную: developer.android.com/tools/releases/"
            f"platform-tools и распаковать папку platform-tools рядом с программой "
            f"({DATA_DIR}).")

    # --- запуск и остановка ---------------------------------------------

    def _run_config(self) -> Config:
        cfg = copy.deepcopy(self.cfg)
        c = cfg.campaign
        c.max_runs = self.max_runs.value() if self.radio_limit.isChecked() else 0
        c.exit_game_on_defeat = self.exit_on_defeat.isChecked()
        c.save_frames = self.save_frames.isChecked()
        return cfg

    def toggle_run(self) -> None:
        if self.bot is None:
            self.start()
        else:
            self.stop()

    def start(self) -> None:
        if not self.phone_ready or self.bot is not None:
            return
        cfg = self._run_config()
        self.session = session_dir(cfg.logs_dir)
        self.session.mkdir(parents=True, exist_ok=True)
        self.file_handler = logging.FileHandler(self.session / "bot.log", encoding="utf-8")
        self.file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger("btc_bot").addHandler(self.file_handler)

        device = Device(serial=self.serial, adb=self.adb_path, capture=cfg.device.capture)
        dry_run = self.dry_run.isChecked()
        bot = CampaignBot(device, self.classifier, cfg.campaign, session_dir=self.session,
                          dry_run=dry_run)
        self.bot = bot
        self.started_at = time.monotonic()
        self.last_preview = 0.0
        self.last_screen = None

        def work() -> RunResult:
            bot.package = resolve_package(device, cfg.device.package)
            return bot.run()

        self._bg(work, self._finished, self._crashed)
        self._set_start_button(running=True)
        self.check_btn.setEnabled(False)
        for w in self.settings_widgets:
            w.setEnabled(False)
        if dry_run:
            self._set_hero("Пробный режим", "Играй сам: бот только смотрит", theme.WARN)
        else:
            self._set_hero("Работает", "Телефон лучше не трогать", theme.OK)

    def stop(self) -> None:
        if self.bot is None:
            return
        self.bot.request_stop()
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Останавливаю…")
        self._set_hero("Останавливаю…", "После текущего шага", theme.WARN)

    def _tick(self) -> None:
        if self.bot is not None:
            self._update_running()

    def _update_running(self, force: bool = False) -> None:
        bot = self.bot
        now = time.monotonic()
        self.stat_runs.setText(str(bot.runs_done))
        self.stat_depth.setText(str(bot.depth_ups))
        elapsed = int(now - self.started_at)
        h, rest = divmod(elapsed, 3600)
        self.stat_time.setText(f"{h}:{rest // 60:02d}:{rest % 60:02d}" if h
                               else f"{rest // 60}:{rest % 60:02d}")
        if (force or now - self.last_preview >= PREVIEW_EVERY) and bot.last_raw is not None:
            self.last_preview = now
            self._show_frame(bot.last_raw, bot.screen)
        if bot.screen != self.last_screen and not bot.stop_requested:
            self.last_screen = bot.screen
            mode = "Пробный режим" if bot.dry_run else "Работает"
            self.hero_state.setText(f"{mode}: {SCREEN_NAMES.get(bot.screen or '', '…')}")

    def _finished(self, result: RunResult) -> None:
        if self.bot is not None:
            self._update_running(force=True)
        state, color = RESULT_STATE.get(result.kind, (result.kind, theme.BAD))
        sub = f"Забегов: {result.runs_done}, глубина +{result.depth_ups}"
        if result.kind != "stopped":
            sub = f"{result.reason}. {sub}"
        if result.game_closed:
            sub += ". Игра закрыта"
        self._reset_after_run()
        self._set_hero(state, sub, color)
        if result.kind != "stopped":
            QApplication.beep()
            notify(f"BtC бот остановлен: {STOP_TITLES.get(result.kind, result.kind)}",
                   f"{result.reason}. Забегов: {result.runs_done}, "
                   f"глубина +{result.depth_ups}")

    def _crashed(self, error: Exception) -> None:
        log.error("Бот упал: %s", error)
        if self.bot is not None:
            self._update_running(force=True)
        self._reset_after_run()
        self._set_hero("Ошибка", str(error), theme.BAD)
        QApplication.beep()

    def _reset_after_run(self) -> None:
        self.bot = None
        if self.file_handler is not None:
            logging.getLogger("btc_bot").removeHandler(self.file_handler)
            self.file_handler.close()
            self.file_handler = None
        self._set_start_button(running=False)
        self.check_btn.setEnabled(True)
        for w in self.settings_widgets:
            w.setEnabled(True)
        self._sync_limit()
        self._refresh_start()

    # --- мелочи ---------------------------------------------------------

    def _show_frame(self, frame: np.ndarray, screen: str | None) -> None:
        self.preview.set_frame(frame)
        name = SCREEN_NAMES.get(screen or "", screen or "—")
        self.screen_label.setText(f"Распознано: {name}")

    def _sync_limit(self) -> None:
        if self.bot is None:
            self.max_runs.setEnabled(self.radio_limit.isChecked())

    def _on_settings_changed(self, *_args) -> None:
        self._sync_limit()
        self.settings.update(
            limit_mode="limit" if self.radio_limit.isChecked() else "all",
            max_runs=self.max_runs.value(),
            exit_on_defeat=self.exit_on_defeat.isChecked(),
            save_frames=self.save_frames.isChecked(),
        )
        save_gui_settings(self.settings)

    def open_logs(self) -> None:
        path = self.session or session_dir(self.cfg.logs_dir).parent
        path.mkdir(parents=True, exist_ok=True)
        try:
            open_path(path)
        except OSError as e:
            QMessageBox.information(self, "Папка с логами", f"{path}\n\n{e}")

    def first_launch(self) -> bool:
        """Предупреждение о риске при первом запуске. False = пользователь отказался."""
        if not self.settings.get("accepted_risk"):
            answer = QMessageBox.warning(
                self, "Перед началом", RISK_TEXT,
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Ok:
                return False
            self.settings["accepted_risk"] = True
            save_gui_settings(self.settings)
        self.check_connection()
        return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 — имя из Qt
        if self.bot is not None:
            answer = QMessageBox.question(
                self, "Бот работает", "Бот ещё работает. Остановить его и закрыть программу?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.bot.request_stop()
        logging.getLogger("btc_bot").removeHandler(self.log_handler)
        event.accept()
