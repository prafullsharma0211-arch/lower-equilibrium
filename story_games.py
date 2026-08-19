"""Story-mode encounters: the protagonist's business journey.

Each Encounter is a self-contained classic game-theory scenario dressed as
a moment in an entrepreneur's business journey: a setup, a real strategic
choice, a resolution against a specific opponent behavior, a quiz question
that asks the player to explain what just happened, and a plain-language
teaching reveal of the underlying concept.

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
from typing import Callable


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
class Encounter:
    id: str
    chapter_title: str
    concept_name: str
    setup_lines: list[str]
    choices: list[EncounterChoice]
    resolve: Callable[[str, random.Random], EncounterOutcome]
    quiz: QuizQuestion
    lesson_lines: list[str]


# ---------------------------------------------------------------------------
# Chapter 1: the supplier at the market.
#
# A one-shot simultaneous-move quality/price game — isomorphic to the
# Prisoner's Dilemma, and to Akerlof's "Market for Lemons": both sides have
# a dominant strategy to defect (skimp on quality / haggle down price),
# even though mutual honesty would leave BOTH of them strictly better off.
# The supplier's choice is deliberately deterministic (always low quality)
# rather than randomized — the point isn't chance, it's that this is his
# best response no matter what the player does. See _resolve_quality_price.
# ---------------------------------------------------------------------------

_QUALITY_PRICE_PAYOFFS = {
    # (player_choice, supplier_choice): (player_payoff, supplier_payoff)
    ("pay_low", "low_quality"): (-20, 30),
    ("pay_low", "high_quality"): (100, -10),
    ("pay_high", "low_quality"): (-70, 80),
    ("pay_high", "high_quality"): (50, 40),
}


def _resolve_quality_price(player_choice: str, rng: random.Random) -> EncounterOutcome:
    supplier_choice = "low_quality"  # his dominant strategy — see lesson_lines
    player_payoff, _supplier_payoff = _QUALITY_PRICE_PAYOFFS[(player_choice, supplier_choice)]

    player_label = "offered the low price" if player_choice == "pay_low" else "paid the full asking price"
    supplier_label = "quietly swapped in cheaper material" if supplier_choice == "low_quality" else "delivered the genuine high-grade material"

    lines = [f"You {player_label}. The supplier {supplier_label}."]
    if player_choice == "pay_high":
        lines.append("You paid full price for material that won't hold up — a costly lesson.")
    else:
        lines.append("At least you didn't overpay for it.")
    lines.append(f"Net effect on your business: {player_payoff:+d} rupees.")

    return EncounterOutcome(player_payoff=player_payoff, result_lines=lines)


QUALITY_PRICE_ENCOUNTER = Encounter(
    id="quality_price",
    chapter_title="Chapter 1: The Supplier at the Market",
    concept_name="Nash Equilibrium via Dominant Strategies",
    setup_lines=[
        "Your Kirana shop needs shelving, and there's a supplier at the "
        "market who deals in construction material.",
        "He knows you're a one-time buyer — he'll likely never see you "
        "again. He could quietly sell cheaper, lower-grade material "
        "instead of the good stuff, and you won't be able to tell the "
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
    lesson_lines=[
        "This was a Nash equilibrium reached through dominant strategies — "
        "the same structure as the classic Prisoner's Dilemma.",
        "The supplier's best move was Low quality no matter what you paid: "
        "it's cheaper for him, and in a one-shot deal with a stranger, "
        "there's no reputation on the line to protect.",
        "Knowing that, your best move was to offer the low price too — "
        "paying full price for material you can't verify is the worst "
        "outcome for you.",
        "Neither of you could do better by switching alone — that's the "
        "Nash equilibrium. But notice: if you'd BOTH somehow committed to "
        "High price + High quality, you would both have ended up better "
        "off. That gap is exactly why trust, contracts, and repeat "
        "business exist — they're how real markets escape this trap.",
    ],
)


STORY_ENCOUNTERS: dict[str, Encounter] = {
    QUALITY_PRICE_ENCOUNTER.id: QUALITY_PRICE_ENCOUNTER,
}
