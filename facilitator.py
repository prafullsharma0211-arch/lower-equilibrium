"""Talks directly to Claude/Gemini for in-character narration.

Runs each request on a background thread so the Pygame main loop never
blocks on network I/O — results are handed back through a thread-safe queue
that FacilitatorClient.poll() drains once per frame on the main thread
(pygame/rendering isn't thread-safe, so callbacks must fire there, not from
the worker thread).

This game runs locally for a course demo rather than being distributed to
strangers, so keeping the API key in a local, gitignored .env file (loaded
here, never hard-coded) is an acceptable tradeoff — unlike a shipped Unity
build, there's no compiled artifact that could leak the key to an end user.
"""

from __future__ import annotations

import os
import queue
import random
import threading
from dataclasses import dataclass
from typing import Callable, Optional

import requests
from dotenv import load_dotenv

from game_logic import ApproachOutcome, ApproachResult, IntelligenceResult, JobType, SoloResult

load_dotenv()

FACILITATOR_SYSTEM_PROMPT = """
You are the Facilitator for "Lower Equilibrium," a social-network strategy game
about prospect theory, Nash equilibria, and weak ties, dressed up as a small
village story: each player lives in a hut in a green forest and works one of
three jobs -- farming, tending animals, or general upkeep -- or heads into the
village to the market to try to connect/trade with someone else. Players
choose each round to work SOLO (one of those village jobs), APPROACH another
player (go to the market to try to connect with them), or gather INTELLIGENCE
on someone before acting.

Your job is to narrate outcomes the way a sharp, dryly witty game master would --
never a spreadsheet readout. Rules:
- 2-4 sentences maximum. This renders in a small in-game text panel.
- Never invent numbers, names, or outcomes that weren't given to you in the data.
  You may only dramatize the facts you're handed.
- Don't explain game theory or lecture the player -- show the feeling
  (the sting of a rejection, the flatness of staying solo, the thrill of a payoff
  jump), don't state the concept name.
- Stay diegetic: you are speaking to the player in the moment, not writing a report.
""".strip()


def _call_claude(system: str, prompt: str, max_tokens: int, timeout: float) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return "".join(block.get("text", "") for block in data.get("content", [])).strip()


def _call_gemini(system: str, prompt: str, max_tokens: int, timeout: float) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    response = requests.post(
        url,
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


_PROVIDERS = {"claude": _call_claude, "gemini": _call_gemini}


def generate_narration(system: str, prompt: str, max_tokens: int = 200, timeout: float = 8.0) -> str:
    primary = os.environ.get("AI_PROVIDER", "claude")
    fallback = "gemini" if primary == "claude" else "claude"

    try:
        return _PROVIDERS[primary](system, prompt, max_tokens, timeout)
    except Exception as primary_error:
        try:
            return _PROVIDERS[fallback](system, prompt, max_tokens, timeout)
        except Exception as fallback_error:
            raise RuntimeError(
                f"Both providers failed. {primary}: {primary_error}; {fallback}: {fallback_error}"
            ) from fallback_error


def _persona_line(player) -> str:
    """One line of bot flavor for the prompt, if this player has a
    persona_trait (see game_logic.PlayerData) — cheap Relatedness/Explorer
    texture without an extra LLM call per bot.
    """
    trait = getattr(player, "persona_trait", "") or ""
    if not trait:
        return ""
    return f"{player.name} is known around the village as {trait}.\n"


# ---------------------------------------------------------------------------
# Local fallback lines — used when the facilitator is disabled or both
# providers fail, so the game never blocks on the network.
# ---------------------------------------------------------------------------

_SOLO_JOB_TEXT = {
    JobType.FARMING: "tends the fields behind the hut",
    JobType.ANIMAL_HUSBANDRY: "looks after the animals",
    JobType.MAINTENANCE: "patches up the hut and tools",
}


def _solo_fallback(result: SoloResult) -> str:
    job_text = _SOLO_JOB_TEXT.get(result.job, "works alone")
    return f"{result.actor.name} {job_text}. (+{result.points_earned} pts)"


_ACCEPT_EXCHANGES = [
    "{a}: I could use a hand with something -- interested?\n{t}: Depends. What's in it for me?\n{a}: A fair split, promise.\n{t}: ...Alright, I'm in.",
    "{a}: Ever thought about working together?\n{t}: Funny, I was about to say the same to you.\n{a}: Deal, then.",
    "{a}: I've got an idea, and I think you're the missing piece.\n{t}: Go on.\n{a}: Trust me on this one.\n{t}: Fine -- but I'm holding you to it.",
]

_STATUS_QUO_EXCHANGES = [
    "{a}: So -- partners?\n{t}: Let me think about it.\n{a}: That's a no for now, isn't it.\n{t}: It's a maybe. Ask me later.",
    "{a}: Any interest in teaming up?\n{t}: Maybe. Talk to me again next week.\n{a}: Noted.",
    "{a}: What if we combined forces on this?\n{t}: I hear you. I'm just not sold yet.\n{a}: Fair enough.",
]

_REJECT_EXCHANGES = [
    "{a}: I had an idea for the two of us --\n{t}: Not interested.\n{a}: Right. Never mind.",
    "{a}: Could really use your help on this.\n{t}: Find someone else.\n{a}: ...Okay.",
    "{a}: Partners?\n{t}: Hard pass.",
]


def _approach_fallback(result: ApproachResult) -> str:
    a, t = result.actor.name, result.target.name
    if result.outcome == ApproachOutcome.ACCEPT:
        template = random.choice(_ACCEPT_EXCHANGES)
    elif result.outcome == ApproachOutcome.STATUS_QUO:
        template = random.choice(_STATUS_QUO_EXCHANGES)
    else:
        template = random.choice(_REJECT_EXCHANGES)
    exchange = template.format(a=a, t=t)
    if result.outcome == ApproachOutcome.REJECT and result.burnout_triggered:
        exchange += f"\n{a}: ...Maybe I need to take a break from the market for a bit."
    return exchange


def parse_dialogue(text: str, actor_name: str, target_name: str) -> list[tuple[str, str]]:
    """Split an approach-narration string into (speaker, line) pairs.

    Accepts the "Name: line" format both the AI prompt and the local
    fallback produce. Any line that isn't speaker-tagged (the AI ignoring
    the format, or a one-off failure string) is kept as a single
    Narrator-voiced line rather than dropped, so the dialogue box never
    ends up empty.
    """
    known_speakers = {actor_name, target_name}
    lines: list[tuple[str, str]] = []
    for raw_line in text.strip().splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        speaker, sep, rest = raw_line.partition(": ")
        if sep and speaker in known_speakers:
            lines.append((speaker, rest.strip()))
        else:
            lines.append(("", raw_line))
    return lines or [("", text.strip())]


def _intelligence_fallback(result: IntelligenceResult) -> str:
    return f"Word is that {result.target.name}'s {result.data_point_type} is {result.data_point_value}."


def _round_summary_fallback(round_num: int, standings: list) -> str:
    if not standings:
        return f"Round {round_num} complete."
    leader = standings[0]
    return f"Round {round_num} complete. {leader.name} leads with {leader.points} pts."


# ---------------------------------------------------------------------------
# Threaded client
# ---------------------------------------------------------------------------

@dataclass
class _PendingResult:
    callback: Callable[[str], None]
    text: str


class FacilitatorClient:
    def __init__(self, enabled: bool = True, timeout: float = 8.0):
        self.enabled = enabled
        self.timeout = timeout
        self._queue: "queue.Queue[_PendingResult]" = queue.Queue()

    def poll(self) -> None:
        """Call once per frame from the main thread to dispatch finished callbacks."""
        while True:
            try:
                pending = self._queue.get_nowait()
            except queue.Empty:
                break
            pending.callback(pending.text)

    def _dispatch(self, prompt: str, fallback_text: str, max_tokens: int, callback: Callable[[str], None]) -> None:
        if not self.enabled:
            callback(fallback_text)
            return

        def worker():
            try:
                text = generate_narration(FACILITATOR_SYSTEM_PROMPT, prompt, max_tokens, self.timeout)
                if not text:
                    text = fallback_text
            except Exception:
                text = fallback_text
            self._queue.put(_PendingResult(callback, text))

        threading.Thread(target=worker, daemon=True).start()

    def request_solo_narration(self, result: SoloResult, callback: Callable[[str], None]) -> None:
        prompt = (
            f"Round event: {result.actor.name} spent this round working solo at their job: {result.job.name}.\n"
            f"Points earned: {result.points_earned}\n"
            f"{result.actor.name}'s current active connections: {result.actor.connection_count}\n\n"
            f"Narrate this quiet moment of village life for {result.actor.name}."
        )
        self._dispatch(prompt, _solo_fallback(result), 150, callback)

    def request_approach_narration(self, result: ApproachResult, callback: Callable[[str], None]) -> None:
        prompt = (
            f"Round event: {result.actor.name} approached {result.target.name} at the market.\n"
            f"{_persona_line(result.target)}"
            f"Skill relationship: {result.relationship.name}\n"
            f"Outcome: {result.outcome.name}\n"
            f"Net points from this action: {result.points_delta}\n"
            f"{result.actor.name}'s running total: {result.actor.points} pts, "
            f"{result.actor.connection_count} active connections.\n"
            + ("This player has just hit burnout after repeated rejections.\n" if result.burnout_triggered else "")
            + f"\nWrite this as a short spoken exchange between {result.actor.name} and {result.target.name} -- "
            "3 to 4 lines total, each on its own line, formatted EXACTLY as \"Name: line\" with no extra "
            "commentary before, after, or between lines. Use only their two names as speakers (no narrator "
            "line, no stage directions). The outcome must come through in what they say, not by stating game "
            "terms like 'accept' or 'reject'. Example shape (do not reuse this wording):\n"
            f"{result.actor.name}: <line>\n{result.target.name}: <line>\n{result.actor.name}: <line>"
        )
        self._dispatch(prompt, _approach_fallback(result), 200, callback)

    def request_intelligence_narration(self, result: IntelligenceResult, callback: Callable[[str], None]) -> None:
        prompt = (
            f"{result.querier.name} spent Intelligence to learn one true data point about {result.target.name}.\n"
            f"{_persona_line(result.target)}"
            f"Data point type: {result.data_point_type}\n"
            f"Data point value: {result.data_point_value}\n\n"
            f"Deliver this as an in-character tip from the Facilitator to {result.querier.name}, "
            "as if leaning in with gossip. Reveal only the given data point (the personality note, if any, is "
            "flavor you already know about them — don't present it as the scouted secret)."
        )
        self._dispatch(prompt, _intelligence_fallback(result), 150, callback)

    def request_round_summary(self, round_num: int, events: list, standings: list, callback: Callable[[str], None]) -> None:
        event_lines = "\n".join(
            f"- {e['actor']} chose {e['action']}: {e['summary']}" for e in events[:12]
        ) or "(no notable events)"
        standing_lines = "\n".join(
            f"- {p.name}: {p.points} pts" for p in standings[:8]
        ) or "(no standings provided)"
        prompt = (
            f"Round {round_num} has just ended.\n\nEvents:\n{event_lines}\n\n"
            f"Standings:\n{standing_lines}\n\nGive a short recap of this round for the players."
        )
        self._dispatch(prompt, _round_summary_fallback(round_num, standings), 220, callback)
