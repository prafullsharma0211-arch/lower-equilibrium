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

Click **Solo**, **Approach**, or **Intelligence** on your turn. Approach/
Intelligence open a target list on the right — click a name, or **Cancel** to
back out. On the Market screen, either wait ~6 seconds for auto-return or
click **Return to Village**.

## Known limitations

- Visuals are simple shapes (circles, rectangles) — intentional, matches the
  "keep graphics limited" brief. No sprite art, no animation beyond static
  frames.
- Bots are fully silent — only your own actions get AI narration, to keep
  latency and API cost down during a playthrough.
- No save/load; closing the window ends the run.
- Window size is fixed at 1100×720 (not resizable).
