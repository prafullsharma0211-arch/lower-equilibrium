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
- `test_logic.py` — runs a full 10-round game with the human auto-playing
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
- **16 players, 10 rounds** by default (`GameManager.__init__` args) — the
  16-step global zone table (reaching N=15+ "Eq3") is still what bots play
  against for the whole game; the human only reaches rounds 9-10 of it, so
  their own progress reads off a separate, compressed finale table instead
  (see "The finale, compressed: rounds 9-10" below).
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

## Chapter 2 — The Road Fund: generalizing to N players

Chapter 1 taught a 2-player dominant-strategy game. The natural next step,
and a good test of whether the framework above actually generalizes, was
an N-player version: a public-goods game with a matching-grant twist,
landing at round 8.

**The setup**: the player and 4 other shopkeepers can each contribute Rs
100 toward repairing the market road. A traveling merchant offers to match
whatever the five shopkeepers raise together, rupee for rupee. The
resulting fund's benefit is split equally among all five shopkeepers,
whichever of them actually paid in.

**The math, worked and verified before writing a line of narrative**
(`_road_fund_net()` in `story_games.py`): contributing your own rupee
only returns 2/5 of a rupee to *you* (the pool is doubled by the match,
then divided five ways), so holding back beats contributing at **every**
possible level of what the other four do — asserted directly:

```
S=  0  contribute0 -> net=   0   contributeFull -> net= -60   (0 wins: True)
S=100  contribute0 -> net=  40   contributeFull -> net= -20   (0 wins: True)
S=200  contribute0 -> net=  80   contributeFull -> net=  20   (0 wins: True)
S=300  contribute0 -> net= 120   contributeFull -> net=  60   (0 wins: True)
S=400  contribute0 -> net= 160   contributeFull -> net= 100   (0 wins: True)
```

That's a genuine dominant strategy, not just a plausible-sounding story —
and just as in Chapter 1, if all five *had* contributed, everyone would
net **+100** instead of the equilibrium's **0**: a real Pareto improvement
that individual rationality can't reach alone. The other four shopkeepers
are modeled as already-rational free-riders (fixed at Rs 0), same
deliberate-determinism choice as the Chapter 1 supplier.

**Two structural additions this chapter needed:**
- **`PayoffCell.col_payoff` is now optional.** A literal 2-player matrix
  doesn't exist for a 5-player game — collapsing "the other 4" into one
  column and giving it a single payoff would misrepresent each of their
  actual incentives. Chapter 2 instead shows a one-sided *sensitivity
  table*: the player's own payoff under two scenarios for what the group
  does, which is the methodologically honest way to demonstrate dominance
  with more than two decision-makers (compare within a column, i.e. hold
  everyone else's behavior fixed — never compare across a row that
  implies four other people all flipped their choice at once).
- **`LessonPage.highlight_row`**: the equilibrium here isn't one cell,
  it's a whole row (holding back dominates in *every* column) — a real
  and useful contrast with Chapter 1's single highlighted cell, called
  out explicitly in the lesson text.

**A layout bug this chapter caught**: the row label "Contribute your
share (Rs 100)" was wider than its column and silently rendered behind
the next cell, undetected by Chapter 1 because its labels happened to be
short enough to fit. `_draw_payoff_matrix()` now wraps row/column labels
and sizes cells to whatever's actually longest instead of assuming a
fixed width — and the lesson-phase action button now anchors below the
matrix's real rendered height instead of a fixed offset from the panel
bottom, so a taller table can't silently push the button off-panel (or,
briefly during the fix, off the bottom of the screen entirely).

**Two more contribution levels, Rs 25 and Rs 50** — direct feedback asking
for more than a binary in/out choice, so the decision doesn't reduce to an
obvious coin flip. `_ROAD_FUND_CHOICE_AMOUNTS` is now the single source of
truth mapping each of the 4 choice ids (`free_ride`, `contribute_25`,
`contribute_50`, `contribute`) to a rupee amount, feeding both
`_resolve_road_fund()` and a matrix comprehension that builds all 8 cells
(4 rows × 2 columns) from it, rather than hand-writing each cell. Verified
before writing any narrative that dominance survives the added
granularity rather than assuming it: `net(c) = floor(2c/5) - c` is linear
in `c`, so *every* row is strictly worse than the one above it in *both*
columns —

```
                  All free-ride   All contribute
Contribute Rs 0        +0              +160
Contribute Rs 25      -15              +145
Contribute Rs 50      -30              +130
Contribute Rs 100     -60              +100
```

— which means the lesson gets a genuinely new, true claim to make, not
just a cosmetic new button: there's no clever "hedge" amount hiding in
the middle that beats contributing nothing, holding back completely
remains the unique dominant choice, and partial contributions lose money
in direct proportion to how much you put in.

**A second layout bug, caught the same way as the first**: going from 2
rows to 4 pushed the lesson pages' text-plus-table combination past the
bottom of the fixed 1100×720 window — the "Next" button rendered off
the bottom of the screen entirely and was unclickable, only visible via a
headless screenshot, not by reasoning about the layout code. Two things
were driving it, both fixed: the row label "Contribute nothing" was the
only one of the four that wrapped to two lines, which forced *every* row
in the table to that taller height even though the other three fit on
one line (renamed the row labels to "Nothing" / "Rs 25" / "Rs 50" / "Rs
100," short enough that none of them wrap); and lesson page 1's prose had
grown to 3 paragraphs partly re-explaining mechanics the setup narration
already covers (the merchant's match, the equal split), trimmed to 2
tighter paragraphs. Both fixes verified by instrumenting
`_draw_payoff_matrix()` to print its actual rendered bottom edge and
confirming the following button's rect stays within the 720px window
before trusting a screenshot to confirm it visually.

## Points are rupees, and the game now says so

"Points" was always meant to represent money — the encounters already
narrated outcomes as "Net effect on your business: -60 rupees" — but the
HUD called it "Points," everyone started at 0, and Chapters 1-2 landed at
rounds 1 and 8. Fixed:

- **Every player starts with `STARTING_MONEY` = Rs 1000** (`game_logic.py`),
  human and bots alike. It's a flat amount added equally to everyone, so it
  shifts every final total up by exactly 1000 and never changes relative
  standings — confirmed by re-running `test_logic.py` and diffing the
  standings against the pre-change run (same ranks, same gaps, totals all
  +1000).
- **The HUD corner now reads "Money: Rs {amount}"** instead of "Points:
  {amount}," alongside Round/Connections/Zone/Rank — this was the actual
  ask, everything else followed from taking it seriously throughout the
  rest of the game's text: the Market outcome banner, the Solo/Intelligence
  narration prefixes, the round-summary line (including the AI-facilitator
  prompt text it's built from, so an API-connected game narrates in rupees
  too), the end-of-game standings and winner line, and the style-select
  career-stats line all switched from "N pts" to "Rs N."
- **Chapter 2 now lands at round 2**, immediately after Chapter 1 at round
  1, instead of round 8 — the two lessons open the game back-to-back
  rather than being spread across the first third of it.
- **Fixed a real bug this surfaced**: the "High Scorer" achievement
  unlocked at 1000 points, which — now that everyone *starts* at 1000 —
  would have fired trivially the instant any game began. Retargeted to
  `STARTING_MONEY * 2` (double your money, Rs 2000) with an updated
  description, and verified directly that firing every callback at game
  start unlocks nothing.

## Chapter 3 — The Cold Storage Bet: a Stag Hunt

Chapters 1 and 2 both taught dominant-strategy games — there was always a
single best move, regardless of what anyone else did. Chapter 3 (round 3,
right after Chapter 2) is deliberately the opposite kind of game: a **Stag
Hunt**, where the right move depends entirely on what the other side does,
and there are two genuinely different stable outcomes instead of one.

**The setup**: a rare, fast-spoiling hill vegetable is worth triple the
usual price — but only sellable if a warehouse owner separately builds
cold storage. The storage is only worth building if there's perishable
trade to justify it. Neither the player nor the warehouse owner knows the
other's decision in advance.

**The payoff table** (`_STAG_HUNT_PAYOFFS` in `story_games.py`), verified
algebraically before writing any narrative:

```
cell (Import Special, Builds Storage)  payoffs=(150, 150)  Nash equilibrium: True
cell (Import Special, Doesn't Build)   payoffs=(-100, 40)  Nash equilibrium: False
cell (Import Regular, Builds Storage)  payoffs=(40, -80)   Nash equilibrium: False
cell (Import Regular, Doesn't Build)   payoffs=(40, 40)    Nash equilibrium: True
mutual-commit Pareto-dominates mutual-safe: True (150, 150) vs (40, 40)
```

Exactly the defining Stag Hunt shape: both same-action cells are stable
(mutual commitment and mutual caution), both mismatched cells are not (the
side who committed alone always wants to retreat next time), and the
mutual-commitment equilibrium is strictly better for both sides than the
mutual-caution one — yet nothing *forces* either side toward it. The
warehouse owner is scripted to play it safe (no established trust with a
still-new farmer), so importing alone costs Rs 100 while playing safe
alongside him nets Rs 40 — same deliberate-determinism choice as the
Chapter 1-2 opponents.

**One more framework addition**: `LessonPage.highlight_cells` (a list,
alongside the existing single-cell and whole-row highlight options) — a
coordination game genuinely has more than one Nash equilibrium, and the
lesson page highlights both simultaneously rather than picking one to
show, with the lesson text distinguishing the payoff-dominant one (better
for both, but risky to trust) from the risk-dominant one (safe, but worse
for both).

Three chapters now form a real progression: a single dominant-strategy
equilibrium (Ch1) → the same idea generalized to N players (Ch2) → a game
with no dominant strategy at all, where the outcome hinges on trust
instead of self-interest (Ch3).

## Chapter 4 — The Juice Stall Standoff: Chicken, and burning your bridges

Chapter 3 was a Stag Hunt: matching the other side was the *good* outcome.
Chapter 4 (round 4, right after Ch3) is its mirror image — a **Game of
Chicken** (equivalently, Hawk-Dove), where matching is the *disaster* and
the two stable outcomes both involve the two sides doing different things.

**The setup**: the player spots a gap in the market for a green-juice
stall; so has a rival vendor. The market can only support one. If both
open, they crash — both lose money undercutting each other. If exactly
one opens, that one wins the whole new market and the other is unaffected.

**The payoff table** (`_CHICKEN_PAYOFFS` in `story_games.py`), verified
algebraically before writing narrative:

```
cell (Open, Rival opens)   payoffs=(-120,-120)  Nash equilibrium: False
cell (Open, Rival backs)   payoffs=(200, 20)     Nash equilibrium: True
cell (Don't, Rival opens)  payoffs=(20, 200)      Nash equilibrium: True
cell (Don't, Rival backs)  payoffs=(20, 20)        Nash equilibrium: False
T (win alone) > R (mutual restraint) > P (mutual crash): True
```

The exact opposite shape from Chapter 3: there, the two *matching* cells
were the equilibria; here, the two *mismatched* cells are. Winning alone
beats mutual restraint beats mutual crash — the defining Chicken ranking.

**A genuine third move, not just two**: alongside the normal "open
quietly" (Hawk with no signal) and "don't open" (Dove), the player can
"announce it loudly — sign a lease, tell the market" — a public,
irreversible commitment. This is Thomas Schelling's "burning your
bridges" (the steering-wheel-out-the-window move from the classic telling
of Chicken): committing first doesn't just change what *you* do, it
changes the *rival's* best response. `_resolve_juice_stall()` models this
directly — quietly opening with no signal meets the rival's own default
plan to open too (mutual crash, since neither side had reason to expect
the other to yield); not opening leaves the rival's default untouched
(they win, you're safe); publicly committing is the only choice that
flips the rival's default from Hawk to Dove. The three outcomes rank
exactly as the lesson intends: commit (+200) > don't open (+20) > open
quietly (-120) — credible commitment strictly beats both playing it safe
*and* gambling blind.

Four chapters now cover: a single dominant-strategy equilibrium (Ch1) →
the same idea at N players (Ch2) → a coordination game with two
same-action equilibria, decided by trust (Ch3) → an anti-coordination
game with two different-action equilibria, decided by who commits first
(Ch4).

## A drawn icon per chapter, not just paragraphs

Direct feedback: explain things "in the form of image rather than text" to
make the lessons more interesting, not just another wall of paragraphs
(even with the payoff matrix already there). Each chapter now gets its own
small drawn icon (`draw_icon()` in `main.py`, same hand-drawn-shapes
approach as the how-to-play guide's icons — no external art assets
anywhere in this project) shown in the corner throughout setup, choice,
result, and lesson: a crate-and-coin for Chapter 1's trade, a cracked road
with the fund's coins for Chapter 2, a cold-storage crate with a wilting
leaf for Chapter 3, two vendors' claims facing off for Chapter 4's
standoff. `Encounter.chapter_icon` names which one; it's deliberately
*not* shown during the quiz phase, since the answer buttons there span
the full panel width and would collide with it.

## The setup narration is a horizontal storyboard, not a text stack

Follow-up feedback, more specific than the chapter-icon pass above: give
*each individual statement* of a chapter's setup its own icon, laid out as
"one box after another horizontally," not stacked paragraphs even with a
corner icon attached. Restructures how a chapter opens:

- **`Step` (new dataclass, `story_games.py`)** replaces the old
  `setup_lines: list[str]` with `setup_steps: list[Step]`, where each
  `Step` carries an `icon`, a short `caption` (a few words, for the
  storyboard box) and the full `text` (the sentence shown as detail
  underneath) — used by all four chapters. Four new icons were added to
  `draw_icon()` to cover the new per-statement content: `idea` (lightbulb,
  spotting an opportunity), `warning` (caution triangle, something could
  go wrong), `question` (uncertainty about what the other side will do),
  `scale` (a balance, the decision point) — reused alongside the existing
  four chapter icons wherever a step is literally about that chapter's
  theme (e.g. Chapter 3's storage steps reuse `cold_storage`).
- **The setup phase now renders a row of boxes**, one per step, left to
  right: reached steps show their icon and caption (the active one
  highlighted gold, earlier ones dimmed but still visible — nothing seen
  disappears), upcoming steps show a locked "?" placeholder, and thin
  connector lines join them like a stepper/subway-map UI. The full
  sentence for the *current* step renders underneath, exactly as before;
  clicking "Next" advances both the active box and the detail text
  together.
- **Verified every caption actually fits** rather than assumed to: a
  direct check (`wrap_text` against the real box width for every step in
  every chapter) caught one caption clipping at the box's bottom edge in
  its rendered screenshot ("Neither of you knows," Chapter 3 — wrapped to
  a second line the original box height didn't leave room for). Fixed
  both ways at once: reworded it shorter ("Mutual unknown") *and* grew the
  box height to comfortably fit any two-line caption, so a future
  chapter's longer caption can't reintroduce the same clip — the same
  robustness lesson as the payoff-matrix label-wrapping fix earlier: size
  the container to the content, don't assume the content will fit a
  guessed size.

## A "< Back" button on every encounter page

Feedback from a screenshot of a Chapter 3 lesson page: there was no way to
step backward through a chapter's setup boxes, its result explanation, or
its lesson pages — only "Next." Added a back button, top-left of the panel,
present across the whole encounter flow:

- **`_draw_encounter_back_button()`** draws a small "< Back" pill at
  `panel.left + 16, panel.top + 18`. The chapter title shifted right (from
  `panel.left + 24` to `panel.left + 108`) to make room for it without
  overlapping — checked against the longest chapter title in the game
  ("Chapter 4: The Juice Stall Standoff") to confirm it still clears the
  chapter icon on the opposite corner.
- **`_encounter_can_go_back()` / `_encounter_go_back()`** define what "back"
  means in each phase: within the setup storyboard or the result text it
  just decrements the revealed-line index one step at a time; from the quiz
  it returns to the result phase, fully revealed; from a lesson page it
  goes to the previous page (fully revealed) or, from the first page, back
  to the quiz. The button is hidden/disabled wherever there's nowhere to go
  (the very first setup step, or the first result line).
- **Deliberately does not go back into "choice."** Once a choice is made,
  `submit_story_encounter()` applies its payoff to the player's points
  immediately — that's already happened by the time "result" is showing.
  Letting "back" reach into "choice" again would let a player see the
  outcome and then pick a different answer with the outcome already known,
  which defeats the point of a chapter that's about committing to a
  decision under uncertainty. `_encounter_can_go_back()` returns `True` for
  the "choice" phase itself (so you can step back into "setup" to reread
  it), but nothing after a choice is submitted can step back past "result."
- **Verified headlessly** that this invariant actually holds, not just that
  it reads that way: made a real choice, advanced through the result,
  clicked back repeatedly, ran more game-update cycles, and confirmed the
  player's points changed by exactly the one committed payoff regardless of
  how much backward/forward navigation happened afterward — no
  double-application, no way to re-roll a decision.

## 10 sessions, not 20 rounds: the course moved, so the game did too

The course this game supports restructured to 10 in-class sessions, so
`GameManager.total_rounds` moved from 20 to 10 and `story_encounter_rounds`
grew from 4 entries to 8. New round mapping: Chapters 1-4 unchanged at
rounds 1-4, four new chapters (below) at rounds 5-8, and the connections
game — previously 16 rounds (5-20) — compressed to just its last 2 rounds
(9-10), now explicitly the finale ("as we grow our business") rather than
the bulk of the game.

One knock-on fix: `special_event_round` ("Market Day," a one-round bonus to
Approach) used to be computed as `total_rounds // 2`. With 10 rounds that
lands on round 5 — now a story round with no Approach actions at all, human
or bot, so the event would silently never fire. Pinned explicitly to
`total_rounds - 1` (round 9) instead, so it still lands with one round left
to feel its effect, inside the connections-game portion where Approach
actually happens.

## Chapter 5 — The Two-Cart Deal: the Centipede Game

Sequential moves and backward induction, and the first chapter that
doesn't fit the "one choice, one resolve()" shape every other chapter
uses — Chapter 5 is genuinely turn-based: a shared kitty starts at Rs 20 and
doubles every time it's passed instead of taken, alternating Player → NPC →
Player → NPC → Player → NPC (3 real player decisions). Taking ends the deal
immediately and keeps the whole kitty for whoever took it.

- **The NPC is deterministically scripted to let it ride on its first two
  turns and take everything on its third** — same "deliberately
  deterministic opponent" discipline as every earlier chapter, chosen so the
  game has a genuine 3-decision arc (`CENTIPEDE_PLAYER_POTS = [20, 80,
  320]`, `CENTIPEDE_FINAL_POT = 640` in `story_games.py`) instead of
  collapsing to a trivial first move. Verified by working backward from that
  guaranteed final NPC take: since it's a certainty, the player's own last
  turn should always take (passing there guarantees zero); knowing that,
  reasoning keeps unraveling the same way all the way back to turn 1 — pure
  backward induction says take immediately, for the smallest pot on the
  table, even though what actually happens in the scripted scenario (letting
  it ride twice before the NPC finally grabs it) tempts the player to keep
  pushing their luck. That gap between the theoretical prediction and the
  scripted opponent's actual behavior is the whole point of the chapter, and
  mirrors real centipede-game experiments, where most people don't take
  immediately even though the theory says they should.
- **main.py gets a small, chapter-specific chain of choice sub-phases**
  (`"choice"` → `"choice2"` → `"choice3"`, see `_draw_centipede_step` /
  `_encounter_centipede_take` / `_encounter_centipede_pass`) instead of a
  generic multi-turn engine — deliberately, since only this one chapter
  needs it. Each sub-phase reuses the exact same choice-button rendering as
  every other chapter; once the chain resolves to one of 4 terminal
  outcomes, it calls the *same* `resolve(choice_id, rng) -> EncounterOutcome`
  contract every other chapter uses (`_encounter_resolve_choice`, factored
  out of the old `_encounter_choose` so both paths share it) — so
  `story_games.py`'s shape doesn't change at all, and the quiz/lesson/
  summary/back-button phases downstream are 100% shared, unmodified code.
  Back-navigation extends the same way: `"choice3"` → `"choice2"` →
  `"choice"` → last setup step, one more link in the existing chain.

## Chapter 6 — The Same Supplier, All Season: Iterated Prisoner's Dilemma

Reputation, forgiveness, and repeated games — literally the same stage game
as Chapter 1 (this chapter reuses `_QUALITY_PRICE_MATRIX` and
`_QUALITY_PRICE_PAYOFFS` unchanged), but played 8 times against the same
opponent instead of once, which is what changes the incentives: a dominant
strategy to defect in a one-shot game no longer dominates once your move can
be answered next round.

- **The player picks a whole-season STRATEGY, not a single move** — Always
  Distrust / Tit-for-Tat / Grim Trigger / Forgiving Tit-for-Tat (defects only
  after TWO straight observed defections) — matching the brief's request
  that players "choose strategies" rather than click through 8 individual
  rounds. `resolve()` genuinely *simulates* the 8-round match against a
  fixed Tit-for-Tat supplier, with a real 10% per-round chance, independent
  each side, that an intended cooperate is miscommunicated and observed as a
  defection — never the reverse, matching "a cooperative move is
  miscommunicated as a defection." No new UI needed: the result is one
  `result_lines` entry per round plus a final total, reusing the existing
  one-line-at-a-time reveal every chapter already has.
- **Verified by actual simulation, not asserted from theory**: 4000 seeded
  8-round runs gave mean totals of Always Distrust -52.6, Grim Trigger
  166.5, Tit-for-Tat 200.7, Forgiving Tit-for-Tat 261.9 rupees — the
  intended ranking, and Always Distrust is a net LOSS on average despite
  winning its first round (it exploits the supplier's initial trust, then
  both sides mirror each other into permanent mutual punishment for the
  remaining 7 rounds). A separate check across longer horizons (20, 40
  rounds) confirmed Tit-for-Tat's edge over Grim Trigger widens the longer
  the relationship runs, since Grim Trigger's one uncorrectable trigger
  costs it more the longer it has to live with the fallout — that's the
  actual, measured reason "forgiving a single slip" is framed as the best
  strategy in the lesson, not a guess.

## Chapters 7 & 8 — the cow you can't inspect, then proving the goat is worth it

Asymmetric information, played from both sides of the same kind of market:
Chapter 7 is Akerlof's "Market for Lemons" from the *uninformed buyer's*
side, Chapter 8 is signaling from the *informed seller's* side — a direct
answer to the trap Chapter 7 sets up.

- **Chapter 7**: the player is buying a milking cow whose true quality only
  the seller knows. The market has already fully unraveled before any offer
  is made — genuinely healthy cows' owners rationally stay out of a market
  where buyers can't verify quality, so no price a buyer offers (fair or
  generous) brings one to market; every offer nets a Lemon, and a bigger
  offer just overpays for the same guaranteed Lemon (Rs 240 fair offer nets
  -160; Rs 320 premium offer nets -240; walking away nets 0 — verified
  dominance: 0 > -160 > -240). This is deliberately the starkest, most
  teachable form of Akerlof's result (full unraveling), not a softer
  "sometimes you get unlucky" version.
- **Chapter 8**: the player now owns a genuine prize goat and must decide
  whether to pay Rs 120 for a costly, verifiable signal (a vet
  certification) instead of settling for the Rs 300 pooling price an
  unverified goat gets. Certifying nets 500-120=380, beating the 300
  pooling price — but the lesson also checks the case the player *isn't*
  in, to establish the signal's credibility: if the goat were merely
  ordinary (worth 100 verified), certifying would net 100-120=-20, far
  worse than pooling at 300 — so an ordinary-goat owner would never
  rationally pay for the same certificate. That gap between what's worth
  proving and what isn't is exactly what makes a costly signal credible to
  a buyer in the first place, verified with real numbers rather than
  asserted from Spence's theory alone.
- **Two real layout bugs caught here**, both from "size the container to
  the content" gaps that had gone unnoticed because no earlier chapter's
  text was long enough to trigger them: (1) `_encounter_button`'s
  `sub_label` (a choice's detail text) was never wrapped — Chapter 6's
  "forgive a single slip" detail ran straight off the panel's right edge
  instead of clipping to its button. Fixed by wrapping it against the
  button's own width and sizing the button's height to fit
  (`_encounter_choice_button_rect`). (2) `_draw_payoff_matrix`'s row-label
  gutter (the vertical "You" label left of the row-option boxes) was a
  fixed 36px, sized only for one-word labels — Chapter 7's two-word "Your
  offer" overflowed it and got silently painted over by the row boxes drawn
  after it. Fixed by measuring the actual label and sizing the gutter (and
  the row-option box offset it feeds into) to match, the same fix shape as
  the row/column *option* wrapping fixed earlier for Chapter 2. Confirmed
  via screenshot that both fixes are pixel-identical to the old layout for
  every existing chapter's short labels, and correct for the new long ones.

## The finale, compressed: rounds 9-10

The connections/network game used to be the bulk of the game (16 rounds);
now it's just the last 2, and two things had to be rethought so it still
lands its own lesson in that much less room.

- **A separate, small finale payoff table**, not a rescale of the existing
  one. The original 16-step zone table (`_BASE_PAYOFF`/`_ZONE_NAMES`) is
  shared by every player — bots keep playing the connections game normally
  every round of the whole 10-round game, unlike the human, who only reaches
  it at rounds 9-10 — and its balance was carefully tuned and verified via
  repeated simulation already. Rescaling it globally to fit 2 rounds would
  also silently warp 8 rounds of bot economy and need re-verifying the whole
  leaderboard. Instead, `get_finale_base_payoff`/`get_finale_zone_name` are
  a separate, small 2-tier table (`_FINALE_BASE_PAYOFF = [45, 90]`) used
  *only* for the human, *only* during rounds 9-10 — an honest 2-tier version
  of the same lesson (Eq1 solo trap vs Eq3 global optimum) rather than a
  pretend 3-tier trap/valley/optimum arc whose 3rd tier could never actually
  pay out with only 2 rounds to realize it in. Verified by direct
  simulation: playing it safe both rounds nets exactly 90 (deterministic);
  reaching out both rounds nets a mean of 135 with real downside risk (worst
  observed case ~83) — a meaningfully better expected outcome for taking the
  risk, without being a free lunch.
- **Connections gained DURING the finale, not lifetime connections.** Bots
  keep approaching everyone — including the human — all through the story
  rounds, so a player can arrive at round 9 already holding a connection or
  two just from being on the receiving end of a bot's Approach, without
  ever having taken an action themselves. Caught via a full 10-round
  headless playthrough that showed the human's zone reading "Eq3 — Global
  optimum" at the very start of round 9, before making a single finale
  decision. Fixed by capturing a baseline (`GameManager.
  _finale_baseline_connections`) the moment the finale begins, and keying
  the finale table off `connections - baseline` (`human_finale_connections()`)
  everywhere it's used — payoff calculation and the HUD's zone label alike
  — instead of the player's raw lifetime connection count.

## Chapter completion shows what you actually earned

Direct feedback: "At the end of each chapter, show how much money you have
and how much you gained or lost in the round." The result phase already
showed a chapter's net effect once, mid-narration — but nothing restated it
next to the running total at the moment the chapter actually closed, so a
player had to go check the HUD separately to see what it added up to.

- New `encounter_phase == "summary"`, inserted between the last lesson page
  and `_encounter_finish()` — applies to all 8 chapters automatically, since
  it's wired into the shared phase machine every chapter already goes
  through, not chapter-specific code. Shows the chapter's net rupees
  (colored green/red) and the resulting total money, with a "Continue your
  journey" button.
- The back button (shipped just before this round of work) extends to cover
  it: back from `"summary"` returns to the lesson's last page, fully
  revealed, the same pattern used for every other phase transition.
- Verified headlessly, including the invariant that matters most: made a
  real choice, advanced to the summary screen, backed up into the lesson and
  forward again, and confirmed the committed payoff is applied to the
  player's points exactly once no matter how much back-and-forth happens —
  extending the same check the back button's own verification already
  established for every other phase.

## Known limitations

- Visuals are flat vector shapes, not sprite art — intentional, matches the
  "keep graphics limited" brief, just with more detail than plain circles
  and rectangles (see above).
- Bots are fully silent — only your own actions get AI narration, to keep
  latency and API cost down during a playthrough.
- Persistence is cross-*game* only (`save_data.json`), not mid-game — closing
  the window mid-round loses that round; nothing earlier is lost.
- Window size is fixed at 1100×720 (not resizable).
