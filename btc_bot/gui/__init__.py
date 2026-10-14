"""Окно программы (PySide6)."""

from __future__ import annotations

import sys
from pathlib import Path


def main(config_path: str | Path | None = None) -> int:
    from PySide6.QtCore import QLibraryInfo, QLocale, QTimer, QTranslator
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ..config import load_config
    from ..i18n import available_languages, set_language
    from ..paths import CONFIG_PATH
    from .theme import apply_theme
    from .window import MainWindow, load_gui_settings

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("BtcAssistant")
    apply_theme(app)

    # Подписи стандартных кнопок диалогов Qt («Да», «Отмена») для русского языка
    qt_translator = QTranslator(app)
    qt_ru = qt_translator.load(
        "qtbase_ru", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))

    def apply_language(code: str) -> None:
        set_language(code)
        app.removeTranslator(qt_translator)
        if code == "ru" and qt_ru:
            app.installTranslator(qt_translator)

    known = {code for code, _ in available_languages()}
    system = QLocale.system().name().split("_")[0]
    apply_language(load_gui_settings().get("language")
                   or (system if system in known else "en"))

    try:
        cfg = load_config(config_path or CONFIG_PATH)
    except Exception as e:  # noqa: BLE001 — без окна ошибку иначе не увидеть
        QMessageBox.critical(None, "BtcAssistant", str(e))
        return 1

    windows: list[MainWindow] = []

    def open_window(previous: MainWindow | None = None) -> MainWindow:
        window = MainWindow(cfg)
        window.language_changed.connect(lambda code: switch_language(window, code))
        if previous is not None:
            window.setGeometry(previous.geometry())
            window.nav.setCurrentRow(previous.nav.currentRow())
        window.show()
        windows.append(window)
        return window

    def switch_language(old: MainWindow, code: str) -> None:
        apply_language(code)
        new = open_window(old)
        old.close()
        windows.remove(old)
        new.check_connection()

    window = open_window()

    def first_launch() -> None:
        if not window.first_launch():
            window.close()

    QTimer.singleShot(200, first_launch)
    return app.exec()
