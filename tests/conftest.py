from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from btc_bot import imaging  # noqa: E402
from btc_bot.screens import Classifier  # noqa: E402
from btc_bot.vision import TemplateLibrary, load_image  # noqa: E402

SAMPLES = ROOT / "samples" / "phone_1280"
DEVICE_W, DEVICE_H = 2780, 1264  # реальный экран телефона


def sample(name: str) -> np.ndarray:
    return load_image(SAMPLES / f"{name}.jpg")


def as_device_frame(img: np.ndarray) -> np.ndarray:
    """Имитирует полноразмерный скриншот с телефона."""
    return imaging.resize(img, DEVICE_W, DEVICE_H)


@pytest.fixture(scope="session")
def classifier() -> Classifier:
    return Classifier(TemplateLibrary.load())


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


@dataclass
class Scene:
    image: np.ndarray
    # куда переходим по нажатию в рамку (рабочие координаты)
    tap_box: tuple[int, int, int, int] | None = None
    on_tap: str | None = None
    # куда переходим сами через столько-то секунд
    after: float | None = None
    then: str | None = None


@dataclass
class FakeDevice:
    scenes: dict[str, Scene]
    current: str
    clock: FakeClock
    taps: list[tuple[str, int, int]] = field(default_factory=list)
    misses: list[tuple[str, int, int]] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)
    entered_at: float = 0.0
    history: list[str] = field(default_factory=list)

    def __post_init__(self):
        self._cache: dict[int, np.ndarray] = {}
        self.history.append(self.current)

    def _go(self, name: str) -> None:
        self.current = name
        self.entered_at = self.clock.now()
        self.history.append(name)

    def _advance(self) -> None:
        while True:
            scene = self.scenes[self.current]
            if scene.after is None or self.clock.now() - self.entered_at < scene.after:
                return
            self._go(scene.then)

    def screenshot(self) -> np.ndarray:
        self._advance()
        img = self.scenes[self.current].image
        key = id(img)
        if key not in self._cache:
            self._cache[key] = as_device_frame(img)
        return self._cache[key]

    def tap(self, x: int, y: int) -> None:
        self._advance()
        scene = self.scenes[self.current]
        wx, wy = x * 1280 / DEVICE_W, y * 1280 / DEVICE_W
        self.taps.append((self.current, round(wx), round(wy)))
        if scene.tap_box is None:
            return
        x1, y1, x2, y2 = scene.tap_box
        if x1 <= wx <= x2 and y1 <= wy <= y2:
            if scene.on_tap:
                self._go(scene.on_tap)
        else:
            self.misses.append((self.current, round(wx), round(wy)))

    def force_stop(self, package: str) -> None:
        self.stopped.append(package)
