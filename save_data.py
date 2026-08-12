"""Persistent cross-game progression.

This is the actual missing progression loop, per the Engagement Loop deck's
own scale table (action loop/seconds -> core gameplay loop/minutes ->
progression loop/sessions-hours): a reason to play a second *game*, not just
survive to the next round of the same one.

Local JSON file, no accounts, no server, nothing to lose by not playing.
Ethical by design (per the course's dark-patterns guardrails): this only
ever adds — no streaks that break, no decay, no login-reminder pressure.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Iterable

_SAVE_PATH = os.path.join(os.path.dirname(__file__), "save_data.json")


@dataclass
class SaveData:
    games_played: int = 0
    best_score: int = 0
    total_points_ever: int = 0
    achievements: list = field(default_factory=list)  # achievement ids, order = unlock order


def load() -> SaveData:
    if not os.path.exists(_SAVE_PATH):
        return SaveData()
    try:
        with open(_SAVE_PATH, "r") as f:
            raw = json.load(f)
        return SaveData(
            games_played=int(raw.get("games_played", 0)),
            best_score=int(raw.get("best_score", 0)),
            total_points_ever=int(raw.get("total_points_ever", 0)),
            achievements=list(raw.get("achievements", [])),
        )
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return SaveData()


def save(data: SaveData) -> None:
    try:
        with open(_SAVE_PATH, "w") as f:
            json.dump(asdict(data), f, indent=2)
    except OSError:
        pass  # never let a save failure crash the game


def record_game_result(data: SaveData, final_score: int, achievements_unlocked: Iterable[str]) -> SaveData:
    data.games_played += 1
    data.best_score = max(data.best_score, final_score)
    data.total_points_ever += final_score
    for achievement_id in achievements_unlocked:
        if achievement_id not in data.achievements:
            data.achievements.append(achievement_id)
    return data
