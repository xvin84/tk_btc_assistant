"""Где лежат файлы программы и файлы пользователя.

Из исходников всё лежит в корне проекта. В собранной программе (PyInstaller)
шаблоны распакованы внутрь сборки, а настройки, логи и скачанный adb лежат
рядом с программой, чтобы их было легко найти. Исключения — macOS (внутрь
.app писать нельзя) и папка программы без права записи: тогда файлы
пользователя уходят в его папку данных.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
APP_NAME = "BtcAssistant"


def user_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / APP_NAME
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / APP_NAME


def _frozen_data_dir() -> Path:
    exe_dir = Path(sys.executable).resolve().parent
    if sys.platform != "darwin" and os.access(exe_dir, os.W_OK):
        return exe_dir
    data = user_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    return data


if FROZEN:
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    DATA_DIR = _frozen_data_dir()
else:
    BUNDLE_DIR = DATA_DIR = Path(__file__).resolve().parent.parent

TEMPLATES_DIR = BUNDLE_DIR / "templates"
CONFIG_PATH = DATA_DIR / "config.toml"
