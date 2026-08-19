"""Story-mode encounters: the protagonist's business journey.

Each Encounter is a self-contained classic game-theory scenario dressed as
a moment in a farmer's journey into business: a setup, a real strategic
choice, a resolution against a specific opponent behavior, a quiz question
that asks the player to explain what just happened, and a plain-language
teaching reveal (possibly staged across multiple pages, e.g. naming the
specific game before generalizing to the broader concept) of the
underlying theory, including an actual 2x2 payoff matrix where relevant.

This addresses direct feedback that the base village game was repetitive
and taught nothing: "just by playing players learn nothing and there is no
storyline." GameManager (game_logic.py) schedules these at specific rounds
(story_encounter_rounds) and resolves their payoff through
submit_story_encounter() — completely separate from the zone-based Solo
payoff, since an encounter's outcome IS that round's result, not a bonus
on top of one.

No pygame dependency here on purpose, same rationale as game_logic.py —
this is content and payoff logic, safe to read/test on its own.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class EncounterChoice:
    id: str
    label: str
    detail: str  # short clarifying line shown under the choice


@dataclass(frozen=True)
class EncounterOutcome:
    player_payoff: int
    result_lines: list[str]


@dataclass(frozen=True)
class QuizQuestion:
    prompt: str
    options: list[str]
    correct_index: int


@dataclass(frozen=True)
class PayoffCell:
    row_payoff: int
    col_payoff: int


@dataclass(frozen=True)
class PayoffMatrix:
    """A 2x2 normal-form payoff table for the lesson screen — actually
    showing the matrix, not just describing it in prose, per direct
    feedback asking for "prisoner's dilemma with 2x2 payoff matrix.\""""
    row_label: str
    col_label: str
    row_options: list[str]
    col_options: list[str]
    cells: dict  # (row_idx, col_idx) -> PayoffCell


@dataclass(frozen=True)
class LessonPage:
    concept_name: str
    lines: list[str]
    show_matrix: bool = False
    highlight_cell: Optional[tuple] = None  # (row_idx, col_idx) in the matrix


@dataclass(frozen=True)
class Encounter:
    id: str
    chapter_title: str
    setup_lines: list[str]
    choices: list[EncounterChoice]
    resolve: Callable[[str, random.Random], EncounterOutcome]
    quiz: QuizQuestion
    lesson_pages: list[LessonPage]
    matrix: Optional[PayoffMatrix] = None


# ---------------------------------------------------------------------------
# Chapter 1: building your stall.
#
# A one-shot simultaneous-move quality/price game — isomorphic to the
# Prisoner's Dilemma, and to Akerlof's "Market for Lemons": both sides have
# a dominant strategy to defect (skimp on quality / haggle down price),
# even though mutual honesty would leave BOTH of them strictly better off.
# The supplier's choice is deliberately deterministic (always low quality)
# rather than randomized — the point isn't chance, it's that this is his
# best response no matter what the player does. See _resolve_quality_price.
#
# Taught in two stages (per direct feedback): first name and show this
# specific game as a Prisoner's Dilemma with its actual matrix, then
# generalize outward to what a Nash equilibrium is.
# ---------------------------------------------------------------------------

_QUALITY_PRICE_PAYOFFS = {
    # (player_choice, supplier_choice): (player_payoff, supplier_payoff)
    ("pay_low", "low_quality"): (-20, 30),
    ("pay_low", "high_quality"): (100, -10),
    ("pay_high", "low_quality"): (-70, 80),
    ("pay_high", "high_quality"): (50, 40),
}

_QUALITY_PRICE_MATRIX = PayoffMatrix(
    row_label="You",
    col_label="Supplier",
    row_options=["Pay Low (Rs 50)", "Pay High (Rs 100)"],
    col_options=["Low Quality", "High Quality"],
    cells={
        (0, 0): PayoffCell(*_QUALITY_PRICE_PAYOFFS[("pay_low", "low_quality")]),
        (0, 1): PayoffCell(*_QUALITY_PRICE_PAYOFFS[("pay_low", "high_quality")]),
        (1, 0): PayoffCell(*_QUALITY_PRICE_PAYOFFS[("pay_high", "low_quality")]),
        (1, 1): PayoffCell(*_QUALITY_PRICE_PAYOFFS[("pay_high", "high_quality")]),
    },
)


def _resolve_quality_price(player_choice: str, rng: random.Random) -> EncounterOutcome:
    supplier_choice = "low_quality"  # his dominant strategy — see the lesson
    player_payoff, _supplier_payoff = _QUALITY_PRICE_PAYOFFS[(player_choice, supplier_choice)]

    player_label = "offered the low price" if player_choice == "pay_low" else "paid the full asking price"
    supplier_label = "quietly used cheaper wood" if supplier_choice == "low_quality" else "built it from the genuine sturdy timber"

    lines = [f"You {player_label}. The supplier {supplier_label}."]
    if player_choice == "pay_high":
        lines.append("You paid full price for a stall that won't hold up through the season — a costly lesson.")
    else:
        lines.append("At least you didn't overpay for it.")
    lines.append(f"Net effect on your new business: {player_payoff:+d} rupees.")

    return EncounterOutcome(player_payoff=player_payoff, result_lines=lines)


QUALITY_PRICE_ENCOUNTER = Encounter(
    id="quality_price",
    chapter_title="Chapter 1: Building Your Stall",
    setup_lines=[
        "You've farmed this land your whole life. This season's harvest "
        "was good enough that you've decided to try something new: a "
        "fresh vegetable stall of your own at the village market, selling "
        "straight from your farm.",
        "First you need a proper stall — a sturdy wooden counter and "
        "crates to display your produce. There's a materials supplier at "
        "the market who can build it for you.",
        "He knows you're a one-time buyer — he'll likely never deal with "
        "you again after this. He could quietly use cheaper, weaker wood "
        "instead of the sturdy stuff, and you won't be able to tell the "
        "difference just by looking.",
        "You have to decide what to pay him right now, before either of "
        "you knows what the other will actually do.",
    ],
    choices=[
        EncounterChoice("pay_low", "Offer the low price", "Rs 50 — protect yourself in case he cheats."),
        EncounterChoice("pay_high", "Pay the full asking price", "Rs 100 — trust that he'll deliver quality."),
    ],
    resolve=_resolve_quality_price,
    quiz=QuizQuestion(
        prompt="Why did the supplier give low quality, no matter what you paid?",
        options=[
            "Because giving low quality was his best move regardless of your choice — a dominant strategy.",
            "Because you offered the low price, so he retaliated.",
            "It was random chance this time.",
        ],
        correct_index=0,
    ),
    matrix=_QUALITY_PRICE_MATRIX,
    lesson_pages=[
        LessonPage(
            concept_name="Prisoner's Dilemma",
            lines=[
                "This exact situation is called a Prisoner's Dilemma — "
                "two sides who would both do better by cooperating, but "
                "each has a private reason not to.",
                "Read the matrix below: whatever the supplier does, you "
                "are always better off paying Low (-20 beats -70; 100 "
                "beats 50). Whatever you pay, the supplier is always "
                "better off giving Low quality (30 beats -10; 80 beats "
                "40).",
                "That's what a 'dominant strategy' means — the best move "
                "regardless of what the other side does.",
            ],
            show_matrix=True,
            highlight_cell=None,
        ),
        LessonPage(
            concept_name="Nash Equilibrium",
            lines=[
                "When both sides play their dominant strategy, you land "
                "on (Pay Low, Low Quality) — highlighted below.",
                "Neither of you can do better by switching alone: pay "
                "High instead and you lose even more; give High quality "
                "instead and the supplier earns less. That's a Nash "
                "equilibrium — a pair of choices where no one benefits "
                "from changing course by themselves.",
                "Notice it's NOT the best possible outcome for either of "
                "you — (High, High) beats it for both. That gap between "
                "'stable' and 'best' is the whole lesson of the "
                "Prisoner's Dilemma: a Nash equilibrium only means no one "
                "wants to move first, not that it's a good outcome.",
            ],
            show_matrix=True,
            highlight_cell=(0, 0),
        ),
    ],
)


STORY_ENCOUNTERS: dict[str, Encounter] = {
    QUALITY_PRICE_ENCOUNTER.id: QUALITY_PRICE_ENCOUNTER,
}
