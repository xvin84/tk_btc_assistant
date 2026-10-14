"""Точка входа собранной программы (PyInstaller)."""

import sys


def self_test() -> int:
    """Проверка сборки в CI: шаблоны и Tk на месте, окно не открываем."""
    import tkinter  # noqa: F401

    from btc_bot.screens import Classifier
    from btc_bot.vision import TemplateLibrary

    lib = TemplateLibrary.load()
    Classifier(lib)
    return 0 if len(lib.templates) >= 10 else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    from btc_bot.gui import main

    sys.exit(main())
