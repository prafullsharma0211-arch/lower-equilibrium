"""Pure game-logic port of the "Lower Equilibrium" proposal.

No pygame dependency here on purpose — this module is safe to import and
exercise from a plain Python script (see test_logic.py) so the rules can be
verified before any UI is built on top.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

class SkillType(Enum):
    # The proposal names Marketing, Creativity, and Finance/Analytics as
    # *examples*. Same/Adjacent/Complementary needs every skill to have an
    # opposite, so a 4th skill (Operations) was added, arranged in a wheel.
    MARKETING = 0
    CREATIVITY = 1
    FINANCE_ANALYTICS = 2
    OPERATIONS = 3


class SkillRelationship(Enum):
    SAME = auto()
    ADJACENT = auto()
    COMPLEMENTARY = auto()


_WHEEL_SIZE = 4


def get_relationship(a: SkillType, b: SkillType) -> SkillRelationship:
    distance = abs(a.value - b.value)
    distance = min(distance, _WHEEL_SIZE - distance)
    if distance == 0:
        return SkillRelationship.SAME
    if distance == 1:
        return SkillRelationship.ADJACENT
    return SkillRelationship.COMPLEMENTARY


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

class ActionType(Enum):
    SOLO = auto()
    APPROACH = auto()
    INTELLIGENCE = auto()
    # A scripted story-mode round (see story_games.py) — the payoff comes
    # from that encounter's own resolution, not from the zone-based Solo
    # formula, so it's resolved separately from the other three actions.
    STORY_ENCOUNTER = auto()


class ApproachOutcome(Enum):
    ACCEPT = auto()
    STATUS_QUO = auto()
    REJECT = auto()


class JobType(Enum):
    # Cosmetic flavor for Solo — doesn't change payoffs.
    FARMING = auto()
    ANIMAL_HUSBANDRY = auto()
    MAINTENANCE = auto()


# ---------------------------------------------------------------------------
# Payoff table — REBALANCED from the proposal's literal numbers.
#
# The proposal's own numbers (valley bottoming at 38, vs Eq2's 60) made
# playing Solo every round a dominant strategy: simulation showed a
# pure-Solo player winning ~100% of the time even at 100 rounds, because the
# valley punished partial growth harder than staying put ever paid off. The
# valley here is softened (60 -> 52 at its lowest, was 60 -> 38) so climbing
# through it is still a dip — loss aversion still reads — but not a
# near-total wipeout of your Eq2 gains. See also the ODDS/APPROACH_COST
# rebalancing below; verified together via repeated simulation
# (test_logic.py) until active play reliably beat pure Solo.
# ---------------------------------------------------------------------------

_BASE_PAYOFF = [40, 43, 47, 52, 56, 59, 60, 58, 56, 54, 52, 58, 65, 75, 88, 100]
_ZONE_NAMES = [
    "Eq1 — Solo trap", "Rising", "Rising", "Approaching Eq2", "Approaching Eq2",
    "Near Eq2 peak", "Eq2 — Group trap", "Transition valley", "Transition valley",
    "Transition valley", "Valley bottom", "Recovery", "Recovery", "Recovery",
    "Approaching Eq3", "Eq3 — Global optimum",
]


def _clamp_index(connections: int) -> int:
    return max(0, min(connections, len(_BASE_PAYOFF) - 1))


def get_base_payoff(connections: int) -> int:
    return _BASE_PAYOFF[_clamp_index(connections)]


def get_zone_name(connections: int) -> str:
    return _ZONE_NAMES[_clamp_index(connections)]


# ---------------------------------------------------------------------------
# Approach outcome odds — REBALANCED from the proposal's literal numbers.
#
# The proposal's own "Expected value" column (-0.1 / +0.4 / +0.1) doesn't
# match what its own accept/reject percentages and payoffs actually compute
# to (recomputing directly gives -1.5 / +0.4 / +0.5 net of the 5pt cost) —
# the source document appears to have an internal inconsistency here. Worse,
# even at the higher end those per-attempt EVs are tiny, so the -5 upfront
# cost plus the risk of a wasted round made Approach a losing proposition
# once compounded over many attempts. Payoffs raised and accept chances
# increased so every relationship has a clearly positive EV per attempt —
# still Complementary > Adjacent > Same in both risk and reward, but none of
# them are a bad bet anymore.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OutcomeOdds:
    accept: float
    status_quo: float
    reject: float
    payoff_if_accepted: int


_ODDS = {
    SkillRelationship.SAME: OutcomeOdds(0.70, 0.20, 0.10, 8),
    SkillRelationship.ADJACENT: OutcomeOdds(0.55, 0.20, 0.25, 16),
    SkillRelationship.COMPLEMENTARY: OutcomeOdds(0.40, 0.15, 0.45, 28),
}


def get_odds(relationship: SkillRelationship) -> OutcomeOdds:
    return _ODDS[relationship]


def roll_outcome(
    relationship: SkillRelationship, rng: random.Random, odds_override: Optional["OutcomeOdds"] = None
) -> ApproachOutcome:
    odds = odds_override if odds_override is not None else get_odds(relationship)
    roll = rng.random()
    if roll < odds.accept:
        return ApproachOutcome.ACCEPT
    if roll < odds.accept + odds.status_quo:
        return ApproachOutcome.STATUS_QUO
    return ApproachOutcome.REJECT


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------------
# Risk style — a player's chosen (or, for bots, assigned) approach to
# Approach: trades expected value for variance, not a strictly-better option.
# Engagement-loop rationale: gives players a real strategic identity to
# commit to (Autonomy) and something to actually get better at reading
# (Competence), instead of everyone converging on one "correct" play.
# ---------------------------------------------------------------------------

class RiskStyle(Enum):
    CAUTIOUS = auto()   # lower cost, lower payoff, higher accept chance — safer, smaller swings
    BALANCED = auto()   # unmodified
    BOLD = auto()       # same cost, higher payoff, lower accept chance — bigger swings


@dataclass(frozen=True)
class RiskStyleModifier:
    cost_mult: float
    payoff_mult: float
    accept_delta: float  # added to base accept chance, taken from/given to reject


_RISK_STYLE_MODIFIERS = {
    RiskStyle.CAUTIOUS: RiskStyleModifier(cost_mult=0.6, payoff_mult=0.7, accept_delta=+0.10),
    RiskStyle.BALANCED: RiskStyleModifier(cost_mult=1.0, payoff_mult=1.0, accept_delta=0.0),
    RiskStyle.BOLD: RiskStyleModifier(cost_mult=1.0, payoff_mult=1.35, accept_delta=-0.10),
}


def get_risk_style_modifier(style: "RiskStyle") -> RiskStyleModifier:
    return _RISK_STYLE_MODIFIERS[style]


# Cheap, local flavor for bots — no LLM call needed just to give them an
# identity. The facilitator (facilitator.py) weaves these into narration
# when a bot is involved, for a lightweight Relatedness/Explorer boost.
_PERSONA_TRAITS = [
    "quietly ambitious",
    "the social butterfly of the group",
    "a careful planner who hates wasting a coin",
    "impulsive and always chasing the next big connection",
    "well-liked but slow to trust newcomers",
    "keeps to themselves, but reliable when approached",
    "the gossip of the village — knows everyone's business",
    "stubbornly independent, prefers working alone",
    "a natural networker, rarely turns anyone away",
    "still smarting from a bad harvest, a bit guarded lately",
]


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

@dataclass
class PlayerData:
    id: int
    name: str
    skill: SkillType
    is_human: bool
    points: int = 0
    connection_ids: set = field(default_factory=set)
    consecutive_rejects: int = 0
    burnout_rounds_remaining: int = 0
    risk_tolerance: float = 0.5
    risk_style: "RiskStyle" = RiskStyle.BALANCED
    persona_trait: str = ""

    @property
    def connection_count(self) -> int:
        return len(self.connection_ids)

    @property
    def is_burned_out(self) -> bool:
        return self.burnout_rounds_remaining > 0


# ---------------------------------------------------------------------------
# Results (consumed by narration / rendering)
# ---------------------------------------------------------------------------

@dataclass
class SoloResult:
    actor: PlayerData
    points_earned: int
    job: JobType


@dataclass
class ApproachResult:
    actor: PlayerData
    target: PlayerData
    relationship: SkillRelationship
    outcome: ApproachOutcome
    points_delta: int
    burnout_triggered: bool


@dataclass
class IntelligenceResult:
    querier: PlayerData
    target: PlayerData
    data_point_type: str
    data_point_value: str


@dataclass
class BotDecision:
    action: ActionType
    target: Optional[PlayerData] = None


@dataclass
class StoryEncounterResult:
    actor: PlayerData
    encounter_id: str
    points_delta: int


# ---------------------------------------------------------------------------
# Action resolution
# ---------------------------------------------------------------------------

APPROACH_COST = 5
INTELLIGENCE_COST = 2
BURNOUT_THRESHOLD = 3
# The proposal says burnout lasts "for some period" without a number —
# an explicit, tunable interpretive choice.
BURNOUT_DURATION_ROUNDS = 2

# One-time scripted mid-game event ("Market Day") — see GameManager.special_event_round.
EVENT_COST_MULT = 0.5
EVENT_ACCEPT_BONUS = 0.15


class ActionResolver:
    def __init__(self, rng: random.Random):
        self._rng = rng

    def resolve_solo(self, actor: PlayerData) -> SoloResult:
        payoff = get_base_payoff(actor.connection_count)
        actor.points += payoff
        job = self._rng.choice(list(JobType))
        return SoloResult(actor=actor, points_earned=payoff, job=job)

    def resolve_approach(self, actor: PlayerData, target: PlayerData, event_bonus: bool = False) -> ApproachResult:
        relationship = get_relationship(actor.skill, target.skill)
        base_odds = get_odds(relationship)
        style_mod = get_risk_style_modifier(actor.risk_style)

        cost = round(APPROACH_COST * style_mod.cost_mult)
        payoff_if_accepted = round(base_odds.payoff_if_accepted * style_mod.payoff_mult)
        accept = _clamp01(base_odds.accept + style_mod.accept_delta)
        reject = _clamp01(base_odds.reject - (accept - base_odds.accept))
        status_quo = max(0.0, 1.0 - accept - reject)

        if event_bonus:
            # Scripted mid-game "Market Day": everyone's more receptive and
            # it's cheaper to try. A one-round novelty beat (Flow: unpredictability)
            # rather than a permanent change — see GameManager.special_event_round.
            cost = round(cost * EVENT_COST_MULT)
            accept = _clamp01(accept + EVENT_ACCEPT_BONUS)
            reject = _clamp01(reject - EVENT_ACCEPT_BONUS)
            status_quo = max(0.0, 1.0 - accept - reject)

        odds = OutcomeOdds(accept, status_quo, reject, payoff_if_accepted)
        outcome = roll_outcome(relationship, self._rng, odds_override=odds)

        # Approach also earns this round's base payoff, same as Solo/
        # Intelligence. Without this, choosing to Approach meant forfeiting
        # your entire baseline income for the round on top of the cost
        # and the risk of failure — an opportunity cost far larger than
        # anything Approach could realistically win back, which was the
        # single biggest reason pure Solo dominated in simulation (see the
        # rebalancing notes above _BASE_PAYOFF and _ODDS).
        points_delta = get_base_payoff(actor.connection_count) - cost
        burnout_triggered = False

        if outcome == ApproachOutcome.ACCEPT:
            points_delta += payoff_if_accepted
            actor.connection_ids.add(target.id)
            target.connection_ids.add(actor.id)
            actor.consecutive_rejects = 0
        elif outcome == ApproachOutcome.REJECT:
            actor.consecutive_rejects += 1
            if actor.consecutive_rejects >= BURNOUT_THRESHOLD:
                actor.burnout_rounds_remaining = BURNOUT_DURATION_ROUNDS
                actor.consecutive_rejects = 0
                burnout_triggered = True
        # STATUS_QUO: no connection change, reject streak untouched.

        actor.points += points_delta

        return ApproachResult(
            actor=actor,
            target=target,
            relationship=relationship,
            outcome=outcome,
            points_delta=points_delta,
            burnout_triggered=burnout_triggered,
        )

    def resolve_intelligence(self, querier: PlayerData, target: PlayerData) -> IntelligenceResult:
        querier.points -= INTELLIGENCE_COST
        # "Can be combined with SOLO — you still earn base payoff."
        querier.points += get_base_payoff(querier.connection_count)

        data_point_type = self._rng.choice(["skill", "points", "connections", "burnout"])
        if data_point_type == "skill":
            value = target.skill.name
        elif data_point_type == "points":
            value = str(target.points)
        elif data_point_type == "connections":
            value = str(target.connection_count)
        else:
            value = "burned out" if target.is_burned_out else "not burned out"

        return IntelligenceResult(
            querier=querier,
            target=target,
            data_point_type=data_point_type,
            data_point_value=value,
        )

    def tick_burnout(self, player: PlayerData) -> None:
        if player.burnout_rounds_remaining > 0:
            player.burnout_rounds_remaining -= 1


# ---------------------------------------------------------------------------
# AI opponent brain — cheap rule-based heuristics, no LLM calls.
# ---------------------------------------------------------------------------

class AIOpponentBrain:
    def __init__(self, rng: random.Random):
        self._rng = rng

    def decide(self, bot: PlayerData, all_players: list) -> BotDecision:
        if bot.is_burned_out:
            if self._rng.random() < 0.25:
                return self._intelligence_decision(bot, all_players)
            return BotDecision(ActionType.SOLO)

        n = bot.connection_count
        if n <= 5:
            approach_probability = 0.75
        elif n == 6:
            approach_probability = _clamp01(0.2 + 0.5 * bot.risk_tolerance)
        elif 7 <= n <= 10:
            approach_probability = _clamp01(0.15 + 0.7 * bot.risk_tolerance)
        elif 11 <= n <= 14:
            approach_probability = _clamp01(0.5 + 0.4 * bot.risk_tolerance)
        else:
            approach_probability = 0.05

        if self._rng.random() >= approach_probability:
            if self._rng.random() < 0.15:
                return self._intelligence_decision(bot, all_players)
            return BotDecision(ActionType.SOLO)

        target = self._choose_target(bot, all_players)
        if target is None:
            return BotDecision(ActionType.SOLO)
        return BotDecision(ActionType.APPROACH, target)

    def _intelligence_decision(self, bot: PlayerData, all_players: list) -> BotDecision:
        target = self._choose_target(bot, all_players)
        if target is None:
            return BotDecision(ActionType.SOLO)
        return BotDecision(ActionType.INTELLIGENCE, target)

    def _choose_target(self, bot: PlayerData, all_players: list) -> Optional[PlayerData]:
        candidates = [p for p in all_players if p.id != bot.id]
        if not candidates:
            return None

        best = None
        best_score = float("-inf")
        for candidate in candidates:
            relationship = get_relationship(bot.skill, candidate.skill)
            odds = get_odds(relationship)
            expected_value = odds.accept * odds.payoff_if_accepted - APPROACH_COST
            safety_bonus = (1 - bot.risk_tolerance) * odds.accept * 10
            score = bot.risk_tolerance * expected_value + safety_bonus + self._rng.random()
            if score > best_score:
                best_score = score
                best = candidate
        return best


# ---------------------------------------------------------------------------
# GameManager — a generator-driven round loop, framework-agnostic.
#
# Call update(dt) once per frame; it advances the loop unless paused or
# waiting on the human. The UI submits the human's choice via
# submit_solo()/submit_approach()/submit_intelligence().
# ---------------------------------------------------------------------------

class GameManager:
    def __init__(
        self,
        total_players: int = 16,
        total_rounds: int = 20,
        human_name: str = "You",
        human_risk_style: "RiskStyle" = RiskStyle.BALANCED,
        delay_between_rounds: float = 1.0,
        seed: Optional[int] = None,
        story_encounter_rounds: Optional[dict] = None,
    ):
        self.total_rounds = total_rounds
        self.delay_between_rounds = delay_between_rounds
        self.current_round = 0
        self.is_game_over = False
        self.paused = False
        self.awaiting_human = False
        # One-time scripted mid-game novelty beat (Flow trigger) — see
        # ActionResolver.resolve_approach's event_bonus handling.
        self.special_event_round = max(1, total_rounds // 2)
        # round_num -> encounter id (see story_games.py). Replaces that
        # round's normal action entirely with a scripted game-theory
        # scenario — this is "his journey," not a simulated village day.
        # Chapter 1 opens the game at round 1 by design: the player should
        # meet the story before the repetitive village loop, not after
        # three ordinary rounds of it. Chapter 2 lands mid-game, once the
        # player has had time back in the village loop between story beats.
        self.story_encounter_rounds: dict = story_encounter_rounds or {
            1: "quality_price",
            min(8, total_rounds): "road_fund",
        }
        self._pending_encounter_id: str = ""
        self._pending_encounter_points: int = 0

        self._rng = random.Random(seed)
        self._resolver = ActionResolver(self._rng)
        self._brain = AIOpponentBrain(self._rng)
        self._dt = 0.0

        skill_values = list(SkillType)
        self.human = PlayerData(
            0, human_name, self._rng.choice(skill_values), is_human=True, risk_style=human_risk_style,
        )
        self.players: list = [self.human]
        for i in range(1, max(total_players, 2)):
            risk_tolerance = self._rng.random()
            bot_style = (
                RiskStyle.CAUTIOUS if risk_tolerance < 0.33
                else RiskStyle.BOLD if risk_tolerance > 0.66
                else RiskStyle.BALANCED
            )
            bot = PlayerData(
                i, f"Bot {i}", self._rng.choice(skill_values), is_human=False,
                risk_tolerance=risk_tolerance,
                risk_style=bot_style,
                persona_trait=self._rng.choice(_PERSONA_TRAITS),
            )
            self.players.append(bot)

        self._human_action: Optional[ActionType] = None
        self._human_target_id: int = -1
        self._human_action_submitted = False

        # Callback lists — append plain functions.
        self.on_round_started: list[Callable] = []
        self.on_human_state_changed: list[Callable] = []
        self.on_action_resolved: list[Callable] = []   # (actor, action, target, job|None)
        self.on_round_summary: list[Callable] = []      # (round, events, standings)
        self.on_game_ended: list[Callable] = []         # (standings)
        self.on_special_event: list[Callable] = []      # (round_num) — fired once, at special_event_round
        # Fired only for the human, with the actual result object
        # (SoloResult | ApproachResult | IntelligenceResult) — enough detail
        # for the UI to request rich narration and, for Approach, switch to
        # the market screen.
        self.on_human_action_result: list[Callable] = []

        self._loop = self._run_game_loop()

    def get_other_players(self) -> list:
        return [p for p in self.players if p.id != self.human.id]

    def submit_solo(self) -> None:
        if not self.awaiting_human:
            return
        self._human_action = ActionType.SOLO
        self._human_target_id = -1
        self._human_action_submitted = True

    def submit_approach(self, target_id: int) -> None:
        if not self.awaiting_human:
            return
        self._human_action = ActionType.APPROACH
        self._human_target_id = target_id
        self._human_action_submitted = True

    def submit_intelligence(self, target_id: int) -> None:
        if not self.awaiting_human:
            return
        self._human_action = ActionType.INTELLIGENCE
        self._human_target_id = target_id
        self._human_action_submitted = True

    def submit_story_encounter(self, points_delta: int, encounter_id: str) -> None:
        if not self.awaiting_human:
            return
        self._human_action = ActionType.STORY_ENCOUNTER
        self._human_target_id = -1
        self._pending_encounter_id = encounter_id
        self._pending_encounter_points = points_delta
        self._human_action_submitted = True

    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def update(self, dt: float) -> None:
        if self.is_game_over:
            return
        self._dt = dt
        try:
            next(self._loop)
        except StopIteration:
            self.is_game_over = True

    def _find_player(self, player_id: int) -> Optional[PlayerData]:
        for p in self.players:
            if p.id == player_id:
                return p
        return None

    def _standings(self) -> list:
        return sorted(self.players, key=lambda p: p.points, reverse=True)

    def _fire_action_resolved(self, actor, action, target, job) -> None:
        for cb in self.on_action_resolved:
            cb(actor, action, target, job)

    def _run_game_loop(self):
        for round_num in range(1, self.total_rounds + 1):
            while self.paused:
                yield

            self.current_round = round_num
            for cb in self.on_round_started:
                cb(round_num)

            if round_num == self.special_event_round:
                for cb in self.on_special_event:
                    cb(round_num)

            for p in self.players:
                self._resolver.tick_burnout(p)

            order = list(self.players)
            self._rng.shuffle(order)
            events = []

            for p in order:
                if p.is_human:
                    self.awaiting_human = True
                    self._human_action_submitted = False
                    for cb in self.on_human_state_changed:
                        cb(self.human)

                    while not self._human_action_submitted:
                        yield

                    self.awaiting_human = False
                    self._resolve_human_action(events)
                    for cb in self.on_human_state_changed:
                        cb(self.human)
                else:
                    self._resolve_bot_action(p, events)

            standings = self._standings()
            for cb in self.on_round_summary:
                cb(round_num, events, standings)

            elapsed = 0.0
            while elapsed < self.delay_between_rounds:
                elapsed += self._dt
                yield

        for cb in self.on_game_ended:
            cb(self._standings())

    def _resolve_human_action(self, events: list) -> None:
        action = self._human_action

        if action == ActionType.SOLO:
            result = self._resolver.resolve_solo(self.human)
            events.append({
                "actor": self.human.name, "action": "Solo",
                "summary": f"{result.job.name}: earned {result.points_earned} pts",
                "result": result,
            })
            self._fire_action_resolved(self.human, ActionType.SOLO, None, result.job)
            for cb in self.on_human_action_result:
                cb(result)

        elif action == ActionType.APPROACH:
            target = self._find_player(self._human_target_id)
            if target is None:
                return
            result = self._resolver.resolve_approach(
                self.human, target, event_bonus=(self.current_round == self.special_event_round)
            )
            events.append({
                "actor": self.human.name, "action": "Approach",
                "summary": f"approached {target.name}: {result.outcome.name} ({result.points_delta:+d} pts)",
                "result": result,
            })
            self._fire_action_resolved(self.human, ActionType.APPROACH, target, None)
            for cb in self.on_human_action_result:
                cb(result)

        elif action == ActionType.INTELLIGENCE:
            target = self._find_player(self._human_target_id)
            if target is None:
                return
            result = self._resolver.resolve_intelligence(self.human, target)
            events.append({
                "actor": self.human.name, "action": "Intelligence",
                "summary": f"scouted {target.name}'s {result.data_point_type}",
                "result": result,
            })
            self._fire_action_resolved(self.human, ActionType.INTELLIGENCE, target, None)
            for cb in self.on_human_action_result:
                cb(result)

        elif action == ActionType.STORY_ENCOUNTER:
            self.human.points += self._pending_encounter_points
            result = StoryEncounterResult(
                actor=self.human, encounter_id=self._pending_encounter_id,
                points_delta=self._pending_encounter_points,
            )
            events.append({
                "actor": self.human.name, "action": "Story",
                "summary": f"{self._pending_encounter_id}: {self._pending_encounter_points:+d} pts",
                "result": result,
            })
            self._fire_action_resolved(self.human, ActionType.STORY_ENCOUNTER, None, None)
            for cb in self.on_human_action_result:
                cb(result)

    def _resolve_bot_action(self, bot: PlayerData, events: list) -> None:
        decision = self._brain.decide(bot, self.players)

        if decision.action == ActionType.SOLO or decision.target is None:
            result = self._resolver.resolve_solo(bot)
            events.append({
                "actor": bot.name, "action": "Solo",
                "summary": f"earned {result.points_earned} pts", "result": result,
            })
            self._fire_action_resolved(bot, ActionType.SOLO, None, result.job)

        elif decision.action == ActionType.APPROACH:
            result = self._resolver.resolve_approach(
                bot, decision.target, event_bonus=(self.current_round == self.special_event_round)
            )
            events.append({
                "actor": bot.name, "action": "Approach",
                "summary": f"approached {decision.target.name}: {result.outcome.name}",
                "result": result,
            })
            self._fire_action_resolved(bot, ActionType.APPROACH, decision.target, None)

        elif decision.action == ActionType.INTELLIGENCE:
            result = self._resolver.resolve_intelligence(bot, decision.target)
            events.append({
                "actor": bot.name, "action": "Intelligence",
                "summary": f"scouted {decision.target.name}", "result": result,
            })
            self._fire_action_resolved(bot, ActionType.INTELLIGENCE, decision.target, None)
