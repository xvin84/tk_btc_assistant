"""Локализация: перевод строк-исходников на активный язык.

Исходный язык — русский: ключами перевода служат сами русские строки из кода
(`tr("Запустить")`). Язык — это каталог `{русская строка: перевод}`;
отсутствующий ключ откатывается к русскому исходнику. Строки с подстановками
переводятся до подстановки: `tr("Забегов: {runs}").format(runs=3)`, а в логе
`log.info(tr("Экран: %s"), screen)`.

Модуль не зависит от Qt: бот и командная строка пользуются им напрямую.
"""

from __future__ import annotations

SOURCE_LANGUAGE = ("ru", "Русский")

_names: dict[str, str] = {SOURCE_LANGUAGE[0]: SOURCE_LANGUAGE[1]}
_catalogs: dict[str, dict[str, str]] = {}
_language = SOURCE_LANGUAGE[0]


def register_language(code: str, name: str, mapping: dict[str, str]) -> None:
    """Добавить или дополнить язык. Русский исходник переопределять нельзя."""
    if code == SOURCE_LANGUAGE[0]:
        return
    _names[code] = name
    _catalogs.setdefault(code, {}).update(mapping)


def set_language(code: str) -> None:
    global _language
    _language = code if code in _names else SOURCE_LANGUAGE[0]


def current_language() -> str:
    return _language


def available_languages() -> list[tuple[str, str]]:
    """Список (код, название): русский первым, остальные по алфавиту."""
    extras = sorted((c for c in _names if c != SOURCE_LANGUAGE[0]),
                    key=lambda c: _names[c].lower())
    return [SOURCE_LANGUAGE] + [(c, _names[c]) for c in extras]


def tr(text: str) -> str:
    if _language == SOURCE_LANGUAGE[0]:
        return text
    return _catalogs.get(_language, {}).get(text, text)


def _load_builtin() -> None:
    from .locales import en

    register_language(en.CODE, en.NAME, en.CATALOG)


_load_builtin()
