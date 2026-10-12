"""Запись игры: скриншоты по таймеру и/или в момент каждого касания.

Нужна, чтобы собрать полноразмерные кадры для новых шаблонов (поражение,
диалоги, нехватка стамины) и позже — материал для боевой логики.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from . import imaging
from .adb import AdbError, Device, parse_touches, touch_to_screen
from .vision import normalize, save_image

log = logging.getLogger("btc_bot")


class Recorder:
    def __init__(
        self,
        device: Device,
        out_dir: Path,
        interval: float | None = None,
        taps: bool = True,
        rotation: int | None = None,
    ):
        self.device = device
        self.out_dir = out_dir
        # без касаний пишем хотя бы по таймеру
        self.interval = interval if interval or taps else 2.0
        self.taps = taps
        self.rotation = rotation
        self._lock = threading.Lock()
        self._latest: tuple[float, np.ndarray] | None = None
        self._stop = threading.Event()
        self.saved_timed = 0
        self.saved_taps = 0

    def run(self, duration: float | None = None) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        log.info("Запись в %s. Остановить: Ctrl+C", self.out_dir)
        capture = threading.Thread(target=self._capture_loop, daemon=True)
        capture.start()
        deadline = time.monotonic() + duration if duration else None
        try:
            if self.taps:
                self._taps_loop(deadline)
            else:
                while not self._stop.is_set():
                    if deadline and time.monotonic() >= deadline:
                        break
                    time.sleep(0.2)
        except KeyboardInterrupt:
            pass
        finally:
            self._stop.set()
            capture.join(timeout=10)
            log.info("Запись остановлена: кадров по таймеру %d, по касаниям %d",
                     self.saved_timed, self.saved_taps)

    # --- непрерывный захват --------------------------------------------

    def _capture_loop(self) -> None:
        last_saved = float("-inf")
        while not self._stop.is_set():
            try:
                frame = self.device.screenshot()
            except AdbError as e:
                log.warning("Скриншот не получился: %s", e)
                time.sleep(1)
                continue
            now = time.monotonic()
            with self._lock:
                self._latest = (now, frame)
            if self.interval and now - last_saved >= self.interval:
                last_saved = now
                self.saved_timed += 1
                save_image(self.out_dir / f"t_{self.saved_timed:04d}.jpg", frame)

    def _latest_frame(self, wait: float = 5.0) -> np.ndarray | None:
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            with self._lock:
                if self._latest is not None:
                    return self._latest[1]
            time.sleep(0.1)
        return None

    # --- касания --------------------------------------------------------

    def _taps_loop(self, deadline: float | None) -> None:
        axes = self.device.touch_axes()
        if axes is None:
            log.warning("Не нашёл сенсорный экран в getevent: пишу только по таймеру")
            self.taps = False
            if not self.interval:
                self.interval = 2.0
            while not self._stop.is_set() and not (deadline and time.monotonic() >= deadline):
                time.sleep(0.2)
            return

        rotation = self.rotation
        if rotation is None:
            rotation = self.device.rotation()
        if rotation is None:
            frame = self._latest_frame()
            rotation = 1 if frame is not None and frame.shape[1] > frame.shape[0] else 0
            log.warning("Поворот экрана не определён, считаю %d", rotation)
        log.info("Сенсор %s (макс. %d×%d), поворот %d", axes.device, axes.max_x, axes.max_y,
                 rotation)

        proc = self.device.stream_events()
        down: dict | None = None
        try:
            for ev in parse_touches(self._lines(proc, deadline), axes.device):
                if ev.raw_x is None or ev.raw_y is None:
                    continue
                frame = self._latest_frame()
                if frame is None:
                    continue
                h, w = frame.shape[:2]
                x, y = touch_to_screen(ev.raw_x, ev.raw_y, axes, w, h, rotation)
                if ev.kind == "down":
                    down = self._save_tap(frame, x, y, ev.raw_x, ev.raw_y)
                elif down is not None:
                    if abs(x - down["x"]) > 30 or abs(y - down["y"]) > 30:
                        self._log_event({"n": down["n"], "event": "swipe_end", "x": x, "y": y})
                    down = None
        finally:
            proc.terminate()

    def _lines(self, proc, deadline: float | None):
        """Строки getevent через очередь, чтобы останавливаться и без касаний."""
        lines: queue.Queue[str | None] = queue.Queue()

        def pump():
            for line in proc.stdout:
                lines.put(line)
            lines.put(None)

        threading.Thread(target=pump, daemon=True).start()
        while not self._stop.is_set():
            if deadline and time.monotonic() >= deadline:
                return
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                continue
            if line is None:
                return
            yield line

    def _save_tap(self, frame: np.ndarray, x: int, y: int, raw_x: int, raw_y: int) -> dict:
        self.saved_taps += 1
        n = self.saved_taps
        name = f"tap_{n:04d}.jpg"
        save_image(self.out_dir / name, frame)

        marked = frame.copy()
        radius = max(12, frame.shape[1] // 80)
        imaging.draw_circle(marked, (x, y), radius, (0, 255, 255), 3)
        imaging.draw_circle(marked, (x, y), 3, (0, 0, 255), -1)
        save_image(self.out_dir / "annotated" / name, marked)

        _, scale = normalize(frame)
        entry = {
            "n": n,
            "time": datetime.now().isoformat(timespec="seconds"),
            "event": "tap",
            "x": x,
            "y": y,
            "work_x": round(x / scale),
            "work_y": round(y / scale),
            "raw": [raw_x, raw_y],
            "frame": name,
        }
        self._log_event(entry)
        log.info("Касание #%d: (%d, %d), рабочие (%d, %d)", n, x, y, entry["work_x"],
                 entry["work_y"])
        return entry

    def _log_event(self, entry: dict) -> None:
        with open(self.out_dir / "taps.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
