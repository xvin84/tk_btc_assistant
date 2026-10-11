"""Управление телефоном через ADB: скриншоты, нажатия, касания, выход из игры."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Iterator

import cv2
import numpy as np


class AdbError(RuntimeError):
    pass


# Что делать, если `adb devices` показывает телефон не в состоянии device
STATE_HINTS = {
    "unauthorized": (
        "телефон не разрешил отладку этому компьютеру. Разблокируй экран и нажми "
        "«Разрешить» в окне «Разрешить отладку по USB?» (лучше с галочкой «Всегда "
        "разрешать с этого компьютера»). Если окна нет: «Для разработчиков» → "
        "«Отозвать авторизацию отладки по USB», затем `adb kill-server` и переподключи кабель."
    ),
    "offline": "телефон offline. Переподключи кабель или выполни `adb kill-server`.",
    "no": (
        "нет прав на USB-устройство (no permissions). Нужны udev-правила: в Arch пакет "
        "android-udev. После установки переподключи кабель."
    ),
}


@dataclass
class TouchAxes:
    device: str  # /dev/input/eventN
    max_x: int
    max_y: int


class Device:
    def __init__(self, serial: str | None = None, adb: str = "adb", timeout: float = 20.0):
        self.serial = serial
        self.adb = adb
        self.timeout = timeout

    # --- низкий уровень -------------------------------------------------

    def _base(self) -> list[str]:
        cmd = [self.adb]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def _run(self, *args: str, timeout: float | None = None, serial: bool = True) -> bytes:
        cmd = (self._base() if serial else [self.adb]) + list(args)
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout or self.timeout)
        except FileNotFoundError as e:
            raise AdbError(f"Не найден adb ({self.adb}). Установи Android platform-tools "
                           f"и добавь adb в PATH или укажи путь в config.toml") from e
        except subprocess.TimeoutExpired as e:
            raise AdbError(f"adb не ответил за {timeout or self.timeout} с: {' '.join(args)}") from e
        if proc.returncode != 0:
            err = proc.stderr.decode(errors="replace").strip()
            raise AdbError(f"adb {' '.join(args)} завершился с кодом {proc.returncode}: {err}")
        return proc.stdout

    def shell(self, command: str, timeout: float | None = None) -> str:
        return self._run("shell", command, timeout=timeout).decode(errors="replace")

    # --- проверки -------------------------------------------------------

    def adb_available(self) -> bool:
        return shutil.which(self.adb) is not None or _looks_like_path(self.adb)

    def devices(self) -> list[tuple[str, str]]:
        out = self._run("devices", serial=False).decode(errors="replace")
        rows = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                rows.append((parts[0], parts[1]))
        return rows

    def ensure_ready(self) -> str:
        """Проверяет, что телефон подключён и разрешил отладку. Возвращает serial."""
        rows = self.devices()
        if self.serial:
            rows = [r for r in rows if r[0] == self.serial]
            if not rows:
                raise AdbError(f"Устройство {self.serial} не найдено в `adb devices`")
        if not rows:
            raise AdbError("Телефон не виден в `adb devices`. Включи «Отладку по USB» и "
                           "подключи кабель (режим USB «Передача файлов»)")
        ready = [serial for serial, state in rows if state == "device"]
        if len(ready) > 1:
            raise AdbError(f"Подключено несколько устройств ({', '.join(ready)}): "
                           "укажи нужное через --serial")
        if not ready:
            serial, state = rows[0]
            hint = STATE_HINTS.get(state, "проверь подключение и `adb devices`.")
            raise AdbError(f"{serial} в состоянии {state}: {hint}")
        return ready[0]

    # --- экран и ввод ---------------------------------------------------

    def screenshot(self) -> np.ndarray:
        data = self._run("exec-out", "screencap", "-p")
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise AdbError("Не удалось декодировать скриншот (пустой ответ screencap?)")
        return img

    def tap(self, x: int, y: int) -> None:
        self.shell(f"input tap {int(x)} {int(y)}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}")

    def force_stop(self, package: str) -> None:
        self.shell(f"am force-stop {package}")

    # --- сведения об устройстве -----------------------------------------

    def current_package(self) -> str | None:
        """Пакет приложения, которое сейчас на экране."""
        out = self.shell("dumpsys window")
        for key in ("mCurrentFocus", "mFocusedApp"):
            m = re.search(key + r"=.*?\s([A-Za-z][\w.]*)/[\w.$]+", out)
            if m:
                return m.group(1)
        return None

    def packages(self, needle: str = "funcat") -> list[str]:
        out = self.shell("pm list packages")
        return sorted(line.split(":", 1)[1].strip() for line in out.splitlines()
                      if line.startswith("package:") and needle in line)

    def rotation(self) -> int | None:
        """Поворот экрана: 0..3 (0, 90, 180, 270 градусов) или None."""
        out = self.shell("dumpsys window displays")
        m = re.search(r"mCurrentRotation=(?:ROTATION_)?(\d+)", out)
        if m:
            value = int(m.group(1))
            return value // 90 if value >= 90 else value
        m = re.search(r"mRotation=(\d)", out)
        if m:
            return int(m.group(1))
        out = self.shell("dumpsys input")
        m = re.search(r"SurfaceOrientation:\s*(\d)", out)
        if m:
            return int(m.group(1))
        return None

    def wm_size(self) -> str:
        return self.shell("wm size").strip()

    # --- касания пользователя (для записи) ------------------------------

    def touch_axes(self) -> TouchAxes | None:
        """Находит сенсорный экран и диапазоны его координат."""
        out = self.shell("getevent -lp")
        return parse_touch_axes(out)

    def stream_events(self) -> subprocess.Popen:
        """Запускает `getevent -lt`; строки читаются из proc.stdout."""
        return subprocess.Popen(
            self._base() + ["shell", "getevent", "-lt"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=1,
            text=True,
            errors="replace",
        )


def _looks_like_path(adb: str) -> bool:
    return "/" in adb or "\\" in adb


def parse_touch_axes(getevent_lp: str) -> TouchAxes | None:
    device = None
    max_x = max_y = None
    for line in getevent_lp.splitlines():
        m = re.match(r"add device \d+:\s*(\S+)", line)
        if m:
            if device and max_x is not None and max_y is not None:
                break
            device, max_x, max_y = m.group(1), None, None
            continue
        m = re.search(r"ABS_MT_POSITION_([XY])\s*:.*?max\s+(\d+)", line)
        if m and device:
            if m.group(1) == "X":
                max_x = int(m.group(2))
            else:
                max_y = int(m.group(2))
    if device and max_x is not None and max_y is not None:
        return TouchAxes(device, max_x, max_y)
    return None


@dataclass
class TouchEvent:
    kind: str  # "down" | "up"
    time: float  # время ядра из getevent, с
    raw_x: int | None
    raw_y: int | None


def parse_touches(lines: Iterator[str], device: str | None = None) -> Iterator[TouchEvent]:
    """Превращает поток `getevent -lt` в события нажатия и отпускания.

    Считаем пальцем первое касание; мультитач для записи не нужен.
    """
    x = y = None
    pending: str | None = None
    t = 0.0
    pattern = re.compile(r"\[\s*([\d.]+)\]\s+(\S+):\s+(\S+)\s+(\S+)\s+(\S+)")
    for line in lines:
        m = pattern.search(line)
        if not m:
            continue
        ts, dev, _etype, code, value = m.groups()
        if device and dev.rstrip(":") != device:
            continue
        t = float(ts)
        if code == "ABS_MT_POSITION_X":
            x = int(value, 16)
        elif code == "ABS_MT_POSITION_Y":
            y = int(value, 16)
        elif code == "BTN_TOUCH":
            pending = "down" if value == "DOWN" else "up"
        elif code == "ABS_MT_TRACKING_ID":
            if value.lower() == "ffffffff":
                pending = pending or "up"
            elif pending is None:
                pending = "down"
        elif code == "SYN_REPORT" and pending:
            yield TouchEvent(pending, t, x, y)
            pending = None


def touch_to_screen(raw_x: float, raw_y: float, axes: TouchAxes,
                    screen_w: int, screen_h: int, rotation: int) -> tuple[int, int]:
    """Координаты сенсора -> координаты скриншота с учётом поворота.

    Формулы как в TouchInputMapper Android. screen_w/screen_h задают
    размер скриншота в текущей ориентации.
    """
    if rotation % 2:
        nat_w, nat_h = screen_h, screen_w
    else:
        nat_w, nat_h = screen_w, screen_h
    x = raw_x * nat_w / (axes.max_x + 1)
    y = raw_y * nat_h / (axes.max_y + 1)
    if rotation == 1:
        sx, sy = y, nat_w - x
    elif rotation == 2:
        sx, sy = nat_w - x, nat_h - y
    elif rotation == 3:
        sx, sy = nat_h - y, x
    else:
        sx, sy = x, y
    return int(round(sx)), int(round(sy))
