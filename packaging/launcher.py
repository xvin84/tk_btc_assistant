"""Точка входа собранной программы (PyInstaller)."""

import os
import sys


def self_test() -> int:
    """Проверка сборки в CI: Qt, шаблоны и окно собираются без показа на экране."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from btc_bot.config import Config
    from btc_bot.gui.theme import apply_theme
    from btc_bot.gui.window import MainWindow

    app = QApplication([])
    apply_theme(app)
    window = MainWindow(Config())
    return 0 if len(window.classifier.lib.templates) >= 10 else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    from btc_bot.gui import main

    sys.exit(main())
