import cv2

from btc_bot.campaign import CampaignBot
from btc_bot.config import CampaignConfig

from conftest import FakeClock, FakeDevice, Scene, sample

PACKAGE = "com.funcat.tgbtc"


def full_run_scenes(battle_start: str = "battle_manual") -> dict[str, Scene]:
    """Один забег из двух боёв, сбор наград и повышение глубины."""
    return {
        "map": Scene(sample("map_start"), tap_box=(1012, 492, 1100, 538), on_tap="setup"),
        "setup": Scene(sample("team_setup"), tap_box=(980, 440, 1090, 545), on_tap="loading"),
        "loading": Scene(sample("loading_1"), after=2, then="versus"),
        "versus": Scene(sample("versus"), after=3, then=battle_start),
        # Автобой выключен: бот должен нажать «АВТО»
        "battle_manual": Scene(sample("battle_manual"), tap_box=(215, 30, 285, 64),
                               on_tap="battle"),
        "battle": Scene(sample("battle_deal"), after=6, then="attack"),
        "attack": Scene(sample("battle_attack"), after=4, then="won"),
        "won": Scene(sample("battle_won_interim"), after=4, then="battle2"),
        "battle2": Scene(sample("battle_deal"), after=8, then="victory"),
        "victory": Scene(sample("victory"), tap_box=(0, 0, 1280, 582), on_tap="loading2"),
        "loading2": Scene(sample("loading_2"), after=2, then="chain"),
        "chain": Scene(sample("chain_reaction"), after=2, then="claim"),
        "claim": Scene(sample("map_claim_all"), tap_box=(905, 495, 1150, 532),
                       on_tap="rewards"),
        "rewards": Scene(sample("rewards_popup"), tap_box=(0, 0, 1280, 582),
                         on_tap="cleared"),
        "cleared": Scene(sample("level_cleared"), after=3, then="depth"),
        # баннер закрывается нажатием в нижней пятой части экрана
        "depth": Scene(sample("depth_up"), tap_box=(0, 466, 1280, 582), on_tap="map2"),
        "map2": Scene(sample("map_start"), tap_box=(1012, 492, 1100, 538), on_tap="setup"),
    }


def make_bot(device, clock, **cfg):
    from btc_bot.vision import TemplateLibrary
    from btc_bot.screens import Classifier

    config = CampaignConfig(**cfg)
    return CampaignBot(device, Classifier(TemplateLibrary.load()), config, package=PACKAGE,
                       clock=clock)


def test_full_run_until_limit():
    clock = FakeClock()
    device = FakeDevice(full_run_scenes(), "map", clock)
    result = make_bot(device, clock, max_runs=1).run()

    assert result.kind == "done"
    assert result.runs_done == 1
    assert result.depth_ups == 1
    assert device.misses == []
    assert device.stopped == []
    # Бот дошёл до новой карты и там остановился по лимиту
    assert device.current == "map2"
    pressed = [scene for scene, _, _ in device.taps]
    assert pressed.count("battle_manual") == 1  # «АВТО» включён один раз
    assert "battle" not in pressed  # включённый «АВТО» не трогаем


def test_second_run_starts_after_depth_up():
    clock = FakeClock()
    device = FakeDevice(full_run_scenes(battle_start="battle"), "map", clock)
    result = make_bot(device, clock, max_runs=2).run()

    assert result.kind == "done"
    assert result.runs_done == 2
    assert device.history.count("setup") == 2
    assert device.misses == []


def test_defeat_closes_game():
    clock = FakeClock()
    lost = sample("victory").copy()
    lost[95:165, 70:320] = (20, 10, 60)  # вместо «ПОБЕДА» другой заголовок
    scenes = full_run_scenes(battle_start="battle")
    scenes["attack"] = Scene(sample("battle_attack"), after=4, then="lost")
    scenes["lost"] = Scene(lost)
    device = FakeDevice(scenes, "map", clock)
    result = make_bot(device, clock).run()

    assert result.kind == "defeat"
    assert result.exit_code == 2
    assert result.game_closed
    assert device.stopped == [PACKAGE]
    assert all(scene != "lost" for scene, _, _ in device.taps)


def test_defeat_does_not_close_game_when_disabled():
    clock = FakeClock()
    lost = sample("victory").copy()
    lost[95:165, 70:320] = (20, 10, 60)
    scenes = {"lost": Scene(lost)}
    device = FakeDevice(scenes, "lost", clock)
    result = make_bot(device, clock, exit_game_on_defeat=False).run()

    assert result.kind == "defeat"
    assert device.stopped == []


def test_no_stamina_stops_without_extra_taps():
    clock = FakeClock()
    popup = cv2.convertScaleAbs(sample("map_start"), alpha=0.45)  # окно поверх карты
    scenes = {
        "map": Scene(sample("map_start"), tap_box=(1012, 492, 1100, 538), on_tap="popup"),
        "popup": Scene(popup),
    }
    device = FakeDevice(scenes, "map", clock)
    result = make_bot(device, clock).run()

    assert result.kind == "no_stamina"
    assert len(device.taps) == 1
    assert device.stopped == []


def test_auto_that_never_turns_on_stops_bot():
    clock = FakeClock()
    scenes = {"battle": Scene(sample("battle_manual"), tap_box=(215, 30, 285, 64))}
    device = FakeDevice(scenes, "battle", clock)
    result = make_bot(device, clock, max_auto_taps=3).run()

    assert result.kind == "error"
    assert len(device.taps) == 3
    assert device.stopped == []


def test_dry_run_never_taps_and_waits_for_player():
    clock = FakeClock()
    scenes = {"map": Scene(sample("map_start"), tap_box=(1012, 492, 1100, 538))}
    device = FakeDevice(scenes, "map", clock)
    bot = make_bot(device, clock, state_timeout=30, start_timeout=10)
    bot.dry_run = True
    for _ in range(120):  # две минуты на карте: человек не торопится
        assert bot.step().screen == "map_start"
        clock.sleep(1)

    assert device.taps == []


def test_adb_glitch_is_retried_and_persistent_failure_stops():
    from btc_bot.adb import AdbError

    clock = FakeClock()
    scenes = {"battle": Scene(sample("battle_deal"))}
    device = FakeDevice(scenes, "battle", clock)
    real_screenshot = device.screenshot
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 2 or calls["n"] > 5:
            raise AdbError("device offline")
        return real_screenshot()

    device.screenshot = flaky
    result = make_bot(device, clock).run()

    assert result.kind == "error"
    assert "ADB" in result.reason
    assert calls["n"] == 10  # разовый сбой пережили, пять подряд — стоп
