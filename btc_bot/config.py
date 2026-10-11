"""Настройки бота. Значения по умолчанию здесь, переопределения в config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path


@dataclass
class DeviceConfig:
    adb: str = "adb"
    serial: str = ""  # пусто = единственное подключённое устройство
    package: str = ""  # пусто = взять приложение, открытое при запуске бота


@dataclass
class CampaignConfig:
    max_runs: int = 0  # сколько забегов (по 5 боёв) пройти; 0 = без ограничения
    poll_interval: float = 1.0  # пауза между скриншотами, с
    tap_cooldown: float = 4.0  # не жать одну и ту же кнопку чаще, с
    max_start_taps: int = 3  # нажатий «Старт» без перехода, после которых стоп (нет стамины?)
    start_timeout: float = 20.0  # сколько ждать расстановку после «Старт», с
    manage_auto: bool = True  # включать «АВТО», если он выключен
    auto_off_frames: int = 2  # сколько кадров подряд «АВТО» должен быть выключен
    max_auto_taps: int = 4  # попыток включить «АВТО» за один забег
    defeat_confirm: float = 8.0  # сколько секунд экран итогов без «ПОБЕДА» = поражение
    overlay_tap_delay: float = 1.5  # ждать перед нажатием на баннер/окно, с
    # Куда нажимать на баннере «Повышение глубины»: доли ширины и высоты экрана
    depth_up_tap_x: float = 0.5
    depth_up_tap_y: float = 0.85
    unknown_timeout: float = 90.0  # неизвестный экран дольше этого = стоп
    state_timeout: float = 180.0  # один и тот же экран (кроме боя) дольше этого = стоп
    battle_timeout: float = 900.0  # бой дольше этого = стоп
    exit_game_on_defeat: bool = True
    exit_game_on_error: bool = False
    save_frames: bool = False  # сохранять кадр при каждой смене экрана


@dataclass
class Config:
    device: DeviceConfig = field(default_factory=DeviceConfig)
    campaign: CampaignConfig = field(default_factory=CampaignConfig)
    logs_dir: str = "logs"


def load_config(path: str | Path | None) -> Config:
    cfg = Config()
    if path is None:
        return cfg
    path = Path(path)
    if not path.exists():
        return cfg
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    _apply(cfg.device, data.get("device", {}), "device")
    _apply(cfg.campaign, data.get("campaign", {}), "campaign")
    if "logs_dir" in data:
        cfg.logs_dir = str(data["logs_dir"])
    return cfg


def _apply(target: object, values: dict, section: str) -> None:
    known = {f.name: f for f in fields(target)}
    for key, value in values.items():
        if key not in known:
            raise ValueError(f"Неизвестный параметр [{section}] {key} в config.toml")
        current = getattr(target, key)
        if isinstance(current, bool):
            if not isinstance(value, bool):
                raise ValueError(f"[{section}] {key} должен быть true/false")
        elif isinstance(current, (int, float)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"[{section}] {key} должен быть числом")
            value = type(current)(value)
        setattr(target, key, value)
