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
class Step:
    """One beat of the setup narration — an icon and a short caption for
    the horizontal storyboard strip, plus the full sentence shown as detail
    text underneath once that step is reached. Direct feedback: explain
    things "icon-wise for each statement... one box after another
    horizontally," not a stack of plain paragraphs."""
    icon: str
    caption: str
    text: str


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
    highlight_cells: Optional[list] = None  # multiple cells — a coordination
    # game like Stag Hunt has more than one genuine Nash equilibrium, and
    # showing only one would misrepresent the game.


@dataclass(frozen=True)
class Encounter:
    id: str
    chapter_title: str
    setup_steps: list[Step]
    choices: list[EncounterChoice]
    resolve: Callable[[str, random.Random], EncounterOutcome]
    quiz: QuizQuestion
    lesson_pages: list[LessonPage]
    matrix: Optional[PayoffMatrix] = None
    # A drawn icon name (see draw_icon() in main.py) shown throughout the
    # chapter — a visual anchor for the scenario, not just paragraphs of
    # setup text, per direct feedback asking for more image, less text.
    chapter_icon: Optional[str] = None


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
    setup_steps=[
        Step("idea", "New idea",
             "You've farmed this land your whole life. This season's harvest "
             "was good enough that you've decided to try something new: a "
             "fresh vegetable stall of your own at the village market, selling "
             "straight from your farm."),
        Step("trade", "Find a supplier",
             "First you need a proper stall — a sturdy wooden counter and "
             "crates to display your produce. There's a materials supplier at "
             "the market who can build it for you."),
        Step("warning", "Could get cheated",
             "He knows you're a one-time buyer — he'll likely never deal with "
             "you again after this. He could quietly use cheaper, weaker wood "
             "instead of the sturdy stuff, and you won't be able to tell the "
             "difference just by looking."),
        Step("scale", "Your move",
             "You have to decide what to pay him right now, before either of "
             "you knows what the other will actually do."),
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
    chapter_icon="trade",
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
    setup_steps=[
        Step("road", "Road's broken",
             "Months into running your vegetable stall, the market road has "
             "fallen into disrepair — deep ruts that scare off cart traffic "
             "and customers alike."),
        Step("trade", "Chip in your share",
             "You and four other shopkeepers along that road — the cloth "
             "seller, the potter, the tea stall owner, and the grain merchant "
             "— are each being asked to chip in toward fixing it. The repair "
             f"is expected to cost about Rs {_ROAD_FUND_SHARE * _ROAD_FUND_N} "
             f"total — Rs {_ROAD_FUND_SHARE} a fair share from each of you."),
        Step("idea", "Merchant will match",
             "A traveling merchant passing through overhears the plan and "
             "makes an offer: whatever the five of you shopkeepers put in "
             "together, he'll match with an equal amount from his own purse."),
        Step("road", "Shared benefit",
             "Whatever gets raised — your contributions plus his matching "
             "share — pays for the repair, and the benefit of a usable road "
             "again is split equally among all five shopkeepers, however much "
             "each of you actually put in."),
        Step("scale", "Your move",
             "It's your turn to decide: how much of your own money goes "
             "toward the road?"),
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
    chapter_icon="road",
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


# ---------------------------------------------------------------------------
# Chapter 3: the cold storage bet.
#
# A Stag Hunt (coordination game), genuinely different from Chapters 1-2:
# there is no dominant strategy for either side. A rare, fast-spoiling
# vegetable is only worth importing if a warehouse owner separately builds
# cold storage; the storage is only worth building if there's perishable
# trade to justify it. Committing together (Import Special + Build) is the
# best outcome for both — but it's not safe, because committing ALONE while
# the other side plays safe is the worst outcome. Playing safe together
# (Import Regular + Don't Build) is also a stable equilibrium, just a worse
# one. Verified algebraically (both same-action cells are Nash equilibria,
# both mismatched cells are not, and mutual commitment Pareto-dominates
# mutual caution) before writing a line of narrative — see the module
# docstring's sibling chapters for the same discipline.
#
# The warehouse owner is scripted to play safe (Don't Build) — same
# deliberate-determinism rationale as Chapters 1-2's opponents: he has no
# established trust with a still-new farmer, so absent any assurance he
# defaults to the risk-dominant choice. That's not a quirk of this one
# NPC — it's the central real-world insight a Stag Hunt is built to teach.
# ---------------------------------------------------------------------------

_STAG_HUNT_PAYOFFS = {
    # (farmer_choice, supplier_choice): (farmer_payoff, supplier_payoff)
    ("import_special", "build"): (150, 150),
    ("import_special", "no_build"): (-100, 40),
    ("import_regular", "build"): (40, -80),
    ("import_regular", "no_build"): (40, 40),
}

_STAG_HUNT_MATRIX = PayoffMatrix(
    row_label="You",
    col_label="Warehouse owner",
    row_options=["Import special greens", "Import regular produce"],
    col_options=["Builds cold storage", "Doesn't build"],
    cells={
        (0, 0): PayoffCell(*_STAG_HUNT_PAYOFFS[("import_special", "build")]),
        (0, 1): PayoffCell(*_STAG_HUNT_PAYOFFS[("import_special", "no_build")]),
        (1, 0): PayoffCell(*_STAG_HUNT_PAYOFFS[("import_regular", "build")]),
        (1, 1): PayoffCell(*_STAG_HUNT_PAYOFFS[("import_regular", "no_build")]),
    },
)


def _resolve_stag_hunt(player_choice: str, rng: random.Random) -> EncounterOutcome:
    supplier_choice = "no_build"  # plays it safe -- see the lesson
    player_payoff, _supplier_payoff = _STAG_HUNT_PAYOFFS[(player_choice, supplier_choice)]

    if player_choice == "import_special":
        lines = [
            "You bring in a cart of the rare hill greens, banking on there "
            "being somewhere to keep them fresh.",
            "The warehouse owner decided the risk wasn't worth it and never "
            "built the cold store. Within two days, your entire shipment "
            "has spoiled, unsold.",
        ]
    else:
        lines = [
            "You stick with your usual produce.",
            "The warehouse owner, seeing no clear demand for cold storage, "
            "doesn't build it either — turns out you both played it safe.",
        ]
    lines.append(f"Net effect on your business: {player_payoff:+d} rupees.")

    return EncounterOutcome(player_payoff=player_payoff, result_lines=lines)


STAG_HUNT_ENCOUNTER = Encounter(
    id="stag_hunt",
    chapter_title="Chapter 3: The Cold Storage Bet",
    setup_steps=[
        Step("idea", "Rare opportunity",
             "Your vegetable stall has been steady work, but you've heard about "
             "a rare, high-value leafy green grown only in the hills — "
             "delicate, and it spoils within two days unless kept properly "
             "cold."),
        Step("cold_storage", "Needs cold storage",
             "If you could sell it fresh, it would fetch triple what your usual "
             "produce does. But without a cold store nearby, it would rot in "
             "your cart before a single customer saw it."),
        Step("cold_storage", "His decision too",
             "There's a warehouse owner in town weighing whether to build a "
             "proper cold-storage unit — a serious investment for him, and "
             "only worth it if there's enough perishable trade in town to "
             "justify it."),
        Step("question", "Mutual unknown",
             "Neither of you knows what the other will decide. If you both "
             "commit — you import, he builds — you'll both do very well. But "
             "if only one of you commits and the other plays it safe, whoever "
             "gambled alone takes the loss."),
        Step("scale", "Your move", "What do you do?"),
    ],
    choices=[
        EncounterChoice("import_special", "Import the special greens", "Big reward if the cold storage gets built — a real loss if it doesn't."),
        EncounterChoice("import_regular", "Stick with your regular produce", "Smaller, steady profit no matter what he decides."),
    ],
    resolve=_resolve_stag_hunt,
    quiz=QuizQuestion(
        prompt="Why did importing the special greens lose you money this time, when Chapter 1's 'safe' choice was always correct regardless of the other side?",
        options=[
            "Because this game has no dominant strategy — the right move depends entirely on what the other person does, and you bet on trust that didn't pay off.",
            "Because importing goods is against the rules.",
            "Because the warehouse owner cheated you on purpose.",
        ],
        correct_index=0,
    ),
    matrix=_STAG_HUNT_MATRIX,
    chapter_icon="cold_storage",
    lesson_pages=[
        LessonPage(
            concept_name="Stag Hunt (a Coordination Game)",
            lines=[
                "This is a different kind of game from Chapters 1 and 2 — "
                "there's no dominant strategy here. Importing the special "
                "greens isn't always right or always wrong; it's only a "
                "good move if the warehouse owner also commits.",
                "This structure is called a Stag Hunt, from an old story "
                "about two hunters: together they can catch a stag (a big "
                "reward, but only if both commit to the hunt), or each can "
                "catch a hare alone (small, safe, guaranteed).",
                "Look at the matrix: if you BOTH commit (top-left), you "
                "both do great. If you both play safe (bottom-right), you "
                "both do fine. But if only one of you commits, that person "
                "takes a real loss while the other stays safe.",
            ],
            show_matrix=True,
        ),
        LessonPage(
            concept_name="Two Nash Equilibria",
            lines=[
                "Unlike Chapter 1's single equilibrium, this game has TWO "
                "stable outcomes, both highlighted below: mutual "
                "commitment (best for both) and mutual caution (safe, but "
                "leaves value on the table).",
                "Both are genuine Nash equilibria — at either one, neither "
                "side can do better by switching alone. Which one you land "
                "on depends entirely on trust: would you have committed "
                "if you'd been sure the warehouse owner would too?",
                "This is why real business partnerships lean on "
                "contracts, deposits, and track records instead of blind "
                "trust — they're tools for turning a risky Stag Hunt into "
                "a safe bet on the better outcome, the same way Chapter "
                "2's equilibrium showed why voluntary goodwill alone "
                "often isn't enough.",
            ],
            show_matrix=True,
            highlight_cells=[(0, 0), (1, 1)],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Chapter 4: the juice stall standoff.
#
# A Game of Chicken (Hawk-Dove) — the mirror image of Chapter 3's Stag
# Hunt. There, matching the other side was the good outcome; here, matching
# is the disaster. The market can only support one green-juice stall: if
# both the player and the rival vendor open (mutual Hawk), they crash —
# both lose money undercutting each other in a market too small for
# either. If exactly one opens, that one wins the whole new market and the
# other is unaffected. Two pure Nash equilibria, both on the off-diagonal
# (one side Hawk, the other Dove) — verified algebraically (both
# mismatched cells are stable, both matched cells are not, and winning
# alone beats mutual restraint beats mutual crash) before writing a line
# of narrative, same discipline as the earlier chapters.
#
# This chapter also introduces a genuine third move beyond the normal
# simultaneous 2-choice pattern: publicly, irreversibly committing to open
# before the rival decides — Schelling's "burning your bridges" (the
# steering-wheel-out-the-window move from the classic telling of Chicken).
# A credible, irreversible commitment changes the OPPONENT's best response:
# facing a rival who provably can't back down, the rational move is to
# yield rather than crash. See _resolve_juice_stall: quietly opening with
# no signal meets the rival's own default plan to open too (mutual
# crash — neither side had a reason to expect the other to back off);
# not opening leaves the rival's default plan untouched (they win, you're
# safe); publicly committing is the only choice that flips the rival's
# default from Hawk to Dove.
# ---------------------------------------------------------------------------

_CHICKEN_PAYOFFS = {
    # (player_move, rival_move): (player_payoff, rival_payoff), Hawk = compete, Dove = back off
    ("hawk", "hawk"): (-120, -120),
    ("hawk", "dove"): (200, 20),
    ("dove", "hawk"): (20, 200),
    ("dove", "dove"): (20, 20),
}

_CHICKEN_MATRIX = PayoffMatrix(
    row_label="You",
    col_label="Rival vendor",
    row_options=["Open your stall", "Don't open"],
    col_options=["Opens too", "Backs off"],
    cells={
        (0, 0): PayoffCell(*_CHICKEN_PAYOFFS[("hawk", "hawk")]),
        (0, 1): PayoffCell(*_CHICKEN_PAYOFFS[("hawk", "dove")]),
        (1, 0): PayoffCell(*_CHICKEN_PAYOFFS[("dove", "hawk")]),
        (1, 1): PayoffCell(*_CHICKEN_PAYOFFS[("dove", "dove")]),
    },
)


def _resolve_juice_stall(player_choice: str, rng: random.Random) -> EncounterOutcome:
    if player_choice == "commit_publicly":
        player_move, rival_move = "hawk", "dove"
        lines = [
            "You sign a lease on the corner stall that same afternoon and "
            "tell everyone in the market who'll listen.",
            "Word gets back to the rival vendor fast — and by evening, "
            "he's quietly dropped the idea. No point competing with a "
            "done deal. You open the green juice stall alone.",
        ]
    elif player_choice == "open_quietly":
        player_move, rival_move = "hawk", "hawk"
        lines = [
            "You start quietly sourcing greens and a blender, telling no "
            "one.",
            "Turns out the rival vendor had the exact same idea, and "
            "neither of you knew it. By the time you both realize it, "
            "you're already mid-setup and neither backs down — two green "
            "juice stalls open the same week, in a market that can't "
            "support either.",
        ]
    else:  # dont_open
        player_move, rival_move = "dove", "hawk"
        lines = [
            "You decide it's not worth the risk and keep running your "
            "stall as it is.",
            "Sure enough, the rival vendor opens a green juice stall a "
            "few weeks later — and it does well. No loss for you, but "
            "the opportunity's gone.",
        ]

    player_payoff, _rival_payoff = _CHICKEN_PAYOFFS[(player_move, rival_move)]
    lines.append(f"Net effect on your business: {player_payoff:+d} rupees.")
    return EncounterOutcome(player_payoff=player_payoff, result_lines=lines)


JUICE_STALL_ENCOUNTER = Encounter(
    id="juice_stall",
    chapter_title="Chapter 4: The Juice Stall Standoff",
    setup_steps=[
        Step("idea", "New idea",
             "Your stall's doing well, and you've spotted a gap in the market: "
             "nobody's selling fresh green juice — fruit blended with leafy "
             "greens. You could set it up within a week."),
        Step("standoff", "A rival, too",
             "But you're not the only one who's noticed. A rival fruit vendor "
             "across the market has been eyeing the exact same idea."),
        Step("warning", "Too small for both",
             "The market's only big enough to support ONE green juice stall. "
             "If you both open, you'll flood a market that can barely support "
             "one — and you'll both lose money undercutting each other."),
        Step("standoff", "Winner takes all",
             "If only one of you opens, that person captures the whole new "
             "market. Whoever backs off just keeps running their stall as "
             "usual — no loss, just no upside either."),
        Step("question", "Your move",
             "You don't know what the rival vendor is planning. But you have "
             "options beyond just guessing."),
    ],
    choices=[
        EncounterChoice("open_quietly", "Quietly start setting up", "No announcement — you're hoping he doesn't have the same idea."),
        EncounterChoice("dont_open", "Don't bother — stick with your stall as is", "Safe. If he opens, he gets the new market; you lose nothing."),
        EncounterChoice("commit_publicly", "Announce it loudly — sign a lease, tell the market", "Burn the bridge: make it impossible to back out, before he decides."),
    ],
    resolve=_resolve_juice_stall,
    quiz=QuizQuestion(
        prompt="Why did announcing your plans loudly actually make you MORE likely to win the market, not less?",
        options=[
            "Once your commitment was public and irreversible, the rival's best move flipped — competing head-on would now cost him more than backing off.",
            "The rival vendor was scared of you personally.",
            "Loud announcements always work in negotiations.",
        ],
        correct_index=0,
    ),
    matrix=_CHICKEN_MATRIX,
    chapter_icon="standoff",
    lesson_pages=[
        LessonPage(
            concept_name="Game of Chicken (Hawk-Dove)",
            lines=[
                "This is another game with no dominant strategy, like "
                "Chapter 3 — but the opposite shape. In the Stag Hunt, "
                "matching the other side was the GOOD outcome. Here, "
                "matching is the WORST outcome.",
                "This structure is called the Game of Chicken, or "
                "Hawk-Dove: two drivers heading straight at each other. "
                "Swerve and you look weak but survive; both hold straight "
                "and you crash.",
                "In your case: opening together is the crash (a market "
                "too small for both of you), and the two stable outcomes "
                "are the ones where you do DIFFERENT things — one of you "
                "opens, the other backs off.",
            ],
            show_matrix=True,
        ),
        LessonPage(
            concept_name="Two Equilibria, and the Power of Commitment",
            lines=[
                "Look at the matrix: (You open, they back off) and (You "
                "back off, they open) are both Nash equilibria — "
                "highlighted below. Whoever ends up backing off wouldn't "
                "gain by switching alone; that would just cause the "
                "crash instead.",
                "Normally, which equilibrium you land on is down to luck "
                "— neither side can be sure what the other will do. But "
                "announcing your plans loudly and irreversibly changes "
                "that: once the rival KNOWS you can't back out, their own "
                "best move becomes backing off, not crashing into you.",
                "This is a real, named tactic — economist Thomas "
                "Schelling called it 'burning your bridges': a "
                "commitment only works if the other side believes you "
                "truly can't reverse it. A steering wheel you can still "
                "hold onto isn't a threat at all.",
            ],
            show_matrix=True,
            highlight_cells=[(0, 1), (1, 0)],
        ),
    ],
)


STORY_ENCOUNTERS: dict[str, Encounter] = {
    QUALITY_PRICE_ENCOUNTER.id: QUALITY_PRICE_ENCOUNTER,
    ROAD_FUND_ENCOUNTER.id: ROAD_FUND_ENCOUNTER,
    STAG_HUNT_ENCOUNTER.id: STAG_HUNT_ENCOUNTER,
    JUICE_STALL_ENCOUNTER.id: JUICE_STALL_ENCOUNTER,
}
