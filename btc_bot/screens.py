"""Какие экраны бывают и как их узнать по шаблонам."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .vision import Match, TemplateLibrary

# Названия экранов
DEFEAT = "defeat"
DEPTH_UP = "depth_up"
REWARDS_POPUP = "rewards_popup"
LEVEL_CLEARED = "level_cleared"
CHAIN_REACTION = "chain_reaction"
VICTORY = "victory"
RESULT_UNKNOWN = "result_unknown"
BATTLE_WON = "battle_won"
BATTLE = "battle"
TEAM_SETUP = "team_setup"
MAP_CLAIM_ALL = "map_claim_all"
MAP_START = "map_start"
MAP = "map"
LOADING = "loading"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScreenRule:
    name: str
    all_of: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()
    none_of: tuple[str, ...] = ()


# Порядок важен: всплывающие окна поверх карты проверяются раньше самой
# карты, потому что под затемнением шаблоны карты тоже находятся.
RULES: tuple[ScreenRule, ...] = (
    # Шаблона поражения пока нет: появится, когда будет скриншот.
    ScreenRule(DEFEAT, all_of=("defeat_title",)),
    ScreenRule(DEPTH_UP, all_of=("depth_up_title",)),
    ScreenRule(REWARDS_POPUP, any_of=("rewards_title", "rewards_prompt")),
    ScreenRule(LEVEL_CLEARED, all_of=("level_cleared_banner",)),
    ScreenRule(CHAIN_REACTION, all_of=("chain_reaction_banner",)),
    ScreenRule(VICTORY, all_of=("victory_title",)),
    # «Нажмите, чтобы продолжить» на месте экрана итогов, но без «ПОБЕДА»:
    # скорее всего поражение (или «ПОБЕДА» ещё не проявилась).
    ScreenRule(RESULT_UNKNOWN, all_of=("victory_prompt",)),
    ScreenRule(BATTLE_WON, any_of=("battle_won_hint", "battle_won_banner")),
    ScreenRule(BATTLE, any_of=("battle_pause", "battle_label")),
    ScreenRule(TEAM_SETUP, any_of=("team_setup_title", "btn_battle_start")),
    ScreenRule(MAP_CLAIM_ALL, all_of=("campaign_header", "btn_claim_all")),
    ScreenRule(MAP_START, all_of=("campaign_header", "btn_map_start")),
    ScreenRule(MAP, all_of=("campaign_header",)),
    ScreenRule(LOADING, all_of=("loading_text",)),
)


@dataclass
class Detection:
    screen: str
    matches: dict[str, Match] = field(default_factory=dict)

    def center(self, name: str) -> tuple[int, int] | None:
        m = self.matches.get(name)
        return m.center if m else None


class Classifier:
    def __init__(self, library: TemplateLibrary, rules: tuple[ScreenRule, ...] = RULES):
        self.lib = library
        # Правила, для которых нет нужных шаблонов, пропускаем целиком
        self.rules = tuple(r for r in rules if self._usable(r))

    def _usable(self, rule: ScreenRule) -> bool:
        if any(n not in self.lib for n in rule.all_of):
            return False
        if rule.any_of and not any(n in self.lib for n in rule.any_of):
            return False
        return True

    def classify(self, frame: np.ndarray) -> Detection:
        """frame уже нормализован (ширина 1280)."""
        cache: dict[str, Match | None] = {}

        def found(name: str) -> Match | None:
            if name not in cache:
                cache[name] = self.lib.found(frame, name) if name in self.lib else None
            return cache[name]

        for rule in self.rules:
            if not all(found(n) for n in rule.all_of):
                continue
            # any_of проверяем целиком: обработчику нужны координаты всех
            # найденных элементов (например, кнопки, а не только заголовка)
            if rule.any_of and not any([found(n) for n in rule.any_of]):
                continue
            if any(found(n) for n in rule.none_of):
                continue
            return Detection(rule.name, {n: m for n, m in cache.items() if m})
        return Detection(UNKNOWN, {n: m for n, m in cache.items() if m})

    def auto_state(self, frame: np.ndarray) -> tuple[bool | None, Match | None]:
        """Состояние кнопки «АВТО» в бою: True/False или None, если не видно.

        Цвета кнопки похожи по форме, поэтому сравниваем, на какой из двух
        шаблонов кадр похож больше, а не каждый с порогом по отдельности.
        """
        on = self.lib.match(frame, "auto_on")
        off = self.lib.match(frame, "auto_off")
        if on is None or off is None:
            return None, on or off
        best = on if on.score >= off.score else off
        if best.score < 0.6 or abs(on.score - off.score) < 0.05:
            return None, best
        return best is on, best

    def scores(self, frame: np.ndarray) -> dict[str, float]:
        """Оценки всех шаблонов: для отладки распознавания."""
        return {n: self.lib.match(frame, n).score for n in sorted(self.lib.templates)}
