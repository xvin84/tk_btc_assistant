"""Уведомление об остановке бота: в шторку Android (Termux:API) или на рабочий стол."""

from __future__ import annotations

import logging
import shutil
import subprocess

log = logging.getLogger("btc_bot")


def notify(title: str, text: str) -> bool:
    """Показывает уведомление, если есть чем. Возвращает True, если получилось."""
    if shutil.which("termux-notification"):
        cmd = ["termux-notification", "--id", "btc-bot", "--title", title, "--content", text]
    elif shutil.which("notify-send"):
        cmd = ["notify-send", "--app-name=btc-bot", title, text]
    else:
        return False
    try:
        subprocess.run(cmd, capture_output=True, timeout=15, check=True)
        return True
    except (OSError, subprocess.SubprocessError) as e:
        log.debug("Уведомление не отправилось: %s", e)
        return False
