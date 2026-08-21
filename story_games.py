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
    # "simple" (default): one choice, one resolve() call, like every
    # chapter below. "centipede": the one chapter (5) with more than one
    # sequential decision point — main.py branches its choice-phase
    # rendering on this instead of forcing a multi-turn game through the
    # single-choice UI everything else uses.
    kind: str = "simple"


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
#
# Four contribution levels rather than a binary in/out (Rs 0 / 25 / 50 /
# 100) — direct feedback asking for more choices to make the decision feel
# harder. Verified before adding them that dominance survives the extra
# granularity rather than assuming it: net(c) = floor(2c/5) - c is linear
# in c for any multiple of 5, so EVERY row is strictly worse than the one
# above it in BOTH columns (0 > -15 > -30 > -60 free-riding; 160 > 145 >
# 130 > 100 if the other four contribute) — contributing nothing remains
# the unique dominant choice, and now the table also shows the added
# insight that partial "hedging" contributions still lose money in
# proportion to how much you put in, not just the extremes.
# ---------------------------------------------------------------------------

_ROAD_FUND_N = 5          # you + 4 other shopkeepers
_ROAD_FUND_SHARE = 100     # the "fair share" ask per shopkeeper
_ROAD_FUND_OTHERS_TOTAL = 0  # the other 4 shopkeepers' fixed (rational) contribution

# choice id -> rupee amount, ascending — the single source of truth for
# both the resolve() math and the matrix built from it below.
_ROAD_FUND_CHOICE_AMOUNTS = {
    "free_ride": 0,
    "contribute_25": 25,
    "contribute_50": 50,
    "contribute": _ROAD_FUND_SHARE,
}


def _road_fund_net(contribution: int, others_total: int) -> tuple[int, int, int]:
    shopkeeper_total = contribution + others_total
    merchant_match = shopkeeper_total  # matches the shopkeepers' total, rupee for rupee
    road_fund = shopkeeper_total + merchant_match
    share_each = road_fund // _ROAD_FUND_N
    return share_each - contribution, road_fund, share_each


_ROAD_FUND_MATRIX = PayoffMatrix(
    row_label="You",
    col_label="The other 4 shopkeepers",
    row_options=[
        # Short enough to stay on one line each — "Contribute nothing"
        # wrapped to two, which alone forced every row in the table to
        # that same taller height and pushed the 4-row table (up from 2)
        # past the bottom of the fixed-size window on the lesson page.
        "Nothing",
        "Rs 25",
        "Rs 50",
        f"Rs {_ROAD_FUND_SHARE}",
    ],
    col_options=["All free-ride", "All contribute"],
    cells={
        (i, j): PayoffCell(_road_fund_net(amount, others)[0])
        for i, amount in enumerate(_ROAD_FUND_CHOICE_AMOUNTS.values())
        for j, others in enumerate((0, _ROAD_FUND_SHARE * (_ROAD_FUND_N - 1)))
    },
)


def _resolve_road_fund(player_choice: str, rng: random.Random) -> EncounterOutcome:
    contribution = _ROAD_FUND_CHOICE_AMOUNTS[player_choice]
    net, road_fund, share_each = _road_fund_net(contribution, _ROAD_FUND_OTHERS_TOTAL)

    if contribution == 0:
        lines = [
            "You keep your money. The other four shopkeepers do the same.",
            "With nobody contributing, there's nothing for the merchant to "
            "match, and no road fund at all — the road stays exactly as "
            "broken as it was.",
        ]
    else:
        lines = [
            f"You put in Rs {contribution} toward the repair. The other four "
            "shopkeepers quietly hold onto theirs.",
            f"The merchant matches the group's total, so the fund comes to "
            f"Rs {road_fund} — split five ways, that's Rs {share_each} back "
            "to each shopkeeper, including the four who paid nothing.",
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
             "It's your turn to decide: how much of your own money — "
             "nothing, a token amount, half your share, or the full "
             f"Rs {_ROAD_FUND_SHARE} — goes toward the road?"),
    ],
    choices=[
        EncounterChoice("free_ride", "Contribute nothing", "Keep your money — let the others cover it."),
        EncounterChoice("contribute_25", "Contribute a token amount (Rs 25)", "Hedge your bet — commit a little without risking much."),
        EncounterChoice("contribute_50", "Contribute half your share (Rs 50)", "Meet them halfway — a bigger gesture, a bigger risk."),
        EncounterChoice("contribute", f"Contribute your full share (Rs {_ROAD_FUND_SHARE})", "Trust that this pays off for everyone, including you."),
    ],
    resolve=_resolve_road_fund,
    quiz=QuizQuestion(
        prompt="Why does contributing ANY amount toward the fund cost you money personally, even with the merchant matching every rupee?",
        options=[
            "You only ever get back your equal 1-in-5 slice of the fund — about 2/5 of whatever you put in — so contributing more just loses you more, no matter what anyone else does; holding back completely is your dominant strategy.",
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
                # Trimmed to 2 tight paragraphs, not 3 — the mechanics
                # (merchant's match, equal split) are already covered in
                # setup_steps above, so repeating them here in full just
                # pushed the now-4-row table (up from 2) past the bottom
                # of the fixed-size window. See the row_options comment
                # on _ROAD_FUND_MATRIX for the matching fix on that side.
                "This is a bigger version of the same trap as the market "
                "supplier — except now there are five of you, and your "
                "payoff depends on what EVERYONE puts in, not just one "
                "other person. Every rupee you contribute only sends 2/5 "
                "of a rupee back to you personally; the rest subsidizes "
                "the other four.",
                "Look at the table: moving down the rows — Rs 25, Rs 50, "
                "Rs 100 — only ever makes your payoff worse, whether the "
                "other four free-ride or all chip in. No 'hedge' amount "
                "beats contributing nothing — a dominant strategy, the "
                "same idea as Chapter 1, across five people instead of "
                "two.",
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
#
# A third, middle option (direct feedback: "3 options — rabbit, bison,
# stag" instead of 2) — the classic extended framing of the hunting story
# this game is named after: hunt a rabbit alone (small, safe, guaranteed),
# hunt a bison with partial help (a real middle ground), or hunt a stag
# together (the biggest prize, but only if your partner truly commits).
# Verified algebraically before writing narrative, not just added as a
# cosmetic third button:
#   - Exactly two genuine pure-strategy Nash equilibria survive adding the
#     middle option, at the same two cells as before (Rabbit+Doesn't-build,
#     Stag+Builds) — Bison is never any player's best response to either
#     of the warehouse owner's pure choices, so it doesn't create a third,
#     spurious equilibrium.
#   - Bison is nonetheless a genuine, non-decorative choice: computing
#     expected value against a BELIEF (rather than certainty) about the
#     warehouse owner's move shows Bison is uniquely optimal for any
#     belief that he builds with probability roughly 0.5-0.62 — a real
#     hedge for a player who isn't sure yet, not just a trap option. Once
#     the warehouse owner's actual (deterministic, risk-averse) behavior
#     is revealed, Rabbit turns out to have been strictly best all along.
# ---------------------------------------------------------------------------

_STAG_HUNT_PAYOFFS = {
    # (farmer_choice, supplier_choice): (farmer_payoff, supplier_payoff)
    ("import_special", "build"): (150, 150),
    ("import_special", "no_build"): (-100, 40),
    ("import_bison", "build"): (100, 60),
    ("import_bison", "no_build"): (-20, 40),
    ("import_regular", "build"): (40, -80),
    ("import_regular", "no_build"): (40, 40),
}

_STAG_HUNT_MATRIX = PayoffMatrix(
    row_label="You",
    col_label="Warehouse owner",
    # Short, single-line labels on purpose — a longer phrasing like "Import
    # regular produce" wraps to two lines and forces every row in the
    # table to that taller height, which is exactly what pushed Chapter
    # 2's table (and its own "Next" button) past the bottom of the window
    # once a third row was added. See that chapter's fix for the same bug.
    row_options=["Regular produce", "Bison melons", "Special greens"],
    col_options=["Builds cold storage", "Doesn't build"],
    cells={
        (0, 0): PayoffCell(*_STAG_HUNT_PAYOFFS[("import_regular", "build")]),
        (0, 1): PayoffCell(*_STAG_HUNT_PAYOFFS[("import_regular", "no_build")]),
        (1, 0): PayoffCell(*_STAG_HUNT_PAYOFFS[("import_bison", "build")]),
        (1, 1): PayoffCell(*_STAG_HUNT_PAYOFFS[("import_bison", "no_build")]),
        (2, 0): PayoffCell(*_STAG_HUNT_PAYOFFS[("import_special", "build")]),
        (2, 1): PayoffCell(*_STAG_HUNT_PAYOFFS[("import_special", "no_build")]),
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
    elif player_choice == "import_bison":
        lines = [
            "You bring in a smaller batch of bison melons — rare, but "
            "sturdier than the hill greens, and only partly dependent on "
            "proper cold storage.",
            "The warehouse owner never builds it. Without any cooling at "
            "all, more of the batch spoils than you'd hoped, and what's "
            "left barely covers what you paid for it.",
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
        Step("idea", "Three ways to bet",
             "There's also a middle option: bison melons, a rarer fruit "
             "that's sturdier than the hill greens — some spoilage without "
             "cold storage, not a total loss. It's like the old hunting "
             "story this game is named for: hunt a rabbit alone and you're "
             "guaranteed something small; hunt a bison and you'll manage "
             "even without help, just not much; hunt a stag and you either "
             "feast together or come home with nothing."),
        Step("scale", "Your move", "What do you do?"),
    ],
    choices=[
        EncounterChoice("import_special", "Import the special greens (the stag)", "Big reward if the cold storage gets built — a real loss if it doesn't."),
        EncounterChoice("import_bison", "Import bison melons (the bison)", "A middle ground — some loss without cold storage, not a wipeout."),
        EncounterChoice("import_regular", "Stick with your regular produce (the rabbit)", "Smaller, steady profit no matter what he decides."),
    ],
    resolve=_resolve_stag_hunt,
    quiz=QuizQuestion(
        prompt="Why does importing anything beyond your regular produce carry real risk here, when Chapter 1's 'safe' choice was always correct regardless of the other side?",
        options=[
            "Because this game has no dominant strategy — the right move depends entirely on what the other person does, and reaching for a bigger opportunity is a bet on trust that doesn't always pay off.",
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
                "greens or the bison melons isn't always right or wrong; "
                "it's only a good move if the warehouse owner commits too.",
                "This structure is called a Stag Hunt, from an old "
                "hunting story with exactly the three options you just "
                "had: a rabbit alone (small, safe, guaranteed), a bison "
                "with partial help (a real middle ground), or a stag "
                "together (the biggest reward — only if your partner "
                "truly commits too).",
                "Look at the matrix: bottom row, left column — both "
                "committing to the stag — is the best outcome for both "
                "of you. Top row, right column — both playing it safe — "
                "is fine for both. Anything else costs someone.",
            ],
            show_matrix=True,
        ),
        LessonPage(
            concept_name="Two Nash Equilibria",
            lines=[
                "Despite three options on the table, this game still has "
                "exactly TWO stable outcomes, both highlighted below: "
                "mutual commitment to the stag (best for both) and mutual "
                "caution with regular produce (safe, but leaves value on "
                "the table).",
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
            highlight_cells=[(0, 1), (2, 0)],
        ),
        LessonPage(
            concept_name="Why the Middle Ground Never Wins Outright",
            lines=[
                "The bison melons look like a sensible hedge — some risk, "
                "but not all of it. Yet check the matrix: bison is never "
                "the BEST reply to either of the warehouse owner's two "
                "possible moves. If he's building, you'd do better with "
                "the stag; if he isn't, you'd do better with the rabbit. "
                "A 'safe middle' option that's never anyone's best "
                "response can't be a Nash equilibrium.",
                "It's still a genuinely reasonable bet if you're not sure "
                "which way he'll go: worked out as an expected value, "
                "bison actually beats both other options for any belief "
                "that he's roughly 50-62% likely to build. It's a real "
                "hedge under real uncertainty, not just a trap for the "
                "indecisive.",
                "But the warehouse owner in this story isn't uncertain — "
                "he's a fixed, risk-averse 'no' every time, the same as "
                "every other deterministic opponent you've faced so far. "
                "Once his behavior is known rather than merely believed, "
                "hedging stops paying: the rabbit was strictly best "
                "all along.",
            ],
            show_matrix=True,
            highlight_row=1,
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


# ---------------------------------------------------------------------------
# Chapter 6: the same supplier, all season.
#
# The iterated Prisoner's Dilemma — literally the same stage game as
# Chapter 1 (this Encounter reuses _QUALITY_PRICE_MATRIX and
# _QUALITY_PRICE_PAYOFFS unchanged), but played repeatedly against the same
# supplier instead of once. That repetition is what changes the incentives:
# a one-shot dominant strategy to defect no longer dominates once your
# current move can be answered by the same opponent next round.
#
# Rather than one player move, the player picks a whole-season STRATEGY
# (EncounterChoice options below); resolve() actually simulates 8 rounds
# against a fixed Tit-for-Tat supplier (cooperate first, then mirror the
# player's last OBSERVED move) with a real 10% chance, applied independently
# every round to both sides, that an intended "pay/deliver fairly" (C) is
# miscommunicated and observed as a shortchange/cut-corners (D) — noise never
# turns a D into a C, only ever the reverse, matching "a cooperative move is
# miscommunicated as a defection." Both sides react to what was actually
# OBSERVED, not what was intended, which is what lets a single bad-luck
# misread cascade into real distrust for strategies that don't forgive it.
#
# Verified by direct simulation (not asserted from theory) before writing
# any of the numbers below into the lesson: across 4000 seeded 8-round runs,
# mean player totals were Always Distrust -52.6, Grim Trigger 166.5,
# Tit-for-Tat 200.7, Forgiving Tit-for-Tat 261.9 — the intended ranking, and
# Always Distrust is a net LOSS on average despite winning its first round
# by exploiting the supplier's initial trust, because from round 2 on the
# supplier mirrors right back and both sides are stuck at the mutual-defect
# payoff (-20) for the rest of the season. A separate check across longer
# horizons (20, 40 rounds) confirmed Tit-for-Tat's edge over Grim Trigger
# widens the longer the relationship runs — Grim Trigger's one uncorrectable
# trigger costs it more the longer it has to live with the fallout.
# ---------------------------------------------------------------------------

_ITERATED_NOISE = 0.10
_ITERATED_ROUNDS = 8


def _opponent_move(player_history: list[str]) -> str:
    # Tit-for-Tat, supplier's side: cooperate first, then mirror the
    # player's last OBSERVED move — same shape as every other chapter's
    # deterministic opponent, just now a function of history instead of a
    # single fixed choice.
    return "C" if not player_history else player_history[-1]


def _player_move(strategy: str, player_history: list[str], opp_history: list[str]) -> str:
    if strategy == "always_distrust":
        return "D"
    if strategy == "tit_for_tat":
        return "C" if not opp_history else opp_history[-1]
    if strategy == "grim_trigger":
        return "D" if "D" in opp_history else "C"
    if strategy == "forgiving_tft":  # defects only after TWO straight observed defections
        if len(opp_history) < 2:
            return "C"
        return "D" if opp_history[-1] == "D" and opp_history[-2] == "D" else "C"
    raise ValueError(strategy)


def _apply_noise(intended: str, rng: random.Random) -> tuple[str, bool]:
    if intended == "C" and rng.random() < _ITERATED_NOISE:
        return "D", True
    return intended, False


def _resolve_iterated_pd(player_choice: str, rng: random.Random) -> EncounterOutcome:
    player_history: list[str] = []   # observed (post-noise) actions, both sides
    opp_history: list[str] = []
    total = 0
    lines = ["You settle on your approach for the whole season and stick with it."]

    for round_num in range(1, _ITERATED_ROUNDS + 1):
        p_intended = _player_move(player_choice, player_history, opp_history)
        o_intended = _opponent_move(player_history)
        p_actual, p_noisy = _apply_noise(p_intended, rng)
        o_actual, o_noisy = _apply_noise(o_intended, rng)

        payoff = _QUALITY_PRICE_PAYOFFS[
            ("pay_high" if p_actual == "C" else "pay_low", "high_quality" if o_actual == "C" else "low_quality")
        ][0]
        total += payoff

        if p_noisy:
            you = "you mean to pay him fairly, but a counting mix-up makes it look like you shorted him"
        else:
            you = "you pay him fairly" if p_actual == "C" else "you lowball him"
        if o_noisy:
            him = "he means to deliver quality, but a bad batch slips through looking like he cut corners"
        else:
            him = "he delivers quality" if o_actual == "C" else "he cuts corners"
        lines.append(f"Round {round_num}: {you.capitalize()}; {him}. {payoff:+d} rupees.")

        player_history.append(p_actual)
        opp_history.append(o_actual)

    lines.append(f"Total across the season: {total:+d} rupees.")
    return EncounterOutcome(player_payoff=total, result_lines=lines)


ITERATED_PD_ENCOUNTER = Encounter(
    id="iterated_pd",
    chapter_title="Chapter 6: The Same Supplier, All Season",
    setup_steps=[
        Step("trade", "Same supplier",
             "The wood supplier from your very first stall is still in "
             "business — and this season, you need materials from him "
             "again. Not just once this time: deliveries, all season long."),
        Step("cycle", "Repeat business",
             "Unlike that first deal, this isn't a one-time transaction. "
             "How you treat each other over many exchanges shapes how the "
             "rest of the season goes — for both of you."),
        Step("warning", "Mix-ups happen",
             "Deliveries aren't perfect. Even an honest attempt at doing "
             "right by each other can get miscommunicated — a good batch "
             "mislabeled, a fair payment that looks short over a counting "
             "error. About 1 in 10 exchanges gets garbled this way."),
        Step("idea", "Pick your approach",
             "You can't decide fresh every single delivery — you need a "
             "standing approach for the whole season, chosen before you "
             "know how any of it plays out."),
        Step("scale", "Your move",
             "How do you want to handle him, delivery after delivery?"),
    ],
    choices=[
        EncounterChoice("always_distrust", "Always lowball him",
                         "Never trust him — pay the low price every single time, no matter what."),
        EncounterChoice("tit_for_tat", "Match his last delivery",
                         "Pay fair the first time. After that, do exactly what he did last time."),
        EncounterChoice("grim_trigger", "Trust him — until he burns you once",
                         "Pay fair every time, unless he ever cuts corners — then never again, all season."),
        EncounterChoice("forgiving_tft", "Match him, but forgive a single slip",
                         "Same as matching his last delivery, but only turn on him after TWO cut-corner "
                         "deliveries in a row — one bad batch could just be a mix-up."),
    ],
    resolve=_resolve_iterated_pd,
    quiz=QuizQuestion(
        prompt="Why does a single miscommunication hurt 'trust him until he burns you once' far worse than "
               "the strategies that can forgive a single slip?",
        options=[
            "Because once triggered by even one misread delivery, it never forgives — locking both sides into "
            "permanent mutual punishment, while a forgiving strategy can recover once trust resumes.",
            "Because it costs more rupees upfront than the other approaches.",
            "Because the supplier always secretly favors whichever approach forgives him.",
        ],
        correct_index=0,
    ),
    matrix=_QUALITY_PRICE_MATRIX,
    chapter_icon="cycle",
    lesson_pages=[
        LessonPage(
            concept_name="Iterated Prisoner's Dilemma",
            lines=[
                "Look closely at the matrix below — it's the exact same "
                "numbers as your very first deal with this supplier back "
                "in Chapter 1. What's different this time is that you're "
                "not playing it once. You're playing it 8 times in a row, "
                "against the same person.",
                "In a one-shot Prisoner's Dilemma, defecting is always the "
                "dominant move — there's no tomorrow to answer for it. "
                "Repetition changes that: your move today can be answered "
                "next round, so a strategy that rewards trust and punishes "
                "betrayal can sustain cooperation that a single round never "
                "could.",
                "This is sometimes called 'the shadow of the future' — "
                "what keeps people, businesses, and even countries honest "
                "with each other isn't goodwill alone, it's knowing there's "
                "a next round.",
            ],
            show_matrix=True,
        ),
        LessonPage(
            concept_name="Reputation, Noise, and Forgiveness",
            lines=[
                "Always lowballing him won a big first round — he trusted "
                "you and delivered quality, so you profited off that trust "
                "immediately. But from round 2 on, he mirrors right back: "
                "you're both stuck cutting corners on each other for the "
                "rest of the season. Simulated over many seasons, that "
                "opening win doesn't come close to covering the cost — "
                "'always distrust' loses money on average, once the whole "
                "season is counted.",
                "'Trust him until he burns you once' starts the same as "
                "matching his last delivery, but it never recovers from a "
                "single misread — including an honest mix-up. One bad "
                "batch, real or just miscommunicated, and you're both "
                "locked into cutting corners on each other for every "
                "remaining round.",
                "Forgiving a single slip does best of all: it reacts to "
                "betrayal exactly like matching his last delivery does, but "
                "shrugs off one-off miscommunication instead of treating it "
                "as a permanent break. In a world where mistakes happen 1 "
                "in 10 times, being willing to forgive a single slip — "
                "without being a pushover for repeated ones — is what "
                "actually protects a long-term relationship, not blind "
                "trust and not permanent suspicion.",
            ],
            show_matrix=False,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Chapter 5: the two-cart deal.
#
# The Centipede Game — sequential moves and backward induction. A pot of
# money grows every time it's passed along instead of taken; whoever takes
# it keeps the whole thing, ending the game immediately. Alternating turns,
# player first: Player, NPC, Player, NPC, Player, NPC (3 player decisions).
#
# The NPC (a rival trader splitting a shared cart-hire deal with the
# player) is deterministically scripted to let it ride on its first two
# turns and take everything on its third and final turn — same
# deterministic-opponent discipline as every other chapter, chosen
# specifically so the game has a genuine 3-decision arc instead of
# collapsing to a trivial first move.
#
# Backward induction, verified by reasoning from the guaranteed final move:
# at the NPC's 3rd turn it always takes everything (scripted, not a real
# choice) — so at the player's 3rd turn, passing guarantees Rs 0 while
# taking guarantees the pot on the table, so a rational player always takes
# there. Knowing that, a rational NPC at ITS 2nd turn should also prefer
# taking over passing into a turn where the player will just take anyway —
# and reasoning keeps unraveling backward the same way a purely rational
# NPC would, all the way to the player's very first move. That's the
# textbook result: pure backward induction says take immediately, on the
# very first turn, for the smallest pot on the table. What actually
# happens in this scenario — an opponent who lets it ride twice, tempting
# the player to do the same, before snapping up the final pot — is the gap
# between that theoretical prediction and how these games actually play
# out in practice, which is the whole point of the chapter.
# ---------------------------------------------------------------------------

CENTIPEDE_POT_START = 20
# Pot available to TAKE at each of the player's 3 decision points — each
# double the last, since a pass doubles the pot twice (the player's own
# pass, then the NPC's automatic one) before it's the player's turn again.
CENTIPEDE_PLAYER_POTS = [20, 80, 320]
# What the NPC claims for itself if the player passes all 3 times.
CENTIPEDE_FINAL_POT = 640

_CENTIPEDE_MATRIX = PayoffMatrix(
    row_label="Your decision",
    col_label="Outcome",
    row_options=["Take on turn 1 (Rs 20)", "Take on turn 2 (Rs 80)", "Take on turn 3 (Rs 320)", "Never take"],
    col_options=["Your payoff"],
    cells={
        (0, 0): PayoffCell(CENTIPEDE_PLAYER_POTS[0]),
        (1, 0): PayoffCell(CENTIPEDE_PLAYER_POTS[1]),
        (2, 0): PayoffCell(CENTIPEDE_PLAYER_POTS[2]),
        (3, 0): PayoffCell(0),
    },
)


def _resolve_centipede(choice_id: str, rng: random.Random) -> EncounterOutcome:
    if choice_id == "take1":
        payoff = CENTIPEDE_PLAYER_POTS[0]
        lines = [
            f"You take the Rs {payoff} on the table right now, before he gets a turn at all.",
            f"Net effect on your business: {payoff:+d} rupees.",
        ]
    elif choice_id == "pass_take3":
        payoff = CENTIPEDE_PLAYER_POTS[1]
        lines = [
            "You let it ride once — and rather than grab the smaller pot himself, he lets it ride too.",
            f"On your second turn, with the pot at Rs {payoff}, you decide not to push your luck again — you take it.",
            f"Net effect on your business: {payoff:+d} rupees.",
        ]
    elif choice_id == "pass_pass_take5":
        payoff = CENTIPEDE_PLAYER_POTS[2]
        lines = [
            "You let it ride twice, and both times, so does he.",
            f"On your third turn, with the pot swollen to Rs {payoff}, that's enough for you — you take it.",
            f"Net effect on your business: {payoff:+d} rupees.",
        ]
    else:  # "pass_pass_pass"
        payoff = 0
        lines = [
            "You let it ride all three times you had the chance, hoping he'd keep letting it ride too.",
            f"He doesn't. On his final turn, with the pot swollen to Rs {CENTIPEDE_FINAL_POT}, he takes every "
            "rupee of it for himself and walks away.",
            f"Net effect on your business: {payoff:+d} rupees.",
        ]
    return EncounterOutcome(player_payoff=payoff, result_lines=lines)


CENTIPEDE_ENCOUNTER = Encounter(
    id="centipede",
    chapter_title="Chapter 5: The Two-Cart Deal",
    setup_steps=[
        Step("idea", "A shared opportunity",
             "A rival trader proposes splitting the hire of a big cart for "
             "this week's harvest run — cheaper for both of you than "
             "hiring separately, and there's a shared kitty of savings "
             "from it, sitting on the table between you."),
        Step("pot", "The kitty can grow",
             f"Right now the kitty holds Rs {CENTIPEDE_POT_START}. Either of "
             "you can take it all for yourself right now, ending the deal "
             "— or let it ride, which doubles it, and passes the choice to "
             "the other person."),
        Step("question", "Turns alternate",
             "You go first. Then him, if you let it ride. Then you again, "
             "if he lets it ride too — back and forth, the kitty doubling "
             "each time, until someone finally takes it."),
        Step("warning", "Whoever takes it keeps it",
             "Taking ends the deal immediately — whoever takes it keeps "
             "the WHOLE kitty for themselves, and the other person gets "
             "nothing from it at all."),
        Step("scale", "Your move",
             f"The kitty is at Rs {CENTIPEDE_POT_START}. It's your turn."),
    ],
    choices=[],  # Chapter 5 walks through 3 sequential turns instead of one
    # choice list — see main.py's _draw_centipede_step / kind="centipede".
    resolve=_resolve_centipede,
    quiz=QuizQuestion(
        prompt="If you assume your rival plays perfectly rationally at every turn — including his very last "
               "one — why does backward induction say YOU should take the small pot immediately, turn 1?",
        options=[
            "Because at the final turn, a rational rival keeps the whole pot for himself — so reasoning "
            "backward from there, every earlier turn unravels to the same conclusion: take now, before it "
            "becomes someone else's turn to take everything.",
            "Because the kitty doesn't actually grow — it's a fixed amount split evenly no matter what.",
            "Because taking on turn 1 is required by the rules of the deal.",
        ],
        correct_index=0,
    ),
    matrix=_CENTIPEDE_MATRIX,
    chapter_icon="pot",
    kind="centipede",
    lesson_pages=[
        LessonPage(
            concept_name="The Centipede Game",
            lines=[
                "This is called a Centipede Game — a chain of turns where "
                "passing grows a shared pot, but taking ends everything "
                "immediately and keeps it all for whoever took it.",
                "Look at the table: waiting longer to take pays off BIG, "
                "right up until the moment your rival decides to grab it "
                "all instead of letting it ride — and then it's zero.",
                "That tension — a growing reward against the risk that "
                "someone else grabs it all first — is the whole game.",
            ],
            show_matrix=True,
        ),
        LessonPage(
            concept_name="Backward Induction",
            lines=[
                "Work it out from the END instead of the start. On the "
                "very last possible turn, a purely rational player always "
                "takes everything — there's no future turn left to protect "
                "by waiting.",
                "Knowing that, the turn right before it is just as clear: "
                "letting it ride only hands a certain zero to a rational "
                "opponent who's about to take it all anyway — so you should "
                "take there too. That reasoning keeps unraveling backward, "
                "one turn at a time, all the way to the very first move.",
                "The conclusion holds even though it feels wrong: pure "
                "backward induction says take the small pot immediately, "
                "on turn 1 — before your opponent, reasoning the exact same "
                "way, gets the chance to. What actually happened in this "
                "scenario — an opponent willing to let it ride, at least "
                "twice, tempting you to keep pushing your luck — is real "
                "behavior diverging from that cold theoretical prediction, "
                "which is what real experiments with this exact game "
                "consistently find: most people don't take immediately, "
                "even though the theory says they should.",
            ],
            show_matrix=False,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Chapter 7: the cow you can't inspect.
#
# Adverse selection — Akerlof's "Market for Lemons," played from the
# UNINFORMED side this time: the player is buying a milking cow whose true
# quality (Good vs Lemon) only the seller knows. Deterministic, like every
# other chapter's opponent, but the mechanism here is starker than a single
# scripted response: the market has already fully unraveled BEFORE the
# player ever makes an offer, because genuinely Good-cow owners rationally
# stay out of a market where buyers can't verify quality and so won't pay
# what a Good cow is really worth. That means no price the player offers —
# "fair" or generous — brings a Good cow to market; every price only
# clears Lemon owners, so paying MORE just means overpaying more for the
# same guaranteed Lemon. This is the sharpest, most teachable form of
# Akerlof's result (full unraveling to the lowest-quality equilibrium) and
# it sets up Chapter 8 directly: since price alone can't fix this, the
# player will need something OTHER than price next chapter.
#
# Numbers (all deterministic, verified before writing any narrative):
#   Good cow: worth Rs 400 to a buyer who could verify it; owner's minimum
#     acceptable price (its worth to them) Rs 300.
#   Lemon: worth Rs 80 to a buyer; owner's minimum acceptable price Rs 50.
#   Population the player believes they're facing: 50% Good, 50% Lemon, so
#     a naive "fair average" offer = 0.5*400 + 0.5*80 = Rs 240.
# A Good owner's Rs 300 floor is ABOVE that "fair average" offer, so they
# never sell to a buyer who can't tell them apart from a Lemon — that's the
# unraveling, not a coincidence of these particular numbers: verified this
# holds for offer <= 300, i.e. any offer a buyer would consider "fair" or
# even generous-but-not-reckless still can't clear a genuine owner's floor
# once buyers are assumed unable to verify quality. Net effects: Fair offer
# (Rs 240) still gets a Lemon: 80-240 = -160. Premium offer (Rs 320,
# genuinely above the Good owner's floor) STILL only gets a Lemon in this
# scenario, because Good owners have already priced themselves out of ever
# trusting an unverified buyer's offer at all, so a bigger number doesn't
# lure them back — it just costs more for the same Lemon: 80-320 = -240.
# Walking away nets exactly 0. Dominance verified: 0 > -160 > -240.
# ---------------------------------------------------------------------------

_LEMON_GOOD_VALUE = 400
_LEMON_LEMON_VALUE = 80
_LEMON_FAIR_OFFER = 240
_LEMON_PREMIUM_OFFER = 320

_LEMONS_MATRIX = PayoffMatrix(
    row_label="Your offer",
    col_label="What actually sells to you",
    row_options=["Fair average (Rs 240)", "Premium (Rs 320)", "Walk away"],
    col_options=["A Lemon — the only kind selling"],
    cells={
        (0, 0): PayoffCell(_LEMON_LEMON_VALUE - _LEMON_FAIR_OFFER),
        (1, 0): PayoffCell(_LEMON_LEMON_VALUE - _LEMON_PREMIUM_OFFER),
        (2, 0): PayoffCell(0),
    },
)


def _resolve_lemons_market(player_choice: str, rng: random.Random) -> EncounterOutcome:
    if player_choice == "walk_away":
        lines = [
            "You decide you can't tell a good cow from a sick one here, "
            "and no price fixes that — so you walk away and keep looking "
            "elsewhere.",
            "Net effect on your business: +0 rupees.",
        ]
        return EncounterOutcome(player_payoff=0, result_lines=lines)

    offer = _LEMON_FAIR_OFFER if player_choice == "fair_offer" else _LEMON_PREMIUM_OFFER
    net = _LEMON_LEMON_VALUE - offer
    offer_desc = "what seems like a fair average price" if player_choice == "fair_offer" else "a generous, above-average price"
    lines = [
        f"You offer {offer_desc} — Rs {offer} — for a cow, assuming you'll "
        "get something close to an average animal.",
        "But the owner of any genuinely healthy cow already knows buyers "
        "here can't tell their animal apart from a sickly one — so they "
        "never bothered listing it at a price like yours in the first "
        "place. Only the owners of sickly cows are willing sellers, no "
        "matter what you offer.",
        f"You end up with a sickly cow worth only about Rs {_LEMON_LEMON_VALUE} "
        f"to you, having paid Rs {offer} for it.",
        f"Net effect on your business: {net:+d} rupees.",
    ]
    return EncounterOutcome(player_payoff=net, result_lines=lines)


LEMONS_MARKET_ENCOUNTER = Encounter(
    id="lemons_market",
    chapter_title="Chapter 7: The Cow You Can't Inspect",
    setup_steps=[
        Step("idea", "Time to expand",
             "Business is good enough that you're ready to expand — a "
             "milking cow would add a steady new line of income to your "
             "farm."),
        Step("question", "Can't tell by looking",
             "At the cattle market, cows look healthy enough on the "
             "surface. But some are genuinely strong milkers, and some are "
             "quietly sickly in ways that won't show for weeks — only the "
             "seller actually knows which is which."),
        Step("warning", "The good ones may be missing",
             "Owners of a genuinely healthy cow know buyers here can't "
             "tell their animal apart from a sickly one. If they can't get "
             "paid what it's really worth, why would they sell it here at "
             "all?"),
        Step("lemon", "A market that knows itself",
             "That means the cows actually being offered to you may "
             "already be skewed toward the sickly ones, before you even "
             "make an offer."),
        Step("scale", "Your move",
             "How much do you offer — and does offering more even help?"),
    ],
    choices=[
        EncounterChoice("fair_offer", "Offer a fair average price (Rs 240)",
                         "Assume roughly half the cows here are healthy, and pay accordingly."),
        EncounterChoice("premium_offer", "Offer a generous price (Rs 320)",
                         "Pay well above average, hoping it attracts a genuinely healthy cow."),
        EncounterChoice("walk_away", "Walk away",
                         "You can't verify quality here at any price — so don't buy."),
    ],
    resolve=_resolve_lemons_market,
    quiz=QuizQuestion(
        prompt="Why did offering MORE money not get you a healthier cow?",
        options=[
            "Because genuinely healthy cows had already been withheld from a market where buyers can't verify "
            "quality — no offer brings them back, so a bigger number just overpays for the same sickly cow.",
            "Because the seller pocketed the difference and gave you the same cow either way.",
            "Because paying more is against the rules of this market.",
        ],
        correct_index=0,
    ),
    matrix=_LEMONS_MATRIX,
    chapter_icon="lemon",
    lesson_pages=[
        LessonPage(
            concept_name="Adverse Selection (The Market for Lemons)",
            lines=[
                "Economist George Akerlof named this after used cars: "
                "buyers can't tell a good car from a 'lemon' before buying "
                "it, so they'll only pay an average price reflecting both. "
                "But that average price is too low for genuinely good "
                "cars' owners to bother selling at — so they leave the "
                "market, dragging the average quality (and the average "
                "price buyers will pay) down further. Left unchecked, this "
                "spiral can unravel a whole market to nothing but lemons.",
                "Look at the table: every offer nets you a Lemon here — "
                "the healthy cows were never on the table to begin with, "
                "for a buyer who can't tell them apart from a sick one.",
            ],
            show_matrix=True,
        ),
        LessonPage(
            concept_name="Why Price Alone Can't Fix It",
            lines=[
                "It's tempting to think 'just pay more' solves this — but "
                "the table shows the opposite: Rs 320 lost you MORE money "
                "than Rs 240, for the exact same sickly cow. Paying more "
                "doesn't summon a healthy cow into the market; it just "
                "raises what you lose on the only cow actually being sold "
                "to you.",
                "This is the real bite of adverse selection: unlike "
                "Chapter 1's dilemma, where paying more at least bought a "
                "*chance* at quality, here NO price fixes the underlying "
                "problem, because the problem isn't the price — it's that "
                "buyers have no way to verify what they're actually "
                "getting.",
                "Walking away was the only choice that didn't lose money "
                "— but that's not a real solution either; it just avoids "
                "the trap instead of fixing it. Fixing it takes something "
                "other than a bigger number, which is exactly the problem "
                "the next chapter takes on, from the other side of this "
                "same kind of market.",
            ],
            show_matrix=False,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Chapter 8: proving the goat is worth it.
#
# Signaling — the direct answer to Chapter 7's trap, played from the
# INFORMED side this time. The player has raised a genuinely prize goat and
# knows it, but buyers can't verify that any better than Chapter 7's cattle
# buyer could. Chapter 7 showed that price alone can't fix this; here the
# fix is a COSTLY, VERIFIABLE signal (a vet certification) — costly enough
# that it only makes sense for someone who actually has the quality to back
# it up.
#
# Numbers (verified before writing the narrative): pooling price (what an
# unverified goat sells for, buyers assuming an average mix of genuine and
# ordinary animals) = Rs 300. A genuine prize goat's true, verified value =
# Rs 500. An ordinary goat's true, verified value = Rs 100. Certification
# costs a flat Rs 120. For the player's ACTUAL (genuinely prize) goat:
# certify nets 500-120=380 > pooling's 300 — worth it. The lesson also
# checks the case the player ISN'T in, to establish the signal's
# credibility: if the goat were merely ordinary, certifying would net
# 100-120=-20, far worse than just pooling at 300 — so an ordinary-goat
# owner would never rationally pay for this same certificate. That gap is
# exactly what makes the certificate credible to a buyer in the first
# place: only genuine quality can afford to prove itself this way. This is
# a real, named result (Spence signaling / Akerlof-Spence-Stiglitz, the
# same body of work Chapter 7 introduced) verified with actual numbers, not
# asserted from theory alone.
# ---------------------------------------------------------------------------

_SIGNAL_POOLING_PRICE = 300
_SIGNAL_PRIZE_VALUE = 500
_SIGNAL_ORDINARY_VALUE = 100
_SIGNAL_CERT_COST = 120


def _resolve_goat_signal(player_choice: str, rng: random.Random) -> EncounterOutcome:
    if player_choice == "no_signal":
        net = _SIGNAL_POOLING_PRICE
        lines = [
            "You sell the goat as-is, no certification. Buyers can't tell "
            "it apart from an ordinary animal, so it fetches only the "
            "going average price.",
            f"Net effect on your business: {net:+d} rupees.",
        ]
    else:
        net = _SIGNAL_PRIZE_VALUE - _SIGNAL_CERT_COST
        lines = [
            f"You pay a vet Rs {_SIGNAL_CERT_COST} for a proper certified "
            "inspection, then take the paperwork to market with the goat.",
            "Buyers can now verify what you already knew — this is "
            "genuinely prize stock — and pay accordingly, instead of "
            "guessing at an average.",
            f"Net effect on your business: {net:+d} rupees.",
        ]
    return EncounterOutcome(player_payoff=net, result_lines=lines)


GOAT_SIGNAL_ENCOUNTER = Encounter(
    id="goat_signal",
    chapter_title="Chapter 8: Proving The Goat Is Worth It",
    setup_steps=[
        Step("idea", "A genuine prize",
             "Months of careful breeding have paid off: you've raised a "
             "genuinely exceptional goat, clearly the best in your herd. "
             "You know it. The buyers at market don't."),
        Step("question", "Looks like any other goat",
             "To anyone just looking it over at the market, it's "
             "indistinguishable from an ordinary animal — the same "
             "problem you ran into buying that cow, except now you're the "
             "one holding the quality nobody can verify."),
        Step("lemon", "The same trap, flipped",
             "Buyers here have been burned by this before. Unless you can "
             "prove it, they'll only offer you the going average price — "
             "the same price an ordinary goat would fetch."),
        Step("certificate", "A costly way to prove it",
             "A traveling vet at the market offers certified quality "
             "inspections — real money, upfront, with no guarantee "
             "buyers even care. But it's a real, verifiable answer to "
             "'how do I know you're not just saying that?'"),
        Step("scale", "Your move",
             "Do you pay for the proof, or take the average price and "
             "move on?"),
    ],
    choices=[
        EncounterChoice("no_signal", "Sell it as-is",
                         "No certification — take the average market price, no upfront cost."),
        EncounterChoice("certify", f"Pay for certification (Rs {_SIGNAL_CERT_COST})",
                         "Prove what you already know, so buyers pay for what it's actually worth."),
    ],
    resolve=_resolve_goat_signal,
    quiz=QuizQuestion(
        prompt="Why would the owner of an ordinary, average-quality goat never bother paying for this same certification?",
        options=[
            "Because certifying an ordinary goat would cost more than it's actually worth once verified — "
            "it would only prove they're not worth much, for a net loss.",
            "Because the vet refuses to inspect ordinary goats.",
            "Because certification is illegal for anyone but prize animals.",
        ],
        correct_index=0,
    ),
    chapter_icon="certificate",
    lesson_pages=[
        LessonPage(
            concept_name="Signaling",
            lines=[
                "Chapter 7 showed that price alone can't fix a market "
                "where buyers can't verify quality — paying more doesn't "
                "summon better quality into view. This chapter is the "
                "other half of that same problem: if you're the one who "
                "actually HAS the quality, how do you prove it?",
                "The answer economist Michael Spence is known for: a "
                "costly, verifiable signal — something expensive enough, "
                "or hard enough to fake, that only genuine quality can "
                "afford to send it.",
                "Paying Rs 120 to certify a goat worth Rs 500 nets Rs 380 "
                "— clearly better than the Rs 300 pooling price you'd get "
                "unverified. The certificate paid for itself.",
            ],
            show_matrix=False,
        ),
        LessonPage(
            concept_name="What Makes a Signal Credible",
            lines=[
                "Here's the part that makes this actually work, not just "
                "a lucky guess: imagine your goat had been an ordinary "
                "one instead, worth only Rs 100 once verified. Certifying "
                "it would still cost Rs 120 — netting Rs -20, far worse "
                "than just taking the Rs 300 pooling price unverified.",
                "That means an ordinary-goat owner would never rationally "
                "pay for this certificate — it only makes sense for "
                "someone who actually has the quality to back it up. "
                "That's exactly why a buyer can trust it: the cost itself "
                "screens out anyone who'd be lying.",
                "This is the real fix for Chapter 7's trap — not a bigger "
                "price, but a signal too expensive for a lemon to fake. "
                "It's why real markets lean on warranties, certifications, "
                "credentials, and inspections: not as paperwork for its "
                "own sake, but because their cost is what makes them "
                "believable.",
            ],
            show_matrix=False,
        ),
    ],
)


# ---------------------------------------------------------------------------
# The finale briefing: rounds 9-10 (the connections game) aren't a scripted
# chapter with a fixed payoff table like 1-8 — they're the real Solo/
# Approach/Intelligence game (game_logic.py), played for real stakes
# against 15 other villagers. Direct feedback asked for the player to be
# told, in-story, why they suddenly need to network and how the mechanic
# they're about to feel actually works, the same way every chapter
# explains itself before and after the player commits to something.
#
# This is narrative-only — a setup storyboard (FINALE_INTRO_STEPS, shown
# once before round 9's first real action) and a wrap-up (FINALE_LESSON,
# shown once at the start of the round right after) — reusing the exact
# Step/LessonPage shapes every chapter already uses, but with no
# EncounterChoice/resolve() of its own, since the real mechanic already
# IS the game: there's no separate scripted payoff table to verify here,
# only a plain-language description of the one that already exists in
# game_logic.py's SkillRelationship odds, checked against the actual
# numbers below rather than asserted from memory:
#   SAME:          accept 70%, payoff +8 if it lands
#   ADJACENT:      accept 55%, payoff +16 if it lands
#   COMPLEMENTARY: accept 40%, payoff +28 if it lands
# Exactly the shape described: easiest with your own specialty, hardest
# with a fully complementary one, and the hardest deal is worth the most
# if it actually closes.
# ---------------------------------------------------------------------------

FINALE_INTRO_STEPS = [
    Step("warning", "Too much to run alone",
         "Your business has grown past what one person can juggle — the "
         "accounts, the day-to-day operations, and getting the word out "
         "are all pulling you in different directions at once."),
    Step("wheel", "Help is out there",
         "Fifteen other people in the village each bring a real "
         "specialty — Marketing, Creativity, Finance & Analytics, or "
         "Operations — but you don't know yet who's strong at what."),
    Step("question", "Finding out costs you",
         "You can Approach someone directly and try to team up, or "
         "quietly gather Intelligence on them first. Either way costs "
         "you money and time you'd otherwise spend running your own "
         "shop — there's no free way to find out, and no guarantee it "
         "works out."),
    Step("approach", "Same, adjacent, or complementary",
         "People who share your own specialty are the easiest to team "
         "up with — but you already know what they know. People whose "
         "skills complement yours completely are the hardest to "
         "convince, yet worth the most to you if it actually works out."),
    Step("scale", "Your move",
         "From here on, every round is a real decision — who do you "
         "approach, and is the risk worth it?"),
]

FINALE_LESSON = LessonPage(
    concept_name="Search and Matching Under Uncertainty",
    lines=[
        "This is a real, named problem in economics: when you can't "
        "observe someone's skill or reliability upfront, finding the "
        "right partner takes costly search, not just a decision.",
        "That search has a real trade-off built in. Approaching someone "
        "just like you is the safest bet — a high chance they say yes — "
        "but a match that only doubles what you already know isn't "
        "worth much. Someone whose skills complement yours completely "
        "is a much harder yes, but a real complementary partnership is "
        "worth far more than teaming up with your own mirror image.",
        "This is why job markets, business partnerships, and hiring all "
        "lean on costly signals of their own — resumes, referrals, "
        "trial projects — to cut down how much expensive searching it "
        "takes to find a good match.",
    ],
)


STORY_ENCOUNTERS: dict[str, Encounter] = {
    QUALITY_PRICE_ENCOUNTER.id: QUALITY_PRICE_ENCOUNTER,
    ROAD_FUND_ENCOUNTER.id: ROAD_FUND_ENCOUNTER,
    STAG_HUNT_ENCOUNTER.id: STAG_HUNT_ENCOUNTER,
    JUICE_STALL_ENCOUNTER.id: JUICE_STALL_ENCOUNTER,
    CENTIPEDE_ENCOUNTER.id: CENTIPEDE_ENCOUNTER,
    ITERATED_PD_ENCOUNTER.id: ITERATED_PD_ENCOUNTER,
    LEMONS_MARKET_ENCOUNTER.id: LEMONS_MARKET_ENCOUNTER,
    GOAT_SIGNAL_ENCOUNTER.id: GOAT_SIGNAL_ENCOUNTER,
}
