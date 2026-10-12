import pytest

from btc_bot import imaging
from btc_bot import screens as S
from btc_bot.vision import normalize

from conftest import as_device_frame, sample

EXPECTED = {
    "map_start": S.MAP_START,
    "team_setup": S.TEAM_SETUP,
    "loading_1": S.LOADING,
    "loading_2": S.LOADING,
    "versus": S.UNKNOWN,  # заставка «команда против команды»: просто ждём
    "battle_deal": S.BATTLE,
    "battle_manual": S.BATTLE,
    "battle_attack": S.BATTLE,
    "battle_won_interim": S.BATTLE_WON,
    "victory": S.VICTORY,
    "chain_reaction": S.CHAIN_REACTION,
    "map_claim_all": S.MAP_CLAIM_ALL,
    "level_cleared": S.LEVEL_CLEARED,
    "rewards_popup": S.REWARDS_POPUP,
    "depth_up": S.DEPTH_UP,
}


@pytest.mark.parametrize("name,expected", sorted(EXPECTED.items()))
def test_samples_classified(classifier, name, expected):
    frame, _ = normalize(sample(name))
    assert classifier.classify(frame).screen == expected


@pytest.mark.parametrize("name,expected", sorted(EXPECTED.items()))
def test_full_resolution_frames_classified(classifier, name, expected):
    # Живой экран телефона 2780x1264 приводится к той же рабочей ширине
    frame, scale = normalize(as_device_frame(sample(name)))
    assert frame.shape[1] == 1280
    assert scale == pytest.approx(2780 / 1280)
    assert classifier.classify(frame).screen == expected


@pytest.mark.parametrize("name,expected", [
    ("battle_deal", True),
    ("battle_attack", True),
    ("battle_manual", False),
])
def test_auto_button_state(classifier, name, expected):
    frame, _ = normalize(sample(name))
    state, match = classifier.auto_state(frame)
    assert state is expected
    x, y = match.center
    assert 215 <= x <= 285 and 30 <= y <= 64


def test_dimmed_map_buttons_are_not_pressable(classifier):
    # Под чужим всплывающим окном карта затемнена: «Старт» нажимать нельзя
    frame, _ = normalize(sample("map_start"))
    dimmed = imaging.scale_brightness(frame, 0.45)
    assert classifier.classify(dimmed).screen == S.UNKNOWN
