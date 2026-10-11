import pytest

from btc_bot.config import load_config


def test_defaults_without_file(tmp_path):
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.campaign.max_runs == 0
    assert cfg.campaign.exit_game_on_defeat is True


def test_overrides(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('[device]\npackage = "com.funcat.tgbtc"\n'
                    "[campaign]\nmax_runs = 5\npoll_interval = 2\n", encoding="utf-8")
    cfg = load_config(path)
    assert cfg.device.package == "com.funcat.tgbtc"
    assert cfg.campaign.max_runs == 5
    assert cfg.campaign.poll_interval == 2.0


def test_unknown_key_is_an_error(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[campaign]\nmax_run = 5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="max_run"):
        load_config(path)


def test_example_config_is_valid():
    from conftest import ROOT

    load_config(ROOT / "config.example.toml")
