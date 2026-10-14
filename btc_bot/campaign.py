"""Автопрохождение цепной кампании: переходы от боя к бою.

Бои ведёт встроенный автобой игры. Бот смотрит на экран, узнаёт, где он
находится, и нажимает нужную кнопку: «Старт» на карте, «СТАРТ» в
расстановке, «АВТО» в бою (если выключен), продолжение после победы и
сбор наград. При поражении останавливается и закрывает игру.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import screens as S
from .adb import AdbError
from .config import CampaignConfig
from .screens import Classifier, Detection
from .vision import WORK_WIDTH, normalize, save_image

log = logging.getLogger("btc_bot")

# Экраны, после которых долгий неизвестный экран, скорее всего, поражение
BATTLE_SCREENS = (S.BATTLE, S.BATTLE_WON, S.RESULT_UNKNOWN)
# Сколько сбоев ADB подряд терпим (разовый обрыв кабеля, зависший screencap)
MAX_ADB_FAILURES = 5


class Clock:
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class StopBot(Exception):
    """Остановка бота. kind: done | no_stamina | defeat | error | stopped."""

    def __init__(self, kind: str, reason: str):
        super().__init__(reason)
        self.kind = kind
        self.reason = reason


@dataclass
class RunResult:
    kind: str
    reason: str
    runs_done: int
    depth_ups: int
    game_closed: bool

    @property
    def exit_code(self) -> int:
        return {"done": 0, "no_stamina": 0, "defeat": 2, "stopped": 130}.get(self.kind, 1)


class CampaignBot:
    def __init__(
        self,
        device,
        classifier: Classifier,
        cfg: CampaignConfig,
        package: str | None = None,
        session_dir: Path | None = None,
        dry_run: bool = False,
        clock: Clock | None = None,
    ):
        self.device = device
        self.classifier = classifier
        self.cfg = cfg
        self.package = package
        self.session_dir = session_dir
        self.dry_run = dry_run
        self.clock = clock or Clock()

        self.screen: str | None = None
        self.screen_since = 0.0
        self.last_known: str | None = None
        self.last_taps: dict[str, float] = {}
        self.start_taps = 0
        self.awaiting_setup_since: float | None = None
        self.setup_taps = 0
        self.auto_taps = 0
        self.auto_off_streak = 0
        self.runs_done = 0
        self.depth_ups = 0
        self.frame_no = 0
        self.adb_failures = 0
        self.last_raw: np.ndarray | None = None
        self.scale = 1.0
        self._stop_requested = threading.Event()

    def request_stop(self) -> None:
        """Попросить бота остановиться (из другого потока, например из окна)."""
        self._stop_requested.set()

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested.is_set()

    # --- основной цикл --------------------------------------------------

    def run(self) -> RunResult:
        mode = " (пробный режим: ничего не нажимаю)" if self.dry_run else ""
        log.info("Бот запущен%s. Игра: %s", mode, self.package or "не определена")
        try:
            while True:
                self._check_stop_request()
                try:
                    self.step()
                    self.adb_failures = 0
                except AdbError as e:
                    self.adb_failures += 1
                    log.warning("Сбой ADB (%d/%d): %s", self.adb_failures, MAX_ADB_FAILURES, e)
                    if self.adb_failures >= MAX_ADB_FAILURES:
                        raise StopBot("error", f"ADB не отвечает: {e}") from e
                    self.clock.sleep(2.0)
                    continue
                self._check_stop_request()
                self.clock.sleep(self.cfg.poll_interval)
        except StopBot as stop:
            return self._finish(stop)

    def step(self) -> Detection:
        raw = self.device.screenshot()
        frame, self.scale = normalize(raw)
        self.last_raw = raw
        now = self.clock.now()
        det = self.classifier.classify(frame)

        if det.screen != self.screen:
            self._enter(det.screen, now)

        handler = getattr(self, f"_on_{det.screen}")
        handler(det, frame, now)
        if not self.dry_run:  # в пробном режиме играет человек, торопить его незачем
            self._check_timeouts(now)
        return det

    def _check_stop_request(self) -> None:
        if self._stop_requested.is_set():
            raise StopBot("stopped", "Остановлено пользователем")

    # --- смена экрана ---------------------------------------------------

    def _enter(self, screen: str, now: float) -> None:
        prev = self.screen
        self.screen = screen
        self.screen_since = now
        self.frame_no += 1
        log.info("Экран: %s%s", screen, f" (был {prev})" if prev else "")
        if screen != S.UNKNOWN:
            self.last_known = screen
        if self.cfg.save_frames:
            self._save_frame(f"{self.frame_no:04d}_{screen}")

        if screen == S.TEAM_SETUP:
            self.start_taps = 0
            self.awaiting_setup_since = None
            self.auto_taps = 0
        elif screen == S.BATTLE:
            self.setup_taps = 0
            self.auto_off_streak = 0
        elif screen == S.VICTORY:
            self.runs_done += 1
            log.info("Победа! Пройдено забегов: %d", self.runs_done)
        elif screen == S.DEPTH_UP:
            self.depth_ups += 1
            log.info("Глубина кампании повышена (за сессию: %d)", self.depth_ups)

    def _time_on_screen(self, now: float) -> float:
        return now - self.screen_since

    # --- обработчики экранов --------------------------------------------

    def _on_map_start(self, det: Detection, frame, now: float) -> None:
        if self.cfg.max_runs and self.runs_done >= self.cfg.max_runs:
            raise StopBot("done", f"Пройдено забегов: {self.runs_done}, лимит достигнут")
        if self.start_taps >= self.cfg.max_start_taps:
            raise StopBot("no_stamina",
                          f"Нажал «Старт» {self.start_taps} раза, но расстановка не открылась. "
                          "Скорее всего, закончилась стамина")
        if self._tap("map_start", det.center("btn_map_start")):
            self.start_taps += 1
            if self.awaiting_setup_since is None:
                self.awaiting_setup_since = now

    def _on_map_claim_all(self, det: Detection, frame, now: float) -> None:
        self._tap("claim_all", det.center("btn_claim_all"))

    def _on_level_cleared(self, det: Detection, frame, now: float) -> None:
        # Баннер висит поверх карты с кнопкой «Получить все»
        if self._time_on_screen(now) < self.cfg.overlay_tap_delay:
            return
        point = det.center("btn_claim_all") or self._center_of(frame, "btn_claim_all")
        self._tap("claim_all", point)

    def _on_rewards_popup(self, det: Detection, frame, now: float) -> None:
        if self._time_on_screen(now) < self.cfg.overlay_tap_delay:
            return
        point = det.center("rewards_prompt") or (WORK_WIDTH // 2, 432)
        self._tap("rewards_continue", point)

    def _on_depth_up(self, det: Detection, frame, now: float) -> None:
        if self._time_on_screen(now) < self.cfg.overlay_tap_delay:
            return
        # По заголовку баннер не закрывается: жмём в пустое место внизу экрана
        h, w = frame.shape[:2]
        point = (round(w * self.cfg.depth_up_tap_x), round(h * self.cfg.depth_up_tap_y))
        self._tap("depth_up_continue", point)

    def _on_team_setup(self, det: Detection, frame, now: float) -> None:
        point = det.center("btn_battle_start")
        if point is None:
            return
        if self.setup_taps >= self.cfg.max_start_taps:
            raise StopBot("error", "Нажимаю «СТАРТ» в расстановке, но бой не начинается")
        if self._tap("battle_start", point):
            self.setup_taps += 1

    def _on_battle(self, det: Detection, frame, now: float) -> None:
        if not self.cfg.manage_auto:
            return
        state, match = self.classifier.auto_state(frame)
        if state is True:
            self.auto_off_streak = 0
        elif state is False:
            self.auto_off_streak += 1
        if self.auto_off_streak < self.cfg.auto_off_frames or match is None:
            return
        if self.auto_taps >= self.cfg.max_auto_taps:
            raise StopBot("error", f"«АВТО» не включается после {self.auto_taps} нажатий")
        if self._tap("auto", match.center):
            self.auto_taps += 1
            self.auto_off_streak = 0
            log.info("Автобой был выключен, включаю")

    def _on_victory(self, det: Detection, frame, now: float) -> None:
        if self._time_on_screen(now) < self.cfg.overlay_tap_delay:
            return
        point = det.center("victory_prompt") or (920, 553)
        self._tap("victory_continue", point)

    def _on_result_unknown(self, det: Detection, frame, now: float) -> None:
        if self._time_on_screen(now) >= self.cfg.defeat_confirm:
            raise StopBot("defeat", "Экран итогов без «ПОБЕДА»: похоже на поражение")

    def _on_defeat(self, det: Detection, frame, now: float) -> None:
        raise StopBot("defeat", "Поражение")

    def _wait(self, det: Detection, frame, now: float) -> None:
        pass

    _on_loading = _wait
    _on_battle_won = _wait
    _on_chain_reaction = _wait
    _on_map = _wait
    _on_unknown = _wait

    # --- таймауты -------------------------------------------------------

    def _check_timeouts(self, now: float) -> None:
        # После «Старт» должна открыться расстановка. Если вместо неё висит
        # что-то другое (обычно окно покупки стамины), дальше не идём.
        if (self.awaiting_setup_since is not None
                and self.screen not in (S.TEAM_SETUP, S.LOADING)
                and now - self.awaiting_setup_since >= self.cfg.start_timeout):
            raise StopBot("no_stamina",
                          "После «Старт» не открылась расстановка. Скорее всего, "
                          "закончилась стамина")
        spent = self._time_on_screen(now)
        if self.screen == S.UNKNOWN:
            if spent >= self.cfg.unknown_timeout:
                if self.last_known in BATTLE_SCREENS:
                    raise StopBot("defeat", f"Незнакомый экран после боя дольше {spent:.0f} с: "
                                            "похоже на поражение")
                raise StopBot("error", f"Незнакомый экран дольше {spent:.0f} с")
        elif self.screen == S.BATTLE:
            if spent >= self.cfg.battle_timeout:
                raise StopBot("error", f"Бой идёт дольше {spent:.0f} с")
        elif spent >= self.cfg.state_timeout:
            raise StopBot("error", f"Экран {self.screen} не меняется {spent:.0f} с")

    # --- действия -------------------------------------------------------

    def _tap(self, key: str, point: tuple[int, int] | None) -> bool:
        """Нажатие в рабочих координатах с защитой от повторов.

        Возвращает True, если нажатие действительно сделано. В пробном
        режиме всегда False: в нём играет человек, и счётчики попыток
        («Старт», «АВТО») не должны срабатывать на его медлительность.
        """
        if point is None:
            return False
        now = self.clock.now()
        if now - self.last_taps.get(key, float("-inf")) < self.cfg.tap_cooldown:
            return False
        self.last_taps[key] = now
        x, y = round(point[0] * self.scale), round(point[1] * self.scale)
        if self.dry_run:
            log.info("[пробно] нажал бы %s в (%d, %d)", key, x, y)
            return False
        log.info("Нажимаю %s в (%d, %d)", key, x, y)
        self.device.tap(x, y)
        return True

    def _center_of(self, frame, name: str) -> tuple[int, int] | None:
        m = self.classifier.lib.match(frame, name)
        return m.center if m else None

    def _save_frame(self, name: str) -> None:
        if self.session_dir is None or self.last_raw is None:
            return
        try:
            save_image(self.session_dir / "frames" / f"{name}.jpg", self.last_raw)
        except (OSError, ValueError) as e:
            log.warning("Не удалось сохранить кадр %s: %s", name, e)

    def _finish(self, stop: StopBot) -> RunResult:
        level = logging.INFO if stop.kind in ("done", "no_stamina", "stopped") else logging.WARNING
        log.log(level, "Остановка (%s): %s", stop.kind, stop.reason)
        self._save_frame(f"stop_{stop.kind}")

        exit_game = (stop.kind == "defeat" and self.cfg.exit_game_on_defeat) or \
                    (stop.kind == "error" and self.cfg.exit_game_on_error)
        closed = False
        if exit_game:
            if not self.package:
                log.warning("Не знаю пакет игры, закрыть её не могу (укажи device.package)")
            elif self.dry_run:
                log.info("[пробно] закрыл бы игру %s", self.package)
            else:
                log.info("Закрываю игру %s", self.package)
                try:
                    self.device.force_stop(self.package)
                    closed = True
                except AdbError as e:
                    log.error("Не удалось закрыть игру: %s", e)
        log.info("Итого: забегов %d, повышений глубины %d", self.runs_done, self.depth_ups)
        return RunResult(stop.kind, stop.reason, self.runs_done, self.depth_ups, closed)
