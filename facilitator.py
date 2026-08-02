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


def _approach_fallback(result: ApproachResult) -> str:
    if result.outcome == ApproachOutcome.ACCEPT:
        return f"{result.actor.name} heads to the market and strikes a deal with {result.target.name}. ({result.points_delta:+d} pts net)"
    if result.outcome == ApproachOutcome.STATUS_QUO:
        return f"{result.actor.name} finds {result.target.name} at the market, but the haggling goes nowhere."
    suffix = " Burnout sets in." if result.burnout_triggered else ""
    return f"{result.target.name} waves {result.actor.name} off at the market.{suffix}"


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
            f"Round event: {result.actor.name} approached {result.target.name}.\n"
            f"Skill relationship: {result.relationship.name}\n"
            f"Outcome: {result.outcome.name}\n"
            f"Net points from this action: {result.points_delta}\n"
            f"{result.actor.name}'s running total: {result.actor.points} pts, "
            f"{result.actor.connection_count} active connections.\n"
            + ("This player has just hit burnout after repeated rejections.\n" if result.burnout_triggered else "")
            + f"\nNarrate this moment for {result.actor.name}."
        )
        self._dispatch(prompt, _approach_fallback(result), 200, callback)

    def request_intelligence_narration(self, result: IntelligenceResult, callback: Callable[[str], None]) -> None:
        prompt = (
            f"{result.querier.name} spent Intelligence to learn one true data point about {result.target.name}.\n"
            f"Data point type: {result.data_point_type}\n"
            f"Data point value: {result.data_point_value}\n\n"
            f"Deliver this as an in-character tip from the Facilitator to {result.querier.name}, "
            "as if leaning in with gossip. Reveal only the given data point."
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
