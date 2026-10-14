#!/usr/bin/env python3
"""Собирает тело GitHub-релиза: «что нового» + описание + возможности, EN → RU.

Источник «что нового» — секция текущей версии из CHANGELOG.en.md / CHANGELOG.md.
Описание и список возможностей — краткая выжимка ниже (полный список — в README).
Запуск: python scripts/release_notes.py [версия] > RELEASE_NOTES.md
Без аргумента версия берётся из pyproject.toml.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "https://github.com/xvin84/tk_btc_assistant"

BETA_EN = (
    "> ⚠️ **Beta.** The app is pre-1.0 — a few rough edges are expected. "
    f"Please report bugs and ideas in the [issues]({REPO}/issues)."
)
BETA_RU = (
    "> ⚠️ **Бета-версия.** Программа ещё до 1.0 — возможны шероховатости. "
    f"Пишите об ошибках и идеях в [issues]({REPO}/issues)."
)

ABOUT_EN = (
    "An auto-runner for the **Chain Campaign** in *Tokyo Ghoul: Break the Chains* "
    "on an Android phone: the game's auto-battle fights, and the app moves from "
    "battle to battle over ADB — starts runs, keeps AUTO on, collects rewards and "
    "stops on defeat or when stamina runs out."
)
ABOUT_RU = (
    "Автопрохождение **цепной кампании** в *Tokyo Ghoul: Break the Chains* на "
    "Android-телефоне: бои ведёт автобой игры, а программа через ADB переходит от "
    "боя к бою — запускает забеги, следит за «АВТО», собирает награды и "
    "останавливается при поражении или нехватке стамины."
)

FEATURES_EN = [
    "**Screen recognition** by caption and button templates; dimmed buttons "
    "under pop-ups are never tapped.",
    "**Safe stops**: defeat (optionally closing the game), out of stamina, an "
    "unfamiliar screen — with a frame for the bug report.",
    "**Qt window**: phone check, live screen preview, counters, log, dry run, "
    "one-click adb download; Russian and English interface.",
    "**Command line** and an experimental **Termux** mode right on the phone.",
]
FEATURES_RU = [
    "**Распознавание экранов** по шаблонам надписей и кнопок; затемнённые кнопки "
    "под всплывающими окнами не нажимаются.",
    "**Безопасные остановки**: поражение (с закрытием игры по желанию), нехватка "
    "стамины, незнакомый экран — с кадром для отчёта.",
    "**Окно на Qt**: проверка телефона, живое превью экрана, счётчики, журнал, "
    "пробный режим, скачивание adb одной кнопкой; русский и английский интерфейс.",
    "**Командная строка** и экспериментальный режим **Termux** прямо на телефоне.",
]

DOWNLOAD_EN = (
    "**Download:** Windows — `BtcAssistant-<version>-windows.zip` (unzip, run "
    "`BtcAssistant.exe`); Linux — `…-linux-x86_64.tar.gz` (unpack, run "
    "`BtcAssistant/BtcAssistant`); macOS on Apple Silicon — `…-macos-arm64.zip` "
    "(the app is not signed: right-click → Open the first time). The game must be "
    "in Russian."
)
DOWNLOAD_RU = (
    "**Скачать:** Windows — `BtcAssistant-<версия>-windows.zip` (распаковать, "
    "запустить `BtcAssistant.exe`); Linux — `…-linux-x86_64.tar.gz` (распаковать, "
    "запустить `BtcAssistant/BtcAssistant`); macOS на Apple Silicon — "
    "`…-macos-arm64.zip` (программа не подписана: в первый раз правый клик → "
    "«Открыть»). Игра должна быть на русском языке."
)


def project_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def changelog_section(path: Path, version: str) -> str:
    """Содержимое блока `## [version] — дата` до следующего `## ` (без заголовка)."""
    text = path.read_text(encoding="utf-8")
    pat = re.compile(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pat.search(text)
    return m.group(1).strip() if m else "_(нет записи в журнале изменений)_"


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items)


def build(version: str) -> str:
    tag = f"v{version}"
    return "\n".join([
        BETA_EN,
        "",
        "## 🇬🇧 English",
        "",
        f"### What's new in {tag}",
        changelog_section(ROOT / "CHANGELOG.en.md", version),
        "",
        "### What is it",
        ABOUT_EN,
        "",
        "### Key features",
        _bullets(FEATURES_EN),
        "",
        f"_Full feature list and docs — see the [README]({REPO}#readme)._",
        "",
        DOWNLOAD_EN,
        "",
        "---",
        "",
        BETA_RU,
        "",
        "## 🇷🇺 Русский",
        "",
        f"### Что нового в {tag}",
        changelog_section(ROOT / "CHANGELOG.md", version),
        "",
        "### Что это",
        ABOUT_RU,
        "",
        "### Основные возможности",
        _bullets(FEATURES_RU),
        "",
        f"_Полный список возможностей и документация — в "
        f"[README]({REPO}/blob/main/README.ru.md)._",
        "",
        DOWNLOAD_RU,
        "",
    ])


def main(argv: list[str]) -> int:
    version = argv[1] if len(argv) > 1 else project_version()
    # На Windows stdout по умолчанию не в UTF-8, а в тексте кириллица и эмодзи
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(build(version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
