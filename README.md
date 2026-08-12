# Lower Equilibrium — Pygame edition

A single-player 2D implementation of the "Lower Equilibrium" game proposal,
built in Pygame to hit a tight deadline after the original Unity/3D prototype
proved too slow to iterate on in this environment. Same rules, same village
framing, much simpler stack: one Python process, no engine, no editor.

Each round you choose to work **Solo** (farming / animal husbandry /
maintenance around the hut — flavor only, random each time), **Approach**
another villager (cuts to a Market screen where you meet them), or gather
**Intelligence** on someone. An AI Facilitator (Claude or Gemini, called
directly from Python) narrates your outcomes in character. Bots use cheap
rule-based heuristics — no LLM calls for them, to keep things fast and free.

## Project layout

- `game_logic.py` — all game rules (payoff table, skill-match odds, action
  resolution, burnout, AI opponent heuristics) plus `GameManager`, a
  generator-driven round loop. **Zero pygame dependency** — this file can be
  imported and exercised from a plain script, which is how it was verified
  (see `test_logic.py`) before any UI was built on top of it.
- `facilitator.py` — direct HTTP calls to Claude/Gemini (no backend server;
  see "Why call the AI directly" below). Runs each request on a background
  thread and hands results back through a queue that `FacilitatorClient.poll()`
  drains once per frame, so the game never freezes waiting on the network.
  Falls back to a local canned line if disabled, no key, or the request fails.
- `main.py` — the Pygame window: Home screen (village circle around the hut,
  farm patch, animal pen, tool shed, action buttons, target picker) and
  Market screen (stalls with awnings/crates/fruit, your avatar + target,
  narration, return button). Two screens are just two draw functions and one
  `screen_state` flag — no scene files, no engine machinery.
- `test_logic.py` — runs a full 20-round game with the human auto-playing
  Solo, asserts it finishes without exceptions, prints standings. Run this
  any time you touch `game_logic.py`.
- `achievements.py` — badge definitions + `AchievementTracker`, which watches
  the human's progress via `GameManager`'s existing callbacks (no changes to
  core game logic needed).
- `save_data.py` — a local JSON file persisting games played, best score,
  and unlocked achievements across separate runs of the game.

## Engagement loop: what was missing, and what was added

Diagnosed against the course's own Engagement Loop Canvas (Goal → Choice →
Action → Feedback → Consequence → Updated state → **New choice** — "why does
the player care about another cycle?") and its scale table (action loop/
seconds → core gameplay loop/minutes → **progression loop**/sessions-hours):
the game had a solid action loop and core gameplay loop, but *nothing* at the
progression-loop scale — round 20 was mechanically identical to round 1,
and nothing carried over between separate games. Cross-checked against
Session 3-4's "Building Blocks of Engagement Systems" (Progression /
Achievements / Meta-Game / Cosmetics / Social / Live Ops), the game had none
of these beyond raw points.

Five additions, all screened against the Ethics deck's dark-pattern list
(no streaks that punish a missed day, no countdowns, no manufactured
scarcity — everything here only ever adds, never nags or decays):

1. **Achievements** (`achievements.py`) — 8 milestone badges (first
   connection, reaching each equilibrium zone, surviving burnout, a
   Complementary-skill success, etc.), unlocked live during play with an
   on-screen toast.
2. **Persistent cross-game progression** (`save_data.py`) — games played,
   best score, and achievements unlocked are saved locally and shown on the
   style-select screen. This is the actual missing progression loop: a
   reason to play a *second game*, not just survive to round 20 of the same
   one.
3. **A real strategic choice at game start** — Cautious / Balanced / Bold
   playstyles (`RiskStyle` in `game_logic.py`), trading Approach's cost and
   payoff for accept-chance in different directions. Verified by simulation
   to be genuinely balanced (avg points within ~3% of each other across 300
   trials each) rather than one dominant option — see the risk-style
   modifiers and comment block above `resolve_approach`.
4. **Light bot personas** — each bot gets a one-line personality trait
   (`PlayerData.persona_trait`), woven into the facilitator's narration
   when you interact with them. No extra LLM calls needed; it's just prompt
   context on top of the narration you were already requesting.
5. **A scripted mid-game event** — "Market Day" at the halfway-point round
   (`GameManager.special_event_round`): approaches are cheaper and everyone's
   more receptive for that one round. A single novelty beat breaking the
   sameness of 20 otherwise-identical rounds, not a repeating mechanic.

## Balance fix: pure Solo used to win every game

Playtesting found that always choosing Solo won ~100% of the time, even over
100-round games. Simulation (`GameManager` run headless with a scripted
human, no UI needed — see git history for the exact experiment) traced this
to three compounding issues, all in the proposal's own literal numbers:

1. The proposal's own "Expected value" column for Approach (-0.1 / +0.4 /
   +0.1) doesn't match what its own accept/reject percentages and payoffs
   actually compute to (recomputing gives -1.5 / +0.4 / +0.5) — near zero or
   negative for every skill match.
2. The transition valley dropped base payoff from 60 (Eq2) down to 38 —
   partial growth was punished harder than it ever paid off within a
   20-round game.
3. The biggest factor: Approach and Solo were mutually exclusive per round,
   so choosing to Approach forfeited that round's *entire* base payoff on
   top of the -5 cost and the risk of failure — once you had any
   connections at all, that opportunity cost dwarfed anything Approach
   could realistically win back.

Fix (see comments in `game_logic.py` next to `_ODDS`, `_BASE_PAYOFF`, and
`resolve_approach`): raised Approach's accept chances and payoffs so every
relationship has a clearly positive EV per attempt, softened the valley
(60 -> 52 at its lowest, was 60 -> 38), and made Approach also earn that
round's base payoff like Solo/Intelligence do. Verified by simulation:
pure-Solo now averages **rank 14.2 of 16 with a 0% win rate**, while active
play averages rank 6.9 of 16 with a 14% win rate — over 300 trials each.

## Why Pygame instead of Unity

The Unity version (see `~/UnityProjects/LowerEquilibrium` if you want to
compare) hit repeated environment friction in this sandbox: batch-mode Editor
hangs, material-leak warnings, scene-file locks whenever the Editor was also
open. None of that is a Pygame problem — there's no editor, no scene assets,
no compile step; `python main.py` either runs or shows a Python traceback.
Given the Aug 20 deadline, trading Unity's richer tooling for something that
can actually be iterated on quickly here was the right call.

## Why call the AI directly instead of running a backend

The Unity version proxied Claude/Gemini through a small Node server so the
API key never shipped inside a distributed build. That threat model doesn't
apply here: this game runs locally, from source, for a course
demo/submission — nobody downloads a compiled binary that could be
decompiled for the key. So `facilitator.py` calls the provider APIs directly
and keeps the key in a local, gitignored `.env`. One process instead of two.

## Design choices not fully specified in the proposal

Same interpretive choices as the Unity version (this is a direct port):

- **Skill space**: 4 skills (Marketing, Creativity, Finance/Analytics,
  Operations) arranged in a wheel, so every skill has a Same/Adjacent/
  Complementary relationship to every other. The proposal names only 3 as
  *examples*.
- **Burnout duration**: 2 rounds after 3 consecutive rejects (tunable via
  `BURNOUT_DURATION_ROUNDS` in `game_logic.py`).
- **16 players, 20 rounds** by default (`GameManager.__init__` args) — enough
  players for connection counts to reach the N=15+ "Eq3" zone.
- **Intelligence data point**: one of {skill, points, connections, burnout}
  at random, revealed truthfully.
- **Village/job/market framing**: cosmetic layer on top of the core
  Solo/Approach/Intelligence math, added at the user's request for visual
  and narrative richness.

## Running it

```bash
cd pygame_game
python3.13 -m venv .venv        # pygame doesn't yet have prebuilt wheels for 3.14
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add ANTHROPIC_API_KEY and/or GEMINI_API_KEY (optional —
# the game runs fine without one, using local narration lines instead)
python main.py
```

Verify the core rules independently at any time with:

```bash
python test_logic.py
```

### Controls

On launch, pick a playstyle (Cautious / Balanced / Bold) — this also shows
your career stats (games played, best score, achievements). Then, on your
turn: click **Solo**, **Approach**, or **Intelligence**. Approach/Intelligence
open a target list on the right — click a name, or **Cancel** to back out. On
the Market screen, either wait ~6 seconds for auto-return or click **Return
to Village**. After the game ends, **Play Again** takes you back to the style
select screen without restarting the app.

## Known limitations

- Visuals are simple shapes (circles, rectangles) — intentional, matches the
  "keep graphics limited" brief. No sprite art, no animation beyond static
  frames.
- Bots are fully silent — only your own actions get AI narration, to keep
  latency and API cost down during a playthrough.
- Persistence is cross-*game* only (`save_data.json`), not mid-game — closing
  the window mid-round loses that round; nothing earlier is lost.
- Window size is fixed at 1100×720 (not resizable).
