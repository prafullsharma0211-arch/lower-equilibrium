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

## Graphics and market conversations

Two further additions on top of the engagement-loop work, in response to
feedback that the game needed richer visuals and a real back-and-forth when
you approach someone, not a single narrated paragraph:

- **Paper-doll figures** (`draw_person()` in `main.py`) replace the plain
  circles everywhere a person is drawn — head, torso, arms, legs, drop
  shadow, skill-colored clothing. Same helper on the Home village circle
  (small scale, 16 at once) and the Market screen (larger, with a gentle
  idle bob animation).
- **Market screen redesign**: sky gradient, a pre-baked dirt/cobblestone
  ground texture, flat trees framing the edges, and redesigned stalls
  (scalloped awning, signboard, crates, a goods sack) instead of a flat
  brown background and three plain rectangles.
- **Home screen redesign: a real village** — the single central hut is now
  a marketplace plaza (well, stalls, "Village Market" label), reached by
  curved dirt roads (`_road_points()`, a quadratic bezier per player) from
  every one of the 16 houses ringing it. Each house comes with its own
  tilled field and fenced animal pen (`draw_homestead()`), sized to
  actually read next to its owner — `draw_person()` was scaled down and
  the homestead scaled up after the first pass came out with oversized
  people next to tiny buildings. Houses are offset tangentially along the
  ring rather than straight outward/downward from their owner, so a
  top-row house doesn't sit on top of its owner's head and a bottom-row
  one doesn't collide with the action buttons.
- **Dialogue exchange for Approach** (`facilitator.py`): the facilitator
  prompt now asks for a short, speaker-tagged back-and-forth ("Name: line")
  instead of one third-person paragraph, parsed by `parse_dialogue()` and
  displayed as a proper chat-style dialogue box that reveals one line at a
  time. The local (no-API-key) fallback got the same treatment — three
  hand-written exchange variants per outcome (accept/status quo/reject), so
  the conversation feel doesn't depend on having a key configured.

## Network-aware target picker

The Approach/Intelligence target list (`App._network_visibility()` in
`main.py`) now gates what you're shown by your actual position in the
network, not omniscience — a direct nod to Granovetter's weak ties, the
theory the whole game is built on:

- **Direct connection**: exact connection count and real burnout status.
- **One hop out** (a connection of one of your connections): a fuzzy bucket
  ("a few / several / many connections"), credited to whichever connection
  is the source ("via Bot 4") rather than an exact number — you heard it
  secondhand.
- **Everyone else**: "connections unknown." That's what the paid
  Intelligence action is for — it's the only way to learn something
  concrete about a total stranger.

This makes Approach a real decision instead of a coin flip on a name you've
never seen before, and it makes *building* connections valuable for
information, not just points — the more people you know, the more of the
village you can actually see.

## Onboarding: fixing "I have no idea what's happening"

A real, cold playtest surfaced ~29 distinct points of confusion — no
restart button, no explanation of the goal or the three actions, jargon
like "Eq1" and "Solo trap" with zero context, no idea why a round ended or
why points changed, no clue the Market screen would auto-close, and no
visible reward system beyond a single best-score number. In short: every
piece of internal game-design language (Nash equilibria zones, prospect
theory, weak ties) had leaked straight into the UI with nothing translating
it for a first-time player. Fixes, all in `main.py`:

- **A 5-page How-to-Play guide** (`HELP_PAGES`) with a small drawn icon per
  page — forced open on the very first launch (`save_data.tutorial_seen`)
  since a button nobody knows to click isn't discoverable, reachable any
  time after via **How to Play** (style-select) or **? Help** (Home/Market
  corner).
- **Hover tooltips on Solo/Approach/Intelligence** (`ACTION_TOOLTIPS`) —
  exactly the "an i button, hovering which could explain it" ask.
- **A Menu button** on Home and Market, always available — there was
  previously no way back to the main menu short of quitting the app.
- **A Rank line in the HUD** ("Rank: 3 / 16") — computed every state change
  from data the game already has, without exposing anyone's exact score
  (that stays deliberately limited — see the network-visibility section
  above — but *some* continuous feedback beats none).
- **An explicit mechanical summary on every action** — Solo and
  Intelligence narration is prefixed with the literal point delta ("Solo
  work: +58 pts. ...") before the AI's in-character flavor text.
- **An Achievements screen** (style-select → **Achievements**) listing all
  8 with locked/unlocked state — they existed before but were only ever
  glimpsed as a toast or a bare count, never a place to actually see what
  they were or how many were left.
- **A hover profile on every villager on the Home map** (`_player_profile_lines()`)
  — name, specialty + a one-line translation of what it actually does
  ("Marketing — gets the word out, wins customers"), persona flavor, and
  the same network-visibility-gated connection info as the target picker.

### Second pass: shorter, hint-driven, and reordered — a second playtest

The guide above went through a second round of feedback: too much text,
icons requested over more paragraphs, and — more importantly — the guide
was spelling out exact mechanics (odds, payoff numbers, the Eq1-Eq3 zone
table) that the game is supposed to make you *discover*. It also caught a
real sequencing bug on the Market screen: the outcome banner appeared
*before* the conversation played out, and the screen closed itself on a
timer with no way to linger. Fixes:

- **Guide rewritten to be hint-driven, not a spoiler.** Instead of "Same-
  skill people have the best odds, Complementary the worst, here's the
  exact split," it now says specialties close to your own are an easier
  ask and reaching further is a bigger stretch — same idea, no numbers
  given away. Burnout and the mid-game payoff dip are now a soft warning
  ("getting turned down too many times wears you out... growing your
  network doesn't always feel good in the moment, stick with it") instead
  of a mechanical lookup table.
- **Small drawn icons** (`draw_icon()`) for Solo/Approach/Intelligence and
  a 4-dot skill wheel, replacing some of the paragraphs outright.
- **The player is framed as an entrepreneur**, and risk styles are now
  explicitly labeled with a strength and a weakness each, instead of a
  bare list of numeric modifiers.
- **Market screen reordered**: the outcome only reveals once the dialogue
  has fully played out, not before it — the point of reading the exchange
  was gone if the ending was already spoiled at the top. The auto-return
  timer is gone entirely; the screen now only closes when you click
  **Return to Village**, with an explicit "Click Return to Village to
  continue" hint once the result is showing.

### A villager's trade is now something you learn, not something you're told

Follow-up feedback: a bot's specialty (Marketing/Creativity/Finance &
Analytics/Operations) was visible for every villager the moment the game
started — in the target picker, in the hover profile, and as their
clothing color on the Home map — with no interaction required. That
defeated the point of Intelligence as a scouting tool: there was nothing
left to learn. Fixed with a new `App._known_players` set (`main.py`), added
to the moment you Approach or use Intelligence on someone (regardless of
outcome — the point is you've now met them) and persisted for the rest of
that game:

- Target-picker rows show "(unknown trade)" instead of a skill name until
  that player is known.
- The Home-map hover profile shows "Trade unknown — Approach or
  Intelligence to find out" instead of their specialty and persona flavor.
- Unknown villagers wear neutral gray on the Home map instead of their
  skill's color — otherwise the map itself would give away for free what
  the picker was hiding.
- Connection-count visibility (direct/indirect/unknown, from the
  network-visibility work above) is unaffected — this is a separate,
  independent layer of "what you actually know about someone."

## Story mode: the game was repetitive and taught nothing

Direct feedback: "the game has a story and learning that is missing...
just by playing players learn nothing." Every round was mechanically
identical — the same three buttons, twenty times, no throughline. Fixed by
framing the player explicitly as an entrepreneur on a journey to build his
business, and weaving self-contained game-theory scenarios ("chapters")
into specific rounds of that journey — new module `story_games.py`,
minimal hook into `game_logic.py`:

- **`game_logic.py`**: `GameManager.story_encounter_rounds` maps a round
  number to an encounter id (round **1** → `"quality_price"` by default —
  the story opens the game immediately, before three rounds of the
  ordinary village loop). When that round comes up,
  `submit_story_encounter(points_delta, encounter_id)` applies the
  encounter's own payoff directly to the player's score — deliberately
  *not* stacked on top of the normal zone-based Solo payoff, since the
  encounter's outcome **is** that round's result, not a bonus.
- **`story_games.py`** (no pygame dependency, same rationale as
  `game_logic.py` — content and payoff logic should be testable on their
  own): each `Encounter` has a narrative setup, 2+ choices, a `resolve()`
  function computing the payoff, a quiz question that asks the player to
  explain what just happened, an optional `PayoffMatrix` (an actual 2x2
  table, not just prose describing one), and `lesson_pages` — the
  teaching reveal can be staged across multiple pages rather than one
  wall of text.
- **Chapter 1 — "Building Your Stall"**: opens the game by casting the
  player as a farmer who's decided to start a fresh-vegetable stall from
  his own harvest. The first real decision is a one-shot simultaneous
  quality/price game: what to pay the stall's materials supplier before
  knowing whether he'll deliver sturdy wood or cheap wood; he decides
  simultaneously, knowing the player is a one-time customer he'll never
  see again. The payoff table (`_QUALITY_PRICE_PAYOFFS`) is a genuine
  dominant-strategy Nash equilibrium isomorphic to the Prisoner's Dilemma:
  Low-quality strictly dominates for the supplier regardless of what the
  player pays, Pay-Low strictly dominates for the player regardless of
  what he delivers, and yet mutual honesty (High price + High quality)
  would leave **both** sides strictly better off than the equilibrium
  outcome — verified by direct payoff-matrix assertions, not just
  eyeballed. This is the same structure as Akerlof's "Market for Lemons."
- **Two-stage lesson, taught in order** (per direct feedback: show the
  actual matrix, name Prisoner's Dilemma first, then generalize to Nash
  equilibrium — not the reverse): lesson page 1 names the situation as a
  Prisoner's Dilemma and shows the full 2x2 matrix so the dominant-strategy
  claims can be checked cell by cell; page 2 defines Nash equilibrium
  properly (no one benefits from switching alone) against the *same*
  matrix, with the equilibrium cell highlighted, and explicitly calls out
  that a Nash equilibrium being "stable" isn't the same as it being
  "good" — the Pareto-better outcome sits right there in the matrix,
  unreachable by either side alone.
- **UI flow** (`main.py`, screen_state `"encounter"`): setup → choice →
  result (plain mechanical outcome, no game-theory jargon yet) → quiz
  (ask the player to explain *why*) → the paginated lesson (reveal the
  concept regardless of whether the quiz answer was right — the point is
  to teach, not to gate the explanation behind a correct guess). The
  screen reuses the Market screen's pause pattern (`game.set_paused(True)`)
  so the round can't silently resolve while the player is still reading.
- **One statement at a time, not a wall of text** — direct feedback: "make
  the initial game information come as 1 statement at a time not 4 line
  all together so people can comprehend." `_draw_encounter_lines()` reveals
  narrative/lesson paragraphs one click at a time (cumulatively — earlier
  lines stay visible, nothing already read disappears), tracked by
  `encounter_line_index` and reset at every phase/page transition. The
  button reads "Next" while there's more to reveal and only becomes the
  real phase-advancing action ("Continue," "What does this mean?," etc.)
  once everything for that phase is on screen — on a lesson page, the
  payoff matrix itself only appears once its text has been fully read.
  Body text also moved to a dedicated larger font (`font_encounter` /
  `font_encounter_small`, 27pt/21pt vs the general UI's 22pt/18pt) — this
  screen is the densest reading in the game and was asked for bigger text
  specifically.
- **Built as a framework, not a one-off**: `story_encounter_rounds` is a
  dict and `STORY_ENCOUNTERS` is a lookup table, `PayoffMatrix` and
  `LessonPage` are reusable dataclasses, specifically so more chapters
  (subgame-perfect equilibrium via an extensive-form choice, the
  centipede game, different auction formats) can be added later as their
  own `Encounter` definitions without touching the round loop again.

## Known limitations

- Visuals are flat vector shapes, not sprite art — intentional, matches the
  "keep graphics limited" brief, just with more detail than plain circles
  and rectangles (see above).
- Bots are fully silent — only your own actions get AI narration, to keep
  latency and API cost down during a playthrough.
- Persistence is cross-*game* only (`save_data.json`), not mid-game — closing
  the window mid-round loses that round; nothing earlier is lost.
- Window size is fixed at 1100×720 (not resizable).
