"""Поиск adb и скачивание Android platform-tools с сайта Google."""

from __future__ import annotations

import io
import os
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from .i18n import tr
from .paths import DATA_DIR

PLATFORM_TOOLS_DIR = DATA_DIR / "platform-tools"
DOWNLOAD_URL = "https://dl.google.com/android/repository/platform-tools-latest-{os}.zip"
# Программа, запущенная из Finder или ярлыка, получает урезанный PATH: смотрим
# туда, куда adb ставят Homebrew и Android Studio
KNOWN_LOCATIONS = (
    Path("/opt/homebrew/bin/adb"),
    Path("/usr/local/bin/adb"),
    Path.home() / "Library" / "Android" / "sdk" / "platform-tools" / "adb",
    Path.home() / "Android" / "Sdk" / "platform-tools" / "adb",
)


def adb_name() -> str:
    return "adb.exe" if sys.platform == "win32" else "adb"


def find_adb(configured: str = "adb") -> str | None:
    """Путь к adb: из настроек, из PATH или скачанный рядом с программой."""
    if configured and configured != "adb":
        return configured if Path(configured).exists() else None
    found = shutil.which("adb")
    if found:
        return found
    for candidate in (PLATFORM_TOOLS_DIR / adb_name(), *KNOWN_LOCATIONS):
        if candidate.exists():
            return str(candidate)
    return None


def download_os() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def download_platform_tools(progress: Callable[[int, int], None] | None = None) -> str:
    """Скачивает platform-tools в папку программы и возвращает путь к adb.

    progress(получено, всего) вызывается по мере загрузки; всего = 0,
    если сервер не сообщил размер.
    """
    url = DOWNLOAD_URL.format(os=download_os())
    with urllib.request.urlopen(url, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        buf = io.BytesIO()
        while chunk := resp.read(64 * 1024):
            buf.write(chunk)
            if progress:
                progress(buf.tell(), total)
    # В архиве всё лежит в папке platform-tools/
    with zipfile.ZipFile(buf) as zf:
        zf.extractall(PLATFORM_TOOLS_DIR.parent)
    adb = PLATFORM_TOOLS_DIR / adb_name()
    if not adb.exists():
        raise RuntimeError(tr("В архиве {url} не нашлось {name}").format(url=url, name=adb_name()))
    if sys.platform != "win32":
        for name in ("adb", "fastboot"):
            path = PLATFORM_TOOLS_DIR / name
            if path.exists():
                os.chmod(path, 0o755)
    return str(adb)
