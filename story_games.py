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
    # None for a single-decision-maker sensitivity table (e.g. "your payoff
    # under two scenarios for what everyone else does") where there's no
    # second player's payoff to show in the same cell — see Chapter 2.
    col_payoff: Optional[int] = None


@dataclass(frozen=True)
class PayoffMatrix:
    """A 2x2 table for the lesson screen — actually showing the numbers,
    not just describing them in prose, per direct feedback asking for
    "prisoner's dilemma with 2x2 payoff matrix." Doubles as either a true
    two-player normal-form matrix (paired payoffs per cell) or a one-sided
    sensitivity table (single payoff per cell, PayoffCell.col_payoff=None)
    for games with more than two decision-makers, where collapsing every
    other player into one "column" would misrepresent their own incentives."""
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
    highlight_row: Optional[int] = None  # highlight a whole row instead of one cell —
    # a dominant strategy holds regardless of the column, so for some
    # lessons the honest highlight is the whole row, not a single outcome.


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


# ---------------------------------------------------------------------------
# Chapter 2: the road fund.
#
# A public-goods game with a matching-grant twist. Five shopkeepers
# (the player + 4 others) can each contribute toward repairing the market
# road; a traveling merchant matches whatever the five of them raise
# together, rupee for rupee; and the resulting fund's benefit is split
# equally among all five, whether or not they personally chipped in.
#
# This is the N-player generalization of Chapter 1's Prisoner's Dilemma —
# the classic "free-rider problem." Contributing your own rupee only
# returns 2/N of a rupee to YOU (here, 2/5 = 0.4), so holding back is a
# dominant strategy regardless of what anyone else does, even though full
# mutual contribution would leave everyone strictly richer. The other four
# shopkeepers are modeled as already-rational free-riders (contribute 0),
# same deliberate-determinism rationale as the supplier in Chapter 1 — see
# _resolve_road_fund.
# ---------------------------------------------------------------------------

_ROAD_FUND_N = 5          # you + 4 other shopkeepers
_ROAD_FUND_SHARE = 100     # the "fair share" ask per shopkeeper
_ROAD_FUND_OTHERS_TOTAL = 0  # the other 4 shopkeepers' fixed (rational) contribution


def _road_fund_net(contribution: int, others_total: int) -> tuple[int, int, int]:
    shopkeeper_total = contribution + others_total
    merchant_match = shopkeeper_total  # matches the shopkeepers' total, rupee for rupee
    road_fund = shopkeeper_total + merchant_match
    share_each = road_fund // _ROAD_FUND_N
    return share_each - contribution, road_fund, share_each


_ROAD_FUND_MATRIX = PayoffMatrix(
    row_label="You",
    col_label="The other 4 shopkeepers",
    row_options=["Contribute nothing", f"Contribute Rs {_ROAD_FUND_SHARE}"],
    col_options=["All free-ride", "All contribute"],
    cells={
        (0, 0): PayoffCell(_road_fund_net(0, 0)[0]),
        (0, 1): PayoffCell(_road_fund_net(0, _ROAD_FUND_SHARE * (_ROAD_FUND_N - 1))[0]),
        (1, 0): PayoffCell(_road_fund_net(_ROAD_FUND_SHARE, 0)[0]),
        (1, 1): PayoffCell(_road_fund_net(_ROAD_FUND_SHARE, _ROAD_FUND_SHARE * (_ROAD_FUND_N - 1))[0]),
    },
)


def _resolve_road_fund(player_choice: str, rng: random.Random) -> EncounterOutcome:
    contribution = _ROAD_FUND_SHARE if player_choice == "contribute" else 0
    net, road_fund, share_each = _road_fund_net(contribution, _ROAD_FUND_OTHERS_TOTAL)

    if player_choice == "contribute":
        lines = [
            f"You put in Rs {contribution} toward the repair. The other four "
            "shopkeepers quietly hold onto theirs.",
            f"The merchant matches the group's total, so the fund comes to "
            f"Rs {road_fund} — split five ways, that's Rs {share_each} back "
            "to each shopkeeper, including the four who paid nothing.",
        ]
    else:
        lines = [
            "You keep your money. The other four shopkeepers do the same.",
            "With nobody contributing, there's nothing for the merchant to "
            "match, and no road fund at all — the road stays exactly as "
            "broken as it was.",
        ]
    lines.append(f"Net effect on your business: {net:+d} rupees.")

    return EncounterOutcome(player_payoff=net, result_lines=lines)


ROAD_FUND_ENCOUNTER = Encounter(
    id="road_fund",
    chapter_title="Chapter 2: The Road Fund",
    setup_lines=[
        "Months into running your vegetable stall, the market road has "
        "fallen into disrepair — deep ruts that scare off cart traffic "
        "and customers alike.",
        "You and four other shopkeepers along that road — the cloth "
        "seller, the potter, the tea stall owner, and the grain merchant "
        "— are each being asked to chip in toward fixing it. The repair "
        f"is expected to cost about Rs {_ROAD_FUND_SHARE * _ROAD_FUND_N} "
        f"total — Rs {_ROAD_FUND_SHARE} a fair share from each of you.",
        "A traveling merchant passing through overhears the plan and "
        "makes an offer: whatever the five of you shopkeepers put in "
        "together, he'll match with an equal amount from his own purse.",
        "Whatever gets raised — your contributions plus his matching "
        "share — pays for the repair, and the benefit of a usable road "
        "again is split equally among all five shopkeepers, however much "
        "each of you actually put in.",
        "It's your turn to decide: how much of your own money goes "
        "toward the road?",
    ],
    choices=[
        EncounterChoice("free_ride", "Contribute nothing", "Keep your money — let the others cover it."),
        EncounterChoice("contribute", f"Contribute your share (Rs {_ROAD_FUND_SHARE})", "Trust that this pays off for everyone, including you."),
    ],
    resolve=_resolve_road_fund,
    quiz=QuizQuestion(
        prompt="Why does contributing your share cost you money personally, even with the merchant matching every rupee?",
        options=[
            "You only get back your equal 1-in-5 slice of the fund, which is less than what you put in, no matter what anyone else does — holding back is your dominant strategy.",
            "The merchant secretly kept some of the matching money.",
            "The road repair failed, so the money was wasted.",
        ],
        correct_index=0,
    ),
    matrix=_ROAD_FUND_MATRIX,
    lesson_pages=[
        LessonPage(
            concept_name="Public Goods Game (The Free-Rider Problem)",
            lines=[
                "This is a bigger version of the same trap as the market "
                "supplier — except now there are five of you instead of "
                "two, and your payoff depends on what EVERYONE puts in, "
                "not just one other person.",
                "Contributions get pooled, doubled by the merchant's "
                "match, then split equally among all five shopkeepers — "
                "whether they contributed or not. Every rupee you put in "
                "only sends 2/5 of a rupee back to you personally; the "
                "rest subsidizes the other four.",
                "Look at the table: whether the other shopkeepers free-ride "
                "or all chip in, your own payoff is always higher in the "
                "top row. That holds in every column — this is a dominant "
                "strategy, the same idea as Chapter 1, just played out "
                "across five people instead of two.",
            ],
            show_matrix=True,
            highlight_row=0,
        ),
        LessonPage(
            concept_name="Nash Equilibrium, Generalized",
            lines=[
                "When holding back is every shopkeeper's best move no "
                "matter what the other four do, the Nash equilibrium is "
                "all five of you contributing nothing — the road never "
                "gets fixed.",
                "Just like before, 'stable' isn't 'best': if all five of "
                "you had contributed, the merchant's match would have "
                "doubled a much bigger pool, and every one of you would "
                "have walked away with more than you started with. Nobody "
                "can get there by acting alone, though — that's exactly "
                "what the free-rider problem punishes.",
                "This is why real roads, bridges, and public services are "
                "usually funded by taxes rather than voluntary donations: "
                "at any real scale, asking people to fund something they "
                "get to benefit from either way reliably breaks down.",
            ],
            show_matrix=True,
            highlight_row=0,
        ),
    ],
)


STORY_ENCOUNTERS: dict[str, Encounter] = {
    QUALITY_PRICE_ENCOUNTER.id: QUALITY_PRICE_ENCOUNTER,
    ROAD_FUND_ENCOUNTER.id: ROAD_FUND_ENCOUNTER,
}
