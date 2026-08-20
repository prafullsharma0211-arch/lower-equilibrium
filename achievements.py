"""Achievements — an ethical Progression-loop layer bolted onto GameManager
via its existing callbacks.

Grounded in the course's own frameworks:
- "Building Blocks of Engagement Systems" (Session 3-4): Achievements —
  badges/trophies/milestones that signal mastery and provide social proof.
- Ethics deck guardrail: nothing here nags, punishes a missed day, or asks
  for money — it's a one-way, no-pressure acknowledgment of something the
  player actually did. No streaks that break, no countdowns, no FOMO.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from game_logic import ApproachOutcome, ApproachResult, GameManager, STARTING_MONEY, SkillRelationship

# Every player now starts with STARTING_MONEY rupees already in hand (see
# game_logic.py), so "reach 1000 points" would fire the instant the game
# begins. The milestone is doubling your money instead, i.e. profiting
# STARTING_MONEY rupees beyond what you started with.
_HIGH_SCORE_TARGET = STARTING_MONEY * 2


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    description: str


ACHIEVEMENTS = [
    Achievement("first_connection", "First Connection", "Form your first connection."),
    Achievement("networker", "Networker", "Reach 6 active connections (Eq2)."),
    Achievement("valley_survivor", "Valley Survivor", "Push through to 11+ connections (Recovery)."),
    Achievement("global_optimum", "Global Optimum", "Reach 15+ connections (Eq3)."),
    Achievement("burnout_recovery", "Burnout Recovery", "Recover from a burnout period."),
    Achievement("persistent", "Persistent", "Attempt 5 Approaches in a single game."),
    Achievement("risk_taker", "Risk Taker", "Land a Complementary-skill connection."),
    Achievement("high_scorer", "High Scorer", f"Double your starting money — reach Rs {_HIGH_SCORE_TARGET}."),
]

_BY_ID = {a.id: a for a in ACHIEVEMENTS}


class AchievementTracker:
    """Watches the human player's progress across ONE game and fires
    on_unlocked(achievement) the moment each condition is first met.

    Construct a fresh instance per game, seeded with achievements already
    unlocked in earlier games (so re-unlocking is silent) — persistence
    across games is save_data.py's job, not this class's.
    """

    def __init__(self, game: GameManager, already_unlocked: Optional[set] = None):
        self.game = game
        self.unlocked: set = set(already_unlocked or set())
        self._was_burned_out = False
        self._approach_attempts = 0

        self.on_unlocked: list[Callable] = []  # (Achievement)

        game.on_human_state_changed.append(self._on_state_changed)
        game.on_human_action_result.append(self._on_action_result)

    def _unlock(self, achievement_id: str) -> None:
        if achievement_id in self.unlocked:
            return
        self.unlocked.add(achievement_id)
        for cb in self.on_unlocked:
            cb(_BY_ID[achievement_id])

    def _on_state_changed(self, human) -> None:
        if human.connection_count >= 1:
            self._unlock("first_connection")
        if human.connection_count >= 6:
            self._unlock("networker")
        if human.connection_count >= 11:
            self._unlock("valley_survivor")
        if human.connection_count >= 15:
            self._unlock("global_optimum")
        if human.points >= _HIGH_SCORE_TARGET:
            self._unlock("high_scorer")

        if human.is_burned_out:
            self._was_burned_out = True
        elif self._was_burned_out and not human.is_burned_out:
            self._unlock("burnout_recovery")
            self._was_burned_out = False

    def _on_action_result(self, result) -> None:
        if isinstance(result, ApproachResult):
            self._approach_attempts += 1
            if self._approach_attempts >= 5:
                self._unlock("persistent")
            if result.outcome == ApproachOutcome.ACCEPT and result.relationship == SkillRelationship.COMPLEMENTARY:
                self._unlock("risk_taker")
