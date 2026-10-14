"""Каждая строка интерфейса переведена на английский."""

import ast
import string

import pytest

from btc_bot import i18n
from btc_bot.adb import STATE_HINTS
from btc_bot.cli import STOP_TITLES
from btc_bot.locales import en
from conftest import ROOT

# Словари уровня модуля переводятся при показе: tr(SCREEN_NAMES[...]) и т.п.
DICT_SOURCES = {
    "btc_bot/gui/window.py": ("SCREEN_NAMES", "RESULT_STATE", "RISK_TEXT", "HELP_TEXT"),
}


def tr_keys() -> set[str]:
    keys: set[str] = set()
    for path in sorted((ROOT / "btc_bot").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "tr" and node.args
                    and isinstance(node.args[0], ast.Constant)):
                keys.add(node.args[0].value)
    return keys


def gui_constants() -> set[str]:
    from btc_bot.gui import window

    keys = set(window.SCREEN_NAMES.values())
    keys |= {label for label, _ in window.RESULT_STATE.values()}
    keys |= {window.RISK_TEXT, window.HELP_TEXT}
    keys |= set(STOP_TITLES.values()) | set(STATE_HINTS.values())
    keys.add("проверь подключение и `adb devices`.")
    return keys


def all_keys() -> set[str]:
    keys = tr_keys()
    try:
        keys |= gui_constants()
    except ImportError:  # без PySide6 проверяем только tr("...")
        pass
    return keys


def test_every_key_is_translated():
    missing = sorted(k for k in all_keys() if k not in en.CATALOG)
    assert not missing, "нет перевода:\n" + "\n".join(missing)


def test_no_stale_translations():
    stale = sorted(k for k in en.CATALOG if k not in all_keys())
    assert not stale, "перевод для строки, которой нет в коде:\n" + "\n".join(stale)


@pytest.mark.parametrize("key", sorted(en.CATALOG))
def test_placeholders_match(key):
    fields = lambda s: sorted(f for _, f, _, _ in string.Formatter().parse(s) if f)  # noqa: E731
    percent = lambda s: sorted(c for c in ("%s", "%d") for _ in range(s.count(c)))  # noqa: E731
    value = en.CATALOG[key]
    assert fields(key) == fields(value)
    assert percent(key) == percent(value)


def test_language_switch():
    i18n.set_language("en")
    try:
        assert i18n.tr("Проверить") == en.CATALOG["Проверить"]
        assert i18n.tr("строка без перевода") == "строка без перевода"
    finally:
        i18n.set_language("ru")
    assert i18n.tr("Проверить") == "Проверить"
