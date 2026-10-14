"""Окно без экрана (offscreen): проверка телефона, забег, остановка."""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from btc_bot.campaign import Clock  # noqa: E402
from btc_bot.config import Config  # noqa: E402
from btc_bot.gui import window as W  # noqa: E402
from btc_bot.gui.theme import apply_theme  # noqa: E402

from conftest import FakeDevice, Scene, sample  # noqa: E402
from test_campaign import full_run_scenes  # noqa: E402


class FastClock(Clock):
    """Сцены подставного телефона сменяются в 10 раз быстрее реального времени."""

    def now(self) -> float:
        return super().now() * 10


@pytest.fixture(scope="module")
def app():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    apply_theme(app)
    return app


@pytest.fixture
def make_window(app, monkeypatch, tmp_path):
    monkeypatch.setattr(W, "load_gui_settings", lambda: {"accepted_risk": True})
    monkeypatch.setattr(W, "save_gui_settings", lambda data: None)
    monkeypatch.setattr(W, "resolve_package", lambda device, configured: "com.funcat.tgbtc")
    windows = []

    def make(scenes=None, start="map", probe=None):
        if scenes is not None:
            monkeypatch.setattr(W, "Device", lambda serial=None, adb=None, capture="png":
                                FakeDevice(scenes, start, FastClock()))
        cfg = Config()
        cfg.logs_dir = str(tmp_path / "logs")
        cfg.campaign.poll_interval = 0.05
        cfg.campaign.overlay_tap_delay = 0.1
        cfg.campaign.tap_cooldown = 0.3
        win = W.MainWindow(cfg)
        if probe is not None:
            monkeypatch.setattr(W.MainWindow, "_probe", lambda self: probe)
        windows.append(win)
        return win

    yield make
    for win in windows:
        if win.bot is not None:
            win.bot.request_stop()
        win.close()


def wait(app, condition, timeout=20.0):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "не дождались"
        app.processEvents()
        time.sleep(0.02)


def ready_probe():
    return {"adb": "adb", "ready": ["X"], "serial": "X", "model": "Fake",
            "frame": sample("map_start"), "screen": "map_start"}


def test_missing_adb_offers_download(app, make_window):
    win = make_window(probe={"adb": None})
    win.check_connection()
    wait(app, lambda: not win.checking)

    assert not win.download_btn.isHidden()
    assert not win.start_btn.isEnabled()


def test_ready_phone_enables_start(app, make_window):
    win = make_window(probe=ready_probe())
    win.check_connection()
    wait(app, lambda: not win.checking)

    assert win.phone_ready
    assert win.start_btn.isEnabled()
    assert win.hero_state.text() == "Готов к запуску"


def test_full_run_until_limit(app, make_window):
    win = make_window(full_run_scenes(battle_start="battle"), probe=ready_probe())
    win.check_connection()
    wait(app, lambda: win.phone_ready)
    win.radio_limit.setChecked(True)
    win.max_runs.setValue(1)
    win.start()
    assert not win.radio_all.isEnabled()  # настройки заперты на время работы
    wait(app, lambda: win.bot is None, timeout=60)

    assert win.hero_state.text() == "Готово"
    assert win.stat_runs.text() == "1"
    assert win.stat_depth.text() == "1"
    assert win.radio_all.isEnabled()
    assert "лимит достигнут" in win.log_view.toPlainText()


def test_stop_button_stops_bot(app, make_window):
    scenes = {"battle": Scene(sample("battle_deal"))}
    win = make_window(scenes, start="battle", probe=ready_probe())
    win.check_connection()
    wait(app, lambda: win.phone_ready)
    win.start()
    wait(app, lambda: win.bot is not None and win.bot.screen == "battle")
    win.toggle_run()
    wait(app, lambda: win.bot is None)

    assert win.hero_state.text() == "Остановлено"
    assert win.start_btn.text().endswith("Запустить")
