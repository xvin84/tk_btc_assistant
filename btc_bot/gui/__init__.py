"""Окно программы (PySide6)."""

from __future__ import annotations

import sys
from pathlib import Path


def main(config_path: str | Path | None = None) -> int:
    from PySide6.QtCore import QLibraryInfo, QTimer, QTranslator
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ..config import load_config
    from ..paths import CONFIG_PATH
    from .theme import apply_theme
    from .window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("BtcAssistant")
    # Русские подписи стандартных кнопок («Да», «Отмена») в диалогах Qt
    translator = QTranslator(app)
    if translator.load("qtbase_ru", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        app.installTranslator(translator)
    apply_theme(app)
    try:
        cfg = load_config(config_path or CONFIG_PATH)
        window = MainWindow(cfg)
    except Exception as e:  # noqa: BLE001 — без окна ошибку иначе не увидеть
        QMessageBox.critical(None, "Не удалось запустить", str(e))
        return 1
    window.show()

    def first_launch() -> None:
        if not window.first_launch():
            window.close()

    QTimer.singleShot(200, first_launch)
    return app.exec()
