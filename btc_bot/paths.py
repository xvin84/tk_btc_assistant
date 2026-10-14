"""Где лежат файлы программы и файлы пользователя.

Из исходников всё лежит в корне проекта. В собранной программе (PyInstaller)
шаблоны распакованы внутрь сборки, а настройки, логи и скачанный adb лежат
рядом с exe, чтобы их было легко найти.
"""

from __future__ import annotations

import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))

if FROZEN:
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    DATA_DIR = Path(sys.executable).resolve().parent
else:
    BUNDLE_DIR = DATA_DIR = Path(__file__).resolve().parent.parent

TEMPLATES_DIR = BUNDLE_DIR / "templates"
CONFIG_PATH = DATA_DIR / "config.toml"
