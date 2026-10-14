"""Окно программы: подключение телефона, настройки и запуск бота.

Всё, что ходит в adb, выполняется в фоновых потоках. Результаты попадают
в очередь событий, а окно разбирает её по таймеру: Tk можно трогать
только из главного потока.
"""

from __future__ import annotations

import base64
import copy
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from . import __version__, imaging
from .adb import AdbError, Device
from .campaign import CampaignBot, RunResult
from .cli import STOP_TITLES, resolve_package, session_dir
from .config import Config, load_config
from .notify import notify
from .paths import CONFIG_PATH, DATA_DIR
from .platform_tools import download_platform_tools, find_adb
from .screens import Classifier
from .vision import TemplateLibrary, normalize

log = logging.getLogger("btc_bot")

REPO_URL = "https://github.com/xvin84/tk_btc_assistant"
SETTINGS_PATH = DATA_DIR / "gui.json"
PREVIEW_WIDTH = 420
POLL_MS = 100
STATS_EVERY = 0.5  # как часто обновлять счётчики, с
PREVIEW_EVERY = 1.5  # как часто обновлять картинку экрана во время работы, с

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

RESULT_TEXT = {
    "done": "Готово: пройдено столько забегов, сколько просили",
    "no_stamina": "Готово: закончилась стамина",
    "defeat": "Поражение, бот остановился",
    "error": "Бот остановился из-за ошибки",
    "stopped": "Остановлено",
}

RISK_TEXT = (
    "Это неофициальная программа. Она нажимает на экран вместо тебя, а "
    "автоматизация нарушает правила большинства игр.\n\n"
    "Бот не лезет в клиент игры и не трогает трафик, но риск блокировки "
    "аккаунта не нулевой. Пользуясь программой, ты принимаешь этот риск."
)

HELP_TEXT = """\
1. Включи режим разработчика
   Настройки → О телефоне → 7 раз нажми «Номер сборки».

2. Включи отладку по USB
   Настройки → Для разработчиков → «Отладка по USB».
   • Xiaomi/POCO: ещё «Отладка по USB (настройки безопасности)», иначе нажатия не пройдут.
   • OnePlus/realme/OPPO: если нажатия не проходят, включи «Отключить мониторинг разрешений».
   Там же включи «Не выключать экран» и держи телефон на зарядке.

3. Подключи телефон кабелем
   Режим USB: «Передача файлов». На телефоне появится окно
   «Разрешить отладку по USB?». Нажми «Разрешить» (лучше с галочкой
   «Всегда разрешать с этого компьютера»).

4. Подготовь игру
   Язык игры: русский. Открой карту цепной кампании, где видна кнопка «Старт».
   Нажми «Проверить» в программе: в строке «Игра» должно быть
   «карта кампании, есть «Старт»».

5. Первый запуск
   Включи «Пробный режим» и пройди один забег руками: в журнале будет видно,
   что бот распознаёт и куда нажал бы. Если всё верно, выключи пробный режим
   и нажми «Запустить».

Пока бот работает, телефон лучше не трогать.

Без кабеля (Android 11+): «Для разработчиков» → «Беспроводная отладка».
Это пока делается в командной строке: adb pair IP:порт, затем adb connect IP:порт.
"""


# --- цвета и стиль ------------------------------------------------------

# Тёмная тема: те же токены, что в Adalight (adalight/gui/theme.py)
BG = "#202225"
CARD = "#26282c"
INPUT = "#1b1d20"
BORDER = "#34373d"
HOVER = "#3d4148"
PRESSED = "#2a2c30"
TEXT = "#e4e4e7"
MUTED = "#9a9da3"
TITLE = "#9db1ff"
ACCENT = "#6c8cff"
START = "#2e7d46"
START_HOVER = "#379554"
STOP = "#8b2e2e"
STOP_HOVER = "#a63a3a"
OK = "#2ca661"
WARN = "#e0a030"
BAD = "#e5534b"
IDLE = "#5c6068"


def _setup_style(root: tk.Tk) -> None:
    default = tkfont.nametofont("TkDefaultFont")
    default.configure(size=10)
    tkfont.nametofont("TkTextFont").configure(size=10)
    family = default.actual("family")

    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=BG)
    # Выпадающий список Combobox — обычный tk-виджет, ему цвета задаются так
    root.option_add("*TCombobox*Listbox.background", CARD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", HOVER)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)

    style.configure(".", background=BG, foreground=TEXT, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, focuscolor=ACCENT,
                    troughcolor=INPUT, fieldbackground=INPUT, selectbackground=ACCENT,
                    selectforeground="#ffffff", insertcolor=TEXT)
    style.map(".", foreground=[("disabled", IDLE)])
    style.configure("Card.TFrame", background=CARD, relief="solid", borderwidth=1)
    style.configure("Inner.TFrame", background=CARD)
    style.configure("Card.TLabel", background=CARD)
    style.configure("Muted.Card.TLabel", background=CARD, foreground=MUTED)
    style.configure("CardTitle.TLabel", background=CARD, foreground=TITLE,
                    font=(family, 11, "bold"))
    style.configure("Title.TLabel", font=(family, 16, "bold"))
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Status.TLabel", font=(family, 11))
    style.configure("Stat.TLabel", background=CARD, font=(family, 18, "bold"))

    for name in ("Card.TCheckbutton", "Card.TRadiobutton"):
        style.configure(name, background=CARD, indicatorbackground=HOVER,
                        indicatorforeground="#ffffff", upperbordercolor=BORDER,
                        lowerbordercolor=BORDER)
        style.map(name, background=[("active", CARD)],
                  indicatorbackground=[("selected", ACCENT), ("active", BORDER)])

    style.configure("TButton", padding=(12, 5), background=HOVER, bordercolor=BORDER,
                    lightcolor=HOVER, darkcolor=HOVER)
    style.map("TButton",
              background=[("disabled", BG), ("pressed", PRESSED), ("active", BORDER)],
              lightcolor=[("pressed", PRESSED), ("active", BORDER)],
              darkcolor=[("pressed", PRESSED), ("active", BORDER)])
    style.configure("Link.TButton", padding=(4, 2), foreground=ACCENT, background=CARD,
                    borderwidth=0, lightcolor=CARD, darkcolor=CARD)
    style.map("Link.TButton", background=[("active", CARD)],
              foreground=[("active", TITLE)])
    for name, color, hover in (("Start.TButton", START, START_HOVER),
                               ("Stop.TButton", STOP, STOP_HOVER)):
        style.configure(name, font=(family, 13, "bold"), padding=(24, 10),
                        foreground="#ffffff", background=color, bordercolor=color,
                        lightcolor=color, darkcolor=color)
        style.map(name,
                  background=[("disabled", HOVER), ("active", hover)],
                  lightcolor=[("disabled", HOVER), ("active", hover)],
                  darkcolor=[("disabled", HOVER), ("active", hover)],
                  bordercolor=[("disabled", HOVER), ("active", hover)],
                  foreground=[("disabled", MUTED)])

    style.configure("TSpinbox", fieldbackground=INPUT, background=HOVER, arrowcolor=TEXT,
                    bordercolor=BORDER, arrowsize=12)
    style.map("TSpinbox", fieldbackground=[("disabled", BG)],
              bordercolor=[("focus", ACCENT)])
    style.configure("TCombobox", fieldbackground=INPUT, background=HOVER, arrowcolor=TEXT,
                    foreground=TEXT)
    style.map("TCombobox", fieldbackground=[("readonly", INPUT)],
              foreground=[("readonly", TEXT)], selectbackground=[("readonly", INPUT)])
    style.configure("Vertical.TScrollbar", background=HOVER, troughcolor=INPUT,
                    bordercolor=INPUT, arrowcolor=MUTED, lightcolor=HOVER, darkcolor=HOVER)
    style.map("Vertical.TScrollbar", background=[("active", BORDER)])


class Card(ttk.Frame):
    def __init__(self, parent, title: str):
        super().__init__(parent, style="Card.TFrame", padding=14)
        ttk.Label(self, text=title, style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.columnconfigure(2, weight=1)


class StatusRow:
    """Строка проверки: цветная точка, название и пояснение."""

    def __init__(self, parent, row: int, title: str):
        self.dot = tk.Label(parent, text="●", fg=IDLE, bg=CARD, font="TkDefaultFont")
        self.dot.grid(row=row, column=0, sticky="nw", padx=(0, 6))
        ttk.Label(parent, text=title, style="Card.TLabel", width=8).grid(
            row=row, column=1, sticky="nw")
        self.text = ttk.Label(parent, text="—", style="Muted.Card.TLabel", wraplength=300,
                              justify="left")
        self.text.grid(row=row, column=2, columnspan=2, sticky="nw", pady=2)

    def set(self, color: str, text: str) -> None:
        self.dot.configure(fg=color)
        self.text.configure(text=text)


class QueueLogHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord) -> None:
        self.q.put(self.format(record))


# --- настройки окна -------------------------------------------------------

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


# --- окно -----------------------------------------------------------------

class App:
    def __init__(self, root: tk.Tk, cfg: Config):
        self.root = root
        self.cfg = cfg
        self.events: queue.Queue = queue.Queue()
        self.log_lines: queue.Queue = queue.Queue()
        self.settings = load_gui_settings()

        self.classifier = Classifier(TemplateLibrary.load())
        self.adb_path = find_adb(cfg.device.adb)
        self.serial: str | None = cfg.device.serial or None
        self.phone_ready = False
        self.checking = False

        self.bot: CampaignBot | None = None
        self.started_at = 0.0
        self.last_stats = 0.0
        self.last_preview = 0.0
        self.session: Path | None = None
        self.file_handler: logging.Handler | None = None
        self.preview_image: tk.PhotoImage | None = None

        self._setup_logging()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(POLL_MS, self._poll)
        self.root.after(200, self._first_launch)

    # --- построение окна ------------------------------------------------

    def _build(self) -> None:
        root = self.root
        root.title("Помощник Break the Chains")
        root.minsize(960, 640)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=1)

        header = ttk.Frame(root, padding=(18, 14, 18, 6))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Помощник Break the Chains", style="Title.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Label(header, text=f"Автопрохождение цепной кампании · v{__version__}",
                  style="Muted.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Button(header, text="Как подготовить телефон", command=self.show_help).grid(
            row=0, column=1, rowspan=2, padx=(8, 0))
        ttk.Button(header, text="GitHub", command=lambda: webbrowser.open(REPO_URL)).grid(
            row=0, column=2, rowspan=2, padx=(8, 0))

        body = ttk.Frame(root, padding=(18, 6))
        body.grid(row=1, column=0, sticky="ew")
        body.columnconfigure(0, weight=1, uniform="col")
        body.columnconfigure(1, weight=1, uniform="col")

        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        left.columnconfigure(0, weight=1)
        self._build_connection(left).grid(row=0, column=0, sticky="ew")
        self._build_settings(left).grid(row=1, column=0, sticky="ew", pady=(12, 0))

        self._build_screen(body).grid(row=0, column=1, sticky="nsew", padx=(9, 0))

        controls = ttk.Frame(root, padding=(18, 12, 18, 6))
        controls.grid(row=2, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)
        self.start_btn = ttk.Button(controls, text="▶  Запустить", style="Start.TButton",
                                    command=self.toggle_run, state="disabled")
        self.start_btn.grid(row=0, column=0, sticky="w")
        self.status = ttk.Label(controls, text="Подключи телефон и нажми «Проверить»",
                                style="Status.TLabel", wraplength=640, justify="left")
        self.status.grid(row=0, column=1, sticky="w", padx=16)

        self._build_log(root).grid(row=3, column=0, sticky="nsew", padx=18, pady=(6, 18))

    def _build_connection(self, parent) -> Card:
        card = Card(parent, "1. Телефон")
        self.row_adb = StatusRow(card, 1, "ADB")
        self.row_phone = StatusRow(card, 2, "Телефон")
        self.row_game = StatusRow(card, 3, "Игра")

        self.device_box = ttk.Combobox(card, state="readonly", width=28)
        self.device_box.bind("<<ComboboxSelected>>", self._on_device_selected)
        self.device_box.grid(row=4, column=2, sticky="w", pady=(4, 0))
        self.device_box.grid_remove()

        buttons = ttk.Frame(card, style="Inner.TFrame")
        buttons.grid(row=5, column=0, columnspan=4, sticky="w", pady=(10, 0))
        self.check_btn = ttk.Button(buttons, text="Проверить", command=self.check_connection)
        self.check_btn.grid(row=0, column=0)
        self.download_btn = ttk.Button(buttons, text="Скачать adb (≈7 МБ, сайт Google)",
                                       command=self.download_adb)
        self.download_btn.grid(row=0, column=1, padx=(8, 0))
        self.download_btn.grid_remove()
        return card

    def _build_settings(self, parent) -> Card:
        card = Card(parent, "2. Настройки")
        s = self.settings
        c = self.cfg.campaign

        self.limit_mode = tk.StringVar(value=s.get("limit_mode", "limit" if c.max_runs else "all"))
        self.max_runs = tk.IntVar(value=int(s.get("max_runs", c.max_runs or 5)))
        self.exit_on_defeat = tk.BooleanVar(value=s.get("exit_on_defeat", c.exit_game_on_defeat))
        self.save_frames = tk.BooleanVar(value=s.get("save_frames", c.save_frames))
        # Пробный режим не запоминаем: включённый «навсегда», он выглядит как поломка
        self.dry_run = tk.BooleanVar(value=False)

        ttk.Label(card, text="Сколько забегов", style="Card.TLabel").grid(
            row=1, column=0, columnspan=4, sticky="w")
        ttk.Radiobutton(card, text="Пока есть стамина", value="all", variable=self.limit_mode,
                        style="Card.TRadiobutton").grid(row=2, column=0, columnspan=4,
                                                        sticky="w", pady=(4, 0))
        limit = ttk.Frame(card, style="Inner.TFrame")
        limit.grid(row=3, column=0, columnspan=4, sticky="w", pady=(2, 8))
        ttk.Radiobutton(limit, text="Не больше", value="limit", variable=self.limit_mode,
                        style="Card.TRadiobutton").grid(row=0, column=0)
        self.max_runs_box = ttk.Spinbox(limit, from_=1, to=999, width=5,
                                        textvariable=self.max_runs)
        self.max_runs_box.grid(row=0, column=1, padx=6)
        ttk.Label(limit, text="(забег = 5 боёв)", style="Muted.Card.TLabel").grid(
            row=0, column=2)

        ttk.Checkbutton(card, text="Закрыть игру при поражении", variable=self.exit_on_defeat,
                        style="Card.TCheckbutton").grid(row=4, column=0, columnspan=4, sticky="w")
        ttk.Checkbutton(card, text="Пробный режим (ничего не нажимать)",
                        variable=self.dry_run, style="Card.TCheckbutton").grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(4, 0))
        ttk.Checkbutton(card, text="Сохранять кадры (для отчёта об ошибке)",
                        variable=self.save_frames, style="Card.TCheckbutton").grid(
            row=6, column=0, columnspan=4, sticky="w", pady=(4, 0))

        for var in (self.limit_mode, self.max_runs, self.exit_on_defeat, self.save_frames):
            var.trace_add("write", lambda *_: self._save_settings())
        self.limit_mode.trace_add("write", lambda *_: self._sync_limit())
        self._sync_limit()
        self.settings_widgets = [w for w in card.winfo_children() + limit.winfo_children()
                                 if isinstance(w, (ttk.Radiobutton, ttk.Checkbutton,
                                                   ttk.Spinbox))]
        return card

    def _build_screen(self, parent) -> Card:
        card = Card(parent, "Экран телефона")
        card.columnconfigure(0, weight=1)
        # С картинкой размеры Label считаются в пикселях, без неё — в символах
        self.placeholder = tk.PhotoImage(width=PREVIEW_WIDTH,
                                         height=PREVIEW_WIDTH * 582 // 1280)
        self.preview = tk.Label(card, bg=INPUT, fg=MUTED, text="Нет картинки",
                                image=self.placeholder, compound="center", borderwidth=0)
        self.preview.grid(row=1, column=0, columnspan=4, sticky="w")
        self.screen_label = ttk.Label(card, text="Распознано: —", style="Muted.Card.TLabel")
        self.screen_label.grid(row=2, column=0, columnspan=4, sticky="w", pady=(6, 10))

        stats = ttk.Frame(card, style="Inner.TFrame")
        stats.grid(row=3, column=0, columnspan=4, sticky="ew")
        self.stat_runs = self._stat(stats, 0, "забегов")
        self.stat_depth = self._stat(stats, 1, "повышений глубины")
        self.stat_time = self._stat(stats, 2, "время работы")
        self.stat_runs.configure(text="0")
        self.stat_depth.configure(text="0")
        self.stat_time.configure(text="0:00")
        return card

    def _stat(self, parent, col: int, caption: str) -> ttk.Label:
        parent.columnconfigure(col, weight=1)
        value = ttk.Label(parent, text="—", style="Stat.TLabel")
        value.grid(row=0, column=col, sticky="w")
        ttk.Label(parent, text=caption, style="Muted.Card.TLabel").grid(
            row=1, column=col, sticky="w")
        return value

    def _build_log(self, parent) -> Card:
        card = Card(parent, "Журнал")
        card.rowconfigure(1, weight=1)
        card.columnconfigure(0, weight=1)
        ttk.Button(card, text="Открыть папку с логами", style="Link.TButton",
                   command=self.open_logs).grid(row=0, column=3, sticky="e")
        box = ttk.Frame(card, style="Inner.TFrame")
        box.grid(row=1, column=0, columnspan=4, sticky="nsew")
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        # ScrolledText взял бы светлую tk-полосу прокрутки, поэтому собираем сами
        self.log_text = tk.Text(box, height=9, wrap="word", state="disabled", relief="flat",
                                background=INPUT, foreground=TEXT, insertbackground=TEXT,
                                highlightthickness=0, font="TkFixedFont", borderwidth=0,
                                padx=8, pady=6)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)
        return card

    # --- журнал ---------------------------------------------------------

    def _setup_logging(self) -> None:
        root_log = logging.getLogger("btc_bot")
        root_log.setLevel(logging.INFO)
        root_log.handlers.clear()
        handler = QueueLogHandler(self.log_lines)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        root_log.addHandler(handler)

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 2000:
            self.log_text.delete("1.0", f"{lines - 2000}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # --- фоновая работа -------------------------------------------------

    def _bg(self, fn, done, fail=None) -> None:
        def work():
            try:
                result = fn()
            except Exception as e:  # noqa: BLE001 — любую ошибку показываем в окне
                self.events.put((fail or self._bg_failed, e))
            else:
                self.events.put((done, result))

        threading.Thread(target=work, daemon=True).start()

    def _bg_failed(self, error: Exception) -> None:
        log.error("Ошибка: %s", error)

    def _poll(self) -> None:
        try:
            while True:
                callback, value = self.events.get_nowait()
                callback(value)
        except queue.Empty:
            pass
        try:
            for _ in range(200):
                self._append_log(self.log_lines.get_nowait())
        except queue.Empty:
            pass
        if self.bot is not None:
            self._update_running()
        self.root.after(POLL_MS, self._poll)

    # --- проверка подключения -------------------------------------------

    def check_connection(self) -> None:
        if self.checking or self.bot is not None:
            return
        self.checking = True
        self.check_btn.configure(state="disabled", text="Проверяю…")
        self.status.configure(text="Проверяю телефон…")
        self._bg(self._probe, self._probe_done, self._probe_failed)

    def _probe(self) -> dict:
        info: dict = {"adb": find_adb(self.cfg.device.adb)}
        if not info["adb"]:
            return info
        probe = Device(adb=info["adb"], capture=self.cfg.device.capture)
        rows = probe.devices()
        ready = [serial for serial, state in rows if state == "device"]
        info["ready"] = ready
        serial = self.serial if self.serial in ready else None
        if serial is None and len(ready) == 1:
            serial = ready[0]
        if serial is None and len(ready) > 1:
            info["choose"] = True
            return info
        device = Device(serial=serial, adb=info["adb"], capture=self.cfg.device.capture)
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

    def _probe_done(self, info: dict) -> None:
        self.checking = False
        self.check_btn.configure(state="normal", text="Проверить")
        self.adb_path = info["adb"]
        self.phone_ready = False
        self.device_box.grid_remove()

        if not self.adb_path:
            self.row_adb.set(BAD, "не найден. Скачай его кнопкой ниже: это официальный "
                                  "набор Android platform-tools")
            self.row_phone.set(IDLE, "—")
            self.row_game.set(IDLE, "—")
            self.download_btn.grid()
            self.status.configure(text="Нужен adb: через него программа видит экран и нажимает")
            self._refresh_start()
            return
        self.download_btn.grid_remove()
        self.row_adb.set(OK, self.adb_path)

        ready = info.get("ready", [])
        if info.get("choose") or len(ready) > 1:
            self.device_box.configure(values=ready)
            self.device_box.grid()
        if info.get("choose"):
            self.row_phone.set(WARN, "подключено несколько устройств, выбери нужное")
            self.row_game.set(IDLE, "—")
            self.status.configure(text="Выбери телефон в списке")
            self._refresh_start()
            return
        if "phone_error" in info:
            self.row_phone.set(BAD, info["phone_error"])
            self.row_game.set(IDLE, "—")
            self.status.configure(text="Телефон не готов. Смотри подсказку и «Как подготовить "
                                       "телефон»")
            self._refresh_start()
            return

        self.serial = info["serial"]
        if len(ready) > 1:
            self.device_box.set(self.serial)
        self.phone_ready = True
        model = info.get("model") or ""
        self.row_phone.set(OK, f"{model} ({self.serial})" if model else self.serial)
        screen = info["screen"]
        self._show_frame(info["frame"], screen)
        if screen == "map_start":
            self.row_game.set(OK, SCREEN_NAMES[screen])
            self.status.configure(text="Всё готово. Нажми «Запустить»")
        else:
            self.row_game.set(WARN, f"{SCREEN_NAMES.get(screen, screen)}. Открой карту цепной "
                                    "кампании с кнопкой «Старт» и проверь ещё раз")
            self.status.configure(text="Телефон подключён. Открой карту цепной кампании")
        self._refresh_start()

    def _probe_failed(self, error: Exception) -> None:
        self.checking = False
        self.check_btn.configure(state="normal", text="Проверить")
        self.phone_ready = False
        self.row_phone.set(BAD, str(error))
        self.status.configure(text="Не получилось связаться с телефоном")
        self._refresh_start()

    def _on_device_selected(self, _event=None) -> None:
        self.serial = self.device_box.get() or None
        self.check_connection()

    # --- скачивание adb -------------------------------------------------

    def download_adb(self) -> None:
        self.download_btn.configure(state="disabled", text="Скачиваю…")

        def progress(got: int, total: int) -> None:
            self.events.put((self._download_progress, (got, total)))

        self._bg(lambda: download_platform_tools(progress), self._download_done,
                 self._download_failed)

    def _download_progress(self, value: tuple[int, int]) -> None:
        got, total = value
        text = f"Скачиваю… {got * 100 // total}%" if total else f"Скачиваю… {got // 1024} КБ"
        self.download_btn.configure(text=text)

    def _download_done(self, adb: str) -> None:
        self.download_btn.configure(state="normal", text="Скачать adb (≈7 МБ, сайт Google)")
        log.info("adb скачан: %s", adb)
        self.check_connection()

    def _download_failed(self, error: Exception) -> None:
        self.download_btn.configure(state="normal", text="Скачать adb (≈7 МБ, сайт Google)")
        log.error("Не удалось скачать adb: %s", error)
        messagebox.showerror("Не удалось скачать adb",
                             f"{error}\n\nМожно скачать вручную: developer.android.com/tools/"
                             f"releases/platform-tools и распаковать папку platform-tools "
                             f"рядом с программой ({DATA_DIR}).")

    # --- запуск и остановка ---------------------------------------------

    def _run_config(self) -> Config:
        cfg = copy.deepcopy(self.cfg)
        c = cfg.campaign
        c.max_runs = self._max_runs() if self.limit_mode.get() == "limit" else 0
        c.exit_game_on_defeat = self.exit_on_defeat.get()
        c.save_frames = self.save_frames.get()
        return cfg

    def _max_runs(self) -> int:
        try:
            return max(1, int(self.max_runs.get()))
        except (tk.TclError, ValueError):
            return 1

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
        dry_run = self.dry_run.get()
        bot = CampaignBot(device, self.classifier, cfg.campaign, session_dir=self.session,
                          dry_run=dry_run)
        self.bot = bot
        self.started_at = time.monotonic()
        self.last_stats = self.last_preview = 0.0

        def work() -> RunResult | None:
            bot.package = resolve_package(device, cfg.device.package)
            return bot.run()

        self._bg(work, self._finished, self._crashed)
        self.start_btn.configure(text="■  Остановить", style="Stop.TButton")
        self.check_btn.configure(state="disabled")
        for w in self.settings_widgets:
            w.configure(state="disabled")
        self.status.configure(text="Пробный режим: играй сам, бот только смотрит"
                              if dry_run else "Бот работает. Телефон лучше не трогать")

    def stop(self) -> None:
        if self.bot is None:
            return
        self.bot.request_stop()
        self.start_btn.configure(state="disabled", text="Останавливаю…")
        self.status.configure(text="Останавливаю после текущего шага…")

    def _update_running(self) -> None:
        bot = self.bot
        now = time.monotonic()
        if now - self.last_stats >= STATS_EVERY:
            self.last_stats = now
            self.stat_runs.configure(text=str(bot.runs_done))
            self.stat_depth.configure(text=str(bot.depth_ups))
            elapsed = int(now - self.started_at)
            h, rest = divmod(elapsed, 3600)
            self.stat_time.configure(text=f"{h}:{rest // 60:02d}:{rest % 60:02d}" if h
                                     else f"{rest // 60}:{rest % 60:02d}")
        if now - self.last_preview >= PREVIEW_EVERY and bot.last_raw is not None:
            self.last_preview = now
            self._show_frame(bot.last_raw, bot.screen)

    def _finished(self, result: RunResult) -> None:
        self._update_running_final()
        text = RESULT_TEXT.get(result.kind, result.kind)
        if result.kind not in ("done", "no_stamina", "stopped"):
            text += f": {result.reason}"
        if result.game_closed:
            text += ". Игра закрыта"
        self._reset_after_run(text)
        if result.kind != "stopped":
            self.root.bell()
            notify(f"BtC бот остановлен: {STOP_TITLES.get(result.kind, result.kind)}",
                   f"{result.reason}. Забегов: {result.runs_done}, глубина +{result.depth_ups}")

    def _crashed(self, error: Exception) -> None:
        log.error("Бот упал: %s", error)
        self._update_running_final()
        self._reset_after_run(f"Бот остановился из-за ошибки: {error}")
        self.root.bell()

    def _update_running_final(self) -> None:
        if self.bot is not None:
            self.last_stats = self.last_preview = 0.0
            self._update_running()

    def _reset_after_run(self, text: str) -> None:
        self.bot = None
        if self.file_handler is not None:
            logging.getLogger("btc_bot").removeHandler(self.file_handler)
            self.file_handler.close()
            self.file_handler = None
        self.start_btn.configure(text="▶  Запустить", style="Start.TButton")
        self.check_btn.configure(state="normal")
        for w in self.settings_widgets:
            w.configure(state="normal")
        self._sync_limit()
        self._refresh_start()
        self.status.configure(text=text)

    def _refresh_start(self) -> None:
        enabled = self.bot is None and self.phone_ready
        self.start_btn.configure(state="normal" if enabled else "disabled")

    # --- мелочи ---------------------------------------------------------

    def _show_frame(self, frame, screen: str | None) -> None:
        h, w = frame.shape[:2]
        size = (PREVIEW_WIDTH, max(1, round(h * PREVIEW_WIDTH / w)))
        small = imaging.resize(frame, *size)
        self.preview_image = tk.PhotoImage(data=base64.b64encode(imaging.encode(small, ".png")))
        self.preview.configure(image=self.preview_image, text="")
        name = SCREEN_NAMES.get(screen or "", screen or "—")
        self.screen_label.configure(text=f"Распознано: {name}")

    def _sync_limit(self) -> None:
        if self.bot is None:
            self.max_runs_box.configure(
                state="normal" if self.limit_mode.get() == "limit" else "disabled")

    def _save_settings(self) -> None:
        self.settings.update(
            limit_mode=self.limit_mode.get(),
            max_runs=self._max_runs(),
            exit_on_defeat=self.exit_on_defeat.get(),
            save_frames=self.save_frames.get(),
        )
        save_gui_settings(self.settings)

    def open_logs(self) -> None:
        path = self.session or session_dir(self.cfg.logs_dir).parent
        path.mkdir(parents=True, exist_ok=True)
        try:
            open_path(path)
        except OSError as e:
            messagebox.showinfo("Папка с логами", str(path) + f"\n\n{e}")

    def show_help(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Как подготовить телефон")
        win.configure(background=CARD)
        win.transient(self.root)
        _dark_title_bar(win)
        text = tk.Text(win, wrap="word", width=78, height=30, relief="flat", padx=18,
                       pady=14, background=CARD, foreground=TEXT, borderwidth=0)
        text.insert("1.0", HELP_TEXT)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)
        ttk.Button(win, text="Понятно", command=win.destroy).pack(pady=(0, 14))

    def _first_launch(self) -> None:
        if not self.settings.get("accepted_risk"):
            if not messagebox.askokcancel("Перед началом", RISK_TEXT, icon="warning",
                                          parent=self.root):
                self.root.destroy()
                return
            self.settings["accepted_risk"] = True
            save_gui_settings(self.settings)
        self.check_connection()

    def on_close(self) -> None:
        if self.bot is not None:
            if not messagebox.askyesno("Бот работает",
                                       "Бот ещё работает. Остановить его и закрыть программу?"):
                return
            self.bot.request_stop()
        self.root.destroy()


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def _dark_title_bar(window: tk.Misc) -> None:
    """Тёмный заголовок окна в Windows 10/11 (DWMWA_USE_IMMERSIVE_DARK_MODE)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value),
                                                   ctypes.sizeof(value))
    except (AttributeError, OSError):
        pass


def main(config_path: str | Path | None = None) -> int:
    _enable_dpi_awareness()
    root = tk.Tk()
    _setup_style(root)
    _dark_title_bar(root)
    try:
        cfg = load_config(config_path or CONFIG_PATH)
        App(root, cfg)
    except Exception as e:  # noqa: BLE001 — без окна ошибку иначе не увидеть
        messagebox.showerror("Не удалось запустить", str(e))
        root.destroy()
        return 1
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
