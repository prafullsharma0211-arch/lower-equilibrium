"""Lower Equilibrium — Pygame edition.

A single window with two screens: Home (village circle around the hut, farm
patch, animal pen, tool shed, and the action buttons) and Market (loaded in
whenever you choose Approach). Bots resolve instantly and silently; only your
actions get narrated by the AI facilitator.
"""

from __future__ import annotations

import math
import os
import random

import pygame

import save_data
from achievements import ACHIEVEMENTS, AchievementTracker
from facilitator import FacilitatorClient, parse_dialogue
from game_logic import (
    ActionType,
    ApproachOutcome,
    ApproachResult,
    GameManager,
    IntelligenceResult,
    JobType,
    RiskStyle,
    SkillType,
    SoloResult,
    get_zone_name,
)

WIDTH, HEIGHT = 1100, 720
FPS = 60

COLOR_BG_HOME = (58, 102, 54)
COLOR_BG_MARKET = (135, 112, 79)
COLOR_PANEL = (22, 22, 28)
COLOR_BUTTON = (45, 100, 190)
COLOR_BUTTON_DISABLED = (65, 65, 75)
COLOR_TEXT = (240, 240, 240)
COLOR_TEXT_DIM = (180, 180, 180)
COLOR_HUMAN = (255, 255, 255)
COLOR_LINE = (230, 230, 230)
ROAD_COLOR = (196, 172, 122)

SKILL_COLORS = {
    SkillType.MARKETING: (217, 76, 76),
    SkillType.CREATIVITY: (76, 166, 230),
    SkillType.FINANCE_ANALYTICS: (89, 191, 102),
    SkillType.OPERATIONS: (230, 179, 51),
}
COLOR_UNKNOWN_SKILL = (130, 130, 130)

JOB_ANIM = {
    JobType.FARMING: "farming",
    JobType.ANIMAL_HUSBANDRY: "tending animals",
    JobType.MAINTENANCE: "doing upkeep",
}

RISK_STYLE_INFO = {
    RiskStyle.CAUTIOUS: ("Cautious", "Strength: steady, reliable growth. Weakness: even wins are smaller."),
    RiskStyle.BALANCED: ("Balanced", "No real strength, no real weakness -- the default way to play."),
    RiskStyle.BOLD: ("Bold", "Strength: big swings pay off big. Weakness: costly runs of bad luck."),
}

SKILL_INFO = {
    SkillType.MARKETING: ("Marketing", "gets the word out, wins customers"),
    SkillType.CREATIVITY: ("Creativity", "dreams up new ideas and products"),
    SkillType.FINANCE_ANALYTICS: ("Finance & Analytics", "keeps the books, reads the numbers"),
    SkillType.OPERATIONS: ("Operations", "keeps the day-to-day running"),
}

ACTION_TOOLTIPS = {
    "solo": ["Work your own business.", "Safe, steady payoff — no risk."],
    "approach": ["Try to team up with someone.", "Bigger reward, but it's a real ask."],
    "intelligence": ["Scout someone before you Approach.", "Small cost, useful edge."],
}

# Short and hint-driven on purpose — a first pass at this guide spelled out
# exact odds and payoff numbers and a playtester said it was both too much
# text AND gave away the whole strategy. This version explains what to do
# without solving the game for you.
HELP_PAGES = [
    ("Welcome", "solo", [
        "You're an entrepreneur in a small village, trying to grow your "
        "network over 20 rounds.",
        "Every round, you and 15 other villagers each quietly make one "
        "move. Then the round resolves and the next begins.",
        "Goal: end Round 20 with the most points.",
    ]),
    ("Your three moves", "approach", [
        "Solo — work your own business. Safe, steady income.",
        "Approach — go meet someone at the market and try to team up. "
        "Bigger reward, but it's a real ask: they might say yes, stay "
        "unsure, or turn you down.",
        "Intelligence — do a little homework on someone before you "
        "Approach them. Small cost, useful edge.",
    ]),
    ("Village trades", "wheel", [
        "Every villager has a specialty: Marketing, Creativity, "
        "Finance & Analytics, or Operations.",
        "Working with someone close to your own specialty is an easier "
        "ask. Reaching further across the village is a bigger stretch — "
        "harder to land, worth more when it works.",
    ]),
    ("A few honest hints", None, [
        "Getting turned down too many times in a row wears you out — "
        "you'll need to shake it off before trying again.",
        "Growing your network doesn't always feel good in the moment. "
        "Stick with it.",
        "You only really know how someone's doing if you know them — "
        "directly, or through a friend of yours.",
    ]),
    ("Getting started", None, [
        "Pick how you operate before your first game (see the strengths "
        "and weaknesses on the next screen) — hover any button in-game "
        "for a quick reminder of what it does.",
        "8 achievements to earn, and your stats carry over between games "
        "— check Achievements from the main menu.",
        "Lost? Menu takes you back any time; ? Help reopens this guide.",
    ]),
]

SKY_TOP = (117, 178, 222)
SKY_HORIZON = (219, 197, 150)
MARKET_HORIZON_Y = 230
MARKET_GROUND_TOP = (168, 138, 92)
MARKET_GROUND_LOW = (140, 112, 71)
SKIN_TONE = (238, 202, 164)


def _draw_vertical_gradient(surface, rect, top_color, bottom_color, step=3):
    x, y, w, h = rect
    for row in range(0, h, step):
        t = row / max(1, h - 1)
        color = tuple(int(top_color[i] + (bottom_color[i] - top_color[i]) * t) for i in range(3))
        pygame.draw.rect(surface, color, (x, y + row, w, step))


def draw_icon(surface, name, center, scale=1.0):
    """Small drawn glyph (hut / handshake / magnifying glass / skill wheel)
    standing in for the three actions in the how-to-play guide — a
    playtester asked for icons over more paragraphs to read."""
    x, y = center
    if name == "solo":
        w, h = 20 * scale, 14 * scale
        wall = pygame.Rect(0, 0, w, h)
        wall.center = (x, y + 4 * scale)
        pygame.draw.rect(surface, (150, 108, 66), wall, border_radius=2)
        roof = [(wall.left - 3 * scale, wall.top), (wall.right + 3 * scale, wall.top), (wall.centerx, wall.top - 10 * scale)]
        pygame.draw.polygon(surface, (112, 48, 38), roof)
    elif name == "approach":
        r = 5 * scale
        left, right = (x - 9 * scale, y), (x + 9 * scale, y)
        pygame.draw.line(surface, (230, 179, 51), left, right, max(2, round(2 * scale)))
        pygame.draw.circle(surface, (217, 76, 76), left, r)
        pygame.draw.circle(surface, (76, 166, 230), right, r)
    elif name == "intelligence":
        r = 7 * scale
        lens_center = (x - 2 * scale, y - 2 * scale)
        pygame.draw.circle(surface, (230, 230, 230), lens_center, r, max(2, round(2 * scale)))
        handle_start = (lens_center[0] + r * 0.7, lens_center[1] + r * 0.7)
        handle_end = (x + 8 * scale, y + 8 * scale)
        pygame.draw.line(surface, (230, 230, 230), handle_start, handle_end, max(2, round(3 * scale)))
    elif name == "wheel":
        offsets = [(0, -12), (12, 0), (0, 12), (-12, 0)]
        colors = list(SKILL_COLORS.values())
        points = [(x + dx * scale, y + dy * scale) for dx, dy in offsets]
        for i in range(4):
            pygame.draw.line(surface, (90, 90, 90), points[i], points[(i + 1) % 4], 1)
        for pt, color in zip(points, colors):
            pygame.draw.circle(surface, color, pt, 6 * scale)
            pygame.draw.circle(surface, (20, 20, 20), pt, 6 * scale, 1)


def draw_person(surface, pos, color, scale=1.0, bob=0.0, outline=(20, 20, 20), facing=0):
    """A small flat 'paper doll' figure: head, torso, arms, legs, drop shadow.

    Shared by the Home village circle (small scale, many at once) and the
    Market screen (larger scale, idle bob animation) so every human figure
    in the game reads the same way instead of a plain circle.
    """
    x, y = pos[0], pos[1] + bob
    head_r = max(3, round(7 * scale))
    torso_w = max(6, round(15 * scale))
    torso_h = max(8, round(20 * scale))
    leg_h = max(5, round(13 * scale))
    limb_w = max(2, round(3 * scale))

    torso_top = y - torso_h / 2
    leg_y0 = y + torso_h / 2
    leg_y1 = leg_y0 + leg_h
    lean = 3 * scale * facing

    shadow_w, shadow_h = torso_w * 1.5, max(3, round(5 * scale))
    shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow_surf, (0, 0, 0, 80), shadow_surf.get_rect())
    surface.blit(shadow_surf, (x - shadow_w / 2 + lean, leg_y1 - shadow_h / 2))

    pygame.draw.line(surface, outline, (x - torso_w * 0.2, leg_y0), (x - torso_w * 0.28 + lean, leg_y1), limb_w)
    pygame.draw.line(surface, outline, (x + torso_w * 0.2, leg_y0), (x + torso_w * 0.28 + lean, leg_y1), limb_w)

    pygame.draw.line(surface, color, (x - torso_w / 2, torso_top + 3 * scale), (x - torso_w / 2 - 4 * scale, torso_top + torso_h * 0.8), limb_w)
    pygame.draw.line(surface, color, (x + torso_w / 2, torso_top + 3 * scale), (x + torso_w / 2 + 4 * scale, torso_top + torso_h * 0.8), limb_w)

    torso_rect = pygame.Rect(0, 0, torso_w, torso_h)
    torso_rect.midtop = (x, torso_top)
    pygame.draw.rect(surface, color, torso_rect, border_radius=max(2, round(3 * scale)))
    pygame.draw.rect(surface, outline, torso_rect, max(1, round(1.5 * scale)), border_radius=max(2, round(3 * scale)))

    head_center = (x, torso_top - head_r * 0.7)
    pygame.draw.circle(surface, SKIN_TONE, head_center, head_r)
    pygame.draw.circle(surface, outline, head_center, head_r, max(1, round(1 * scale)))


def homestead_anchor(pos, angle, scale=1.0):
    """Ground point a player's house/field/pen cluster sits on: offset mostly
    tangentially along the village circle (so houses form a street around
    the ring instead of clustering toward the center or the edges) plus a
    small outward push. A purely radial or purely-downward offset either
    stacks the house on top of a top-row player's head or under a
    bottom-row player's feet — tangential placement avoids both. Shared with
    road drawing so each curved road ends exactly at the house it leads to.
    """
    tangent = (-math.sin(angle), math.cos(angle))
    radial = (math.cos(angle), math.sin(angle))
    return (
        pos[0] + tangent[0] * 34 * scale + radial[0] * 18 * scale,
        pos[1] + tangent[1] * 34 * scale + radial[1] * 18 * scale,
    )


def draw_homestead(surface, anchor, scale=1.0, animal_variant=0):
    """A small house with a tilled field on one side and a fenced animal pen
    on the other, base-aligned at `anchor` — every villager's own home and
    land, sized to actually read next to their figure instead of a couple of
    tiny accent boxes.
    """
    ax, ay = anchor

    house_w, house_h = 22 * scale, 15 * scale
    wall = pygame.Rect(0, 0, house_w, house_h)
    wall.midbottom = (ax, ay)
    pygame.draw.rect(surface, (150, 108, 66), wall, border_radius=1)
    pygame.draw.rect(surface, (90, 60, 35), wall, max(1, round(scale)), border_radius=1)
    roof = [
        (wall.left - 4 * scale, wall.top),
        (wall.right + 4 * scale, wall.top),
        (wall.centerx, wall.top - 11 * scale),
    ]
    pygame.draw.polygon(surface, (112, 48, 38), roof)
    pygame.draw.polygon(surface, (40, 22, 16), roof, max(1, round(scale)))
    door = pygame.Rect(0, 0, round(5 * scale), round(8 * scale))
    door.midbottom = wall.midbottom
    pygame.draw.rect(surface, (70, 45, 28), door)

    field = pygame.Rect(0, 0, round(17 * scale), round(12 * scale))
    field.midbottom = (ax - house_w * 0.95, ay)
    pygame.draw.rect(surface, (101, 82, 46), field, border_radius=2)
    for i in range(3):
        fx = field.left + 2 + i * (field.width - 4) / 2
        pygame.draw.line(surface, (75, 60, 32), (fx, field.top + 2), (fx, field.bottom - 2), max(1, round(scale)))

    pen = pygame.Rect(0, 0, round(16 * scale), round(12 * scale))
    pen.midbottom = (ax + house_w * 0.95, ay)
    pygame.draw.rect(surface, (156, 182, 112), pen, border_radius=2)
    pygame.draw.rect(surface, (120, 90, 55), pen, max(1, round(scale)), border_radius=2)

    animal_color = (245, 245, 245) if animal_variant % 2 == 0 else (176, 132, 88)
    body = pygame.Rect(0, 0, round(8 * scale), round(6 * scale))
    body.center = pen.center
    pygame.draw.ellipse(surface, animal_color, body)
    pygame.draw.circle(surface, animal_color, (body.left, body.centery), max(2, round(2.5 * scale)))


def _bezier_points(p0, p1, p2, steps=14):
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        points.append((x, y))
    return points


def _road_points(start, end, bulge=22):
    """A gently curved path from `start` to `end` (quadratic bezier via a
    perpendicular-offset control point), so village roads sweep instead of
    running as dead-straight spokes."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy) or 1.0
    perp = (-dy / length, dx / length)
    mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    control = (mid[0] + perp[0] * bulge, mid[1] + perp[1] * bulge)
    return _bezier_points(start, control, end)


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if font.size(trial)[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class Button:
    def __init__(self, rect, label, on_click, font):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.font = font
        self.enabled = True

    def draw(self, surface):
        color = COLOR_BUTTON if self.enabled else COLOR_BUTTON_DISABLED
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        text_color = COLOR_TEXT if self.enabled else COLOR_TEXT_DIM
        text_surf = self.font.render(self.label, True, text_color)
        surface.blit(text_surf, text_surf.get_rect(center=self.rect.center))

    def handle_click(self, pos) -> bool:
        if self.enabled and self.rect.collidepoint(pos):
            self.on_click()
            return True
        return False


class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Lower Equilibrium")
        self.clock = pygame.time.Clock()

        self.font = pygame.font.Font(None, 22)
        self.font_small = pygame.font.Font(None, 18)
        self.font_big = pygame.font.Font(None, 32)

        self.has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GEMINI_API_KEY"))
        self.facilitator = FacilitatorClient(enabled=self.has_key)

        # Persistent cross-game progression (save_data.py) — the actual
        # "progression loop" the Engagement Loop deck's scale table calls
        # for: a reason to play a second GAME, not just a second round.
        self.save_data = save_data.load()

        self.game = None  # created in _start_game(), once a risk style is chosen
        self.tracker = None
        self.newly_unlocked_this_game: list = []

        self.round_text = "Round 0 / 0"
        self.points_text = "Points: 0"
        self.connections_text = "Connections: 0"
        self.zone_text = "-"
        self.rank_text = "-"
        self._points_before_action = 0
        self._last_approach_result = None
        self._known_players: set[int] = set()
        # Separate narration per screen — round-summary text (Home) must never
        # stomp on the market visit's own narration, and vice versa.
        self.home_narration = "Welcome. Choose an action once the round begins."

        # "style_select" | "home" | "market" | "help" | "achievements"
        self.screen_state = "style_select"
        self._help_return_state = "style_select"
        self.help_page = 0
        self.target_picker_open = False
        self.pending_action = None  # ActionType.APPROACH | ActionType.INTELLIGENCE
        self._picker_rows = []
        self.hover_tooltip = None  # (lines, mouse_pos) while hovering an action button

        self.market_target = None
        self.market_time = 0.0  # drives idle bob animation

        # Dialogue exchange shown on the Market screen (see facilitator.parse_dialogue)
        self.market_dialogue: list[tuple[str, str]] = []
        self.market_dialogue_index = 0
        self.market_dialogue_timer = 0.0
        self.market_line_duration = 2.2
        self._market_dialogue_ready = False  # False while showing the "heading to the market..." placeholder
        self._market_actor_name = ""
        self._market_target_name = ""

        self._market_ground_texture = self._build_ground_texture()

        self.game_over = False
        self.final_standings = []

        # Toast-style banners (top of screen), used for achievement unlocks
        # and the mid-game special event — informational only, never a
        # pressure/urgency mechanic.
        self.toast_text = ""
        self.toast_timer = 0.0

        self._build_buttons()
        self._build_style_buttons()

        # A real playtester with zero context had no idea what the game was,
        # what the buttons did, or how a round worked (see README for the
        # full list of confusion points this addresses) — so the how-to-play
        # guide is forced open on the very first launch, not just tucked
        # behind a button nobody would think to click first.
        if not self.save_data.tutorial_seen:
            self._open_help(return_state="style_select")
            self.save_data.tutorial_seen = True
            save_data.save(self.save_data)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _build_style_buttons(self):
        styles = [RiskStyle.CAUTIOUS, RiskStyle.BALANCED, RiskStyle.BOLD]
        self.style_buttons = []
        card_width, gap = 280, 30
        total_width = card_width * len(styles) + gap * (len(styles) - 1)
        start_x = WIDTH // 2 - total_width // 2
        for i, style in enumerate(styles):
            label, _ = RISK_STYLE_INFO[style]
            x = start_x + i * (card_width + gap)
            button = Button((x, 420, card_width, 50), label, lambda s=style: self._start_game(s), self.font)
            self.style_buttons.append((button, style))

    def _start_game(self, style: RiskStyle):
        self.game = GameManager(
            total_players=16, total_rounds=20, human_risk_style=style, delay_between_rounds=1.2,
        )
        self.game.on_round_started.append(self._on_round_started)
        self.game.on_human_state_changed.append(self._on_human_state_changed)
        self.game.on_round_summary.append(self._on_round_summary)
        self.game.on_game_ended.append(self._on_game_ended)
        self.game.on_human_action_result.append(self._on_human_action_result)
        self.game.on_special_event.append(self._on_special_event)

        self.tracker = AchievementTracker(self.game, already_unlocked=set(self.save_data.achievements))
        self.tracker.on_unlocked.append(self._on_achievement_unlocked)
        self.newly_unlocked_this_game = []

        self.round_text = f"Round 0 / {self.game.total_rounds}"
        self.points_text = "Points: 0"
        self.connections_text = "Connections: 0"
        self.zone_text = "-"
        self.rank_text = "-"
        self._last_approach_result = None
        # A villager's trade is unknown until you've actually approached or
        # scouted them — it shouldn't be free information just for existing
        # in the picker list. Sticks for the rest of the game once learned.
        self._known_players: set[int] = set()
        self.home_narration = (
            "Round 1 of 20. Pick Solo for a safe guaranteed payoff, Approach to "
            "risk points on a new connection, or Intelligence to scout someone "
            "first — hover a button (or tap ? Help) for details."
        )
        if not self.has_key:
            self.home_narration += " (No API key set — using local narration.)"
        self.game_over = False
        self.final_standings = []
        self.screen_state = "home"

    def _build_buttons(self):
        by = HEIGHT - 170
        self.solo_button = Button((WIDTH // 2 - 245, by, 150, 44), "Solo", self._on_solo_clicked, self.font)
        self.approach_button = Button(
            (WIDTH // 2 - 75, by, 150, 44), "Approach",
            lambda: self._open_target_picker(ActionType.APPROACH), self.font,
        )
        self.intel_button = Button(
            (WIDTH // 2 + 95, by, 150, 44), "Intelligence",
            lambda: self._open_target_picker(ActionType.INTELLIGENCE), self.font,
        )
        self.action_buttons = [self.solo_button, self.approach_button, self.intel_button]
        self._action_tooltips = {
            self.solo_button: ACTION_TOOLTIPS["solo"],
            self.approach_button: ACTION_TOOLTIPS["approach"],
            self.intel_button: ACTION_TOOLTIPS["intelligence"],
        }
        self._set_buttons_enabled(False)

        self.cancel_picker_button = Button((WIDTH - 250, HEIGHT - 60, 220, 36), "Cancel", self._close_target_picker, self.font_small)
        self.return_button = Button((WIDTH // 2 - 110, HEIGHT - 204, 220, 44), "Return to Village", self._return_home, self.font)
        self.play_again_button = Button((WIDTH // 2 - 110, HEIGHT - 60, 220, 44), "Play Again", self._play_again, self.font)

        # Always-available escape hatches (addresses "there is no restart
        # button" / "how do I get unstuck" feedback) — shown on Home and
        # Market, not just after game over.
        self.menu_button = Button((WIDTH - 180, 20, 80, 32), "Menu", self._play_again, self.font_small)
        self.ingame_help_button = Button((WIDTH - 90, 20, 70, 32), "? Help", lambda: self._open_help(), self.font_small)

        # Style-select entry points into the guide and the achievement list
        # (below the style cards' wrapped description text, which can run
        # up to 3 lines).
        self.style_help_button = Button((WIDTH // 2 - 190, 560, 180, 36), "How to Play", lambda: self._open_help("style_select"), self.font_small)
        self.style_achievements_button = Button((WIDTH // 2 + 10, 560, 180, 36), "Achievements", lambda: self._open_achievements("style_select"), self.font_small)

        # How-to-Play overlay navigation (panel is fixed at 900x460, centered).
        self.help_close_button = Button((904, 132, 80, 28), "Close", self._close_help, self.font_small)
        self.help_prev_button = Button((120, 554, 90, 32), "< Prev", self._help_prev, self.font_small)
        self.help_next_button = Button((890, 554, 90, 32), "Next >", self._help_next, self.font_small)

        # Achievements overlay (panel is fixed at 700x560, centered).
        self.achievements_close_button = Button((804, 92, 80, 28), "Close", self._close_achievements, self.font_small)

    def _build_ground_texture(self) -> pygame.Surface:
        """Pre-baked dirt/cobblestone speckle for the market ground, drawn once
        (not per-frame — hundreds of dots repainted every frame would be wasted
        work for a texture that never changes)."""
        height = HEIGHT - MARKET_HORIZON_Y
        surface = pygame.Surface((WIDTH, height))
        _draw_vertical_gradient(surface, (0, 0, WIDTH, height), MARKET_GROUND_TOP, MARKET_GROUND_LOW)
        rng = random.Random(7)
        for _ in range(260):
            px = rng.randint(0, WIDTH)
            py = rng.randint(0, height)
            shade = rng.randint(-18, 14)
            base = MARKET_GROUND_TOP if py < height * 0.5 else MARKET_GROUND_LOW
            color = tuple(max(0, min(255, c + shade)) for c in base)
            pygame.draw.circle(surface, color, (px, py), rng.choice((1, 1, 2)))
        return surface

    def _play_again(self):
        self.game = None
        self.tracker = None
        self.game_over = False
        self.final_standings = []
        self.screen_state = "style_select"

    def _set_buttons_enabled(self, enabled: bool):
        for b in self.action_buttons:
            b.enabled = enabled

    # ------------------------------------------------------------------
    # Help / Achievements navigation
    # ------------------------------------------------------------------

    def _open_help(self, return_state=None):
        self._help_return_state = return_state if return_state is not None else self.screen_state
        self.help_page = 0
        self.screen_state = "help"

    def _close_help(self):
        self.screen_state = self._help_return_state

    def _help_prev(self):
        self.help_page = max(0, self.help_page - 1)

    def _help_next(self):
        self.help_page = min(len(HELP_PAGES) - 1, self.help_page + 1)

    def _open_achievements(self, return_state=None):
        self._help_return_state = return_state if return_state is not None else self.screen_state
        self.screen_state = "achievements"

    def _close_achievements(self):
        self.screen_state = self._help_return_state

    @staticmethod
    def _approach_outcome_summary(result: ApproachResult) -> tuple[str, tuple[int, int, int]]:
        """Plain-language mechanical summary of an Approach, shown as a
        banner on the Market screen — a playtester with no context couldn't
        tell whether talking to someone had actually done anything."""
        if result.outcome == ApproachOutcome.ACCEPT:
            return f"Connection formed with {result.target.name}! ({result.points_delta:+d} pts)", (90, 200, 110)
        if result.outcome == ApproachOutcome.STATUS_QUO:
            return f"No connection yet — you can try again later. ({result.points_delta:+d} pts)", (210, 200, 120)
        text = f"{result.target.name} wasn't interested this time. ({result.points_delta:+d} pts)"
        if result.burnout_triggered:
            text += " Burned out — Approach unavailable for a couple rounds."
        return text, (220, 120, 120)

    # ------------------------------------------------------------------
    # GameManager callbacks
    # ------------------------------------------------------------------

    def _on_round_started(self, round_num):
        self.round_text = f"Round {round_num} / {self.game.total_rounds}"

    def _on_human_state_changed(self, human):
        self.points_text = f"Points: {human.points}"
        self.connections_text = f"Connections: {human.connection_count}"
        self.zone_text = get_zone_name(human.connection_count)

        standings = sorted(self.game.players, key=lambda p: p.points, reverse=True)
        rank = next(i for i, p in enumerate(standings, start=1) if p.is_human)
        self.rank_text = f"{rank} / {len(self.game.players)}"

        can_act = self.game.awaiting_human
        self._set_buttons_enabled(can_act)
        if can_act:
            self.approach_button.enabled = not human.is_burned_out
            if human.is_burned_out:
                self.home_narration = f"Burned out for {human.burnout_rounds_remaining} more round(s) — Approach is unavailable."

    def _on_round_summary(self, round_num, events, standings):
        self.facilitator.request_round_summary(round_num, events, standings, self._set_home_narration)

    def _on_game_ended(self, standings):
        self.game_over = True
        self.final_standings = standings
        self._set_buttons_enabled(False)

        save_data.record_game_result(self.save_data, self.game.human.points, self.tracker.unlocked)
        save_data.save(self.save_data)

    def _on_achievement_unlocked(self, achievement):
        self.newly_unlocked_this_game.append(achievement)
        self.toast_text = f"Achievement unlocked: {achievement.name}"
        self.toast_timer = 4.0

    def _on_special_event(self, round_num):
        self.toast_text = "Market Day! Everyone's more open to connecting this round."
        self.toast_timer = 5.0
        self.home_narration = "It's Market Day — approaches are cheaper and people are more receptive today."

    def _on_human_action_result(self, result):
        if isinstance(result, SoloResult):
            delta = result.actor.points - self._points_before_action
            prefix = f"Solo work: {delta:+d} pts. "
            self.facilitator.request_solo_narration(
                result, lambda text, p=prefix: self._set_home_narration(p + text)
            )
        elif isinstance(result, ApproachResult):
            self._last_approach_result = result
            self.market_target = result.target
            self.screen_state = "market"
            self.game.set_paused(True)
            self._market_actor_name = result.actor.name
            self._market_target_name = result.target.name if result.target else ""
            waiting_line = (
                f"You head to the market to find {result.target.name}..."
                if result.target else "You head to the market..."
            )
            self.market_dialogue = [("", waiting_line)]
            self.market_dialogue_index = 0
            self.market_dialogue_timer = 0.0
            self._market_dialogue_ready = False
            self.facilitator.request_approach_narration(result, self._set_market_narration)
        elif isinstance(result, IntelligenceResult):
            delta = result.querier.points - self._points_before_action
            prefix = f"Intelligence: {delta:+d} pts. Learned {result.target.name}'s {result.data_point_type}: {result.data_point_value}. "
            self.facilitator.request_intelligence_narration(
                result, lambda text, p=prefix: self._set_home_narration(p + text)
            )

    def _set_home_narration(self, text: str):
        self.home_narration = text

    def _set_market_narration(self, text: str):
        self.market_dialogue = parse_dialogue(text, self._market_actor_name, self._market_target_name)
        self.market_dialogue_index = 0
        self.market_dialogue_timer = 0.0
        self._market_dialogue_ready = True

    # ------------------------------------------------------------------
    # UI actions
    # ------------------------------------------------------------------

    def _on_solo_clicked(self):
        self._points_before_action = self.game.human.points
        self.game.submit_solo()
        self._set_buttons_enabled(False)

    def _open_target_picker(self, action):
        self.pending_action = action
        self.target_picker_open = True

    def _close_target_picker(self):
        self.target_picker_open = False
        self.pending_action = None

    def _choose_target(self, target_id: int):
        self._points_before_action = self.game.human.points
        # Approaching or scouting someone is what makes you actually know
        # their trade — it sticks for the rest of the game once learned.
        self._known_players.add(target_id)
        if self.pending_action == ActionType.APPROACH:
            self.game.submit_approach(target_id)
        else:
            self.game.submit_intelligence(target_id)
        self.target_picker_open = False
        self.pending_action = None
        self._set_buttons_enabled(False)

    def _return_home(self):
        self.screen_state = "home"
        self.game.set_paused(False)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            if self.toast_timer > 0:
                self.toast_timer -= dt

            if self.game is not None:
                self.game.update(dt)
                self.facilitator.poll()

                if self.screen_state == "market":
                    self.market_time += dt
                    if self.market_dialogue_index < len(self.market_dialogue) - 1:
                        self.market_dialogue_timer += dt
                        if self.market_dialogue_timer >= self.market_line_duration:
                            self.market_dialogue_timer = 0.0
                            self.market_dialogue_index += 1
                    # No auto-return timer here on purpose — a playtester
                    # was confused when the screen closed itself with no
                    # warning. The outcome only reveals once the dialogue
                    # has fully played out (see _draw_dialogue_box), and the
                    # screen only closes when Return to Village is clicked.

            # Hover tooltips on the action buttons (a playtester asked for
            # exactly this: "an i button, hovering which could lead to
            # explaining it") — only live on Home, with no picker/help/
            # achievements overlay covering the buttons.
            self.hover_tooltip = None
            if self.screen_state == "home" and not self.target_picker_open:
                mouse_pos = pygame.mouse.get_pos()
                for btn, lines in self._action_tooltips.items():
                    if btn.rect.collidepoint(mouse_pos):
                        self.hover_tooltip = (lines, mouse_pos)
                        break
                if self.hover_tooltip is None and self.game is not None:
                    # Hovering a villager on the map shows their profile —
                    # "explain your profile... hover above a bot, it should
                    # show a popup for his profile."
                    _, positions, _ = self._village_positions()
                    for p in self.game.players:
                        px, py = positions[p.id]
                        if (mouse_pos[0] - px) ** 2 + (mouse_pos[1] - py) ** 2 <= 16 * 16:
                            self.hover_tooltip = (self._player_profile_lines(p), mouse_pos)
                            break

            if self.screen_state == "style_select":
                self._draw_style_select()
            elif self.screen_state == "home":
                self._draw_home()
            elif self.screen_state == "market":
                self._draw_market()
            elif self.screen_state == "help":
                self._draw_help()
            elif self.screen_state == "achievements":
                self._draw_achievements()

            if self.toast_timer > 0:
                self._draw_toast()

            if self.game_over:
                self._draw_end_overlay()

            pygame.display.flip()

        pygame.quit()

    def _handle_click(self, pos):
        if self.screen_state == "help":
            self.help_prev_button.handle_click(pos)
            self.help_next_button.handle_click(pos)
            self.help_close_button.handle_click(pos)
            return

        if self.screen_state == "achievements":
            self.achievements_close_button.handle_click(pos)
            return

        if self.game_over:
            self.play_again_button.handle_click(pos)
            return

        if self.screen_state == "style_select":
            if self.style_help_button.handle_click(pos):
                return
            if self.style_achievements_button.handle_click(pos):
                return
            for button, _style in self.style_buttons:
                if button.handle_click(pos):
                    return
            return

        if self.target_picker_open:
            self.cancel_picker_button.handle_click(pos)
            for rect, player in self._picker_rows:
                if rect.collidepoint(pos):
                    self._choose_target(player.id)
                    return
            return

        if self.menu_button.handle_click(pos):
            return
        if self.ingame_help_button.handle_click(pos):
            return

        if self.screen_state == "market":
            self.return_button.handle_click(pos)
            return

        for b in self.action_buttons:
            if b.handle_click(pos):
                return

    # ------------------------------------------------------------------
    # Rendering — Style select (also shows persistent cross-game profile)
    # ------------------------------------------------------------------

    def _draw_style_select(self):
        surface = self.screen
        surface.fill((30, 34, 28))

        title = self.font_big.render("Lower Equilibrium", True, COLOR_TEXT)
        surface.blit(title, (WIDTH // 2 - title.get_width() // 2, 60))

        subtitle = self.font.render("You're an entrepreneur growing your network. How do you operate?", True, COLOR_TEXT_DIM)
        surface.blit(subtitle, (WIDTH // 2 - subtitle.get_width() // 2, 110))

        # Persistent profile — the actual progression loop: a reason to
        # play a second GAME, not just a second round.
        sd = self.save_data
        achieved = len(sd.achievements)
        profile_lines = [
            f"Games played: {sd.games_played}    Best score: {sd.best_score}",
            f"Achievements: {achieved} / {len(ACHIEVEMENTS)}",
        ]
        panel = pygame.Rect(0, 0, 420, 70)
        panel.center = (WIDTH // 2, 170)
        pygame.draw.rect(surface, COLOR_PANEL, panel, border_radius=8)
        for i, line in enumerate(profile_lines):
            text = self.font_small.render(line, True, COLOR_TEXT)
            surface.blit(text, (panel.centerx - text.get_width() // 2, panel.top + 14 + i * 24))

        for button, style in self.style_buttons:
            button.draw(surface)
            _, description = RISK_STYLE_INFO[style]
            lines = wrap_text(description, self.font_small, button.rect.width - 20)
            for i, line in enumerate(lines):
                text = self.font_small.render(line, True, COLOR_TEXT_DIM)
                surface.blit(text, (button.rect.centerx - text.get_width() // 2, button.rect.bottom + 12 + i * 20))

        # New here? Start with the guide — a playtester with none of this
        # context had no idea what the game was or what any button did.
        self.style_help_button.draw(surface)
        self.style_achievements_button.draw(surface)

    def _draw_toast(self):
        text = self.font.render(self.toast_text, True, (20, 20, 20))
        padding = 16
        box = pygame.Rect(0, 0, text.get_width() + padding * 2, text.get_height() + padding)
        box.centerx = WIDTH // 2
        box.top = 16
        pygame.draw.rect(self.screen, (240, 210, 90), box, border_radius=8)
        self.screen.blit(text, (box.centerx - text.get_width() // 2, box.centery - text.get_height() // 2))

    # ------------------------------------------------------------------
    # Rendering — How to Play / Achievements overlays
    # ------------------------------------------------------------------

    def _draw_help(self):
        surface = self.screen
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        surface.blit(overlay, (0, 0))

        panel = pygame.Rect(0, 0, 900, 460)
        panel.center = (WIDTH // 2, HEIGHT // 2)
        pygame.draw.rect(surface, COLOR_PANEL, panel, border_radius=10)

        heading, icon, lines = HELP_PAGES[self.help_page]
        title = self.font_big.render(heading, True, COLOR_TEXT)
        surface.blit(title, (panel.left + 24, panel.top + 20))

        # Icons sit below the Close button (top-right corner), not beside
        # it, so they never fight it for space at this panel width.
        if heading == "Your three moves":
            for i, name in enumerate(("solo", "approach", "intelligence")):
                icon_x = panel.right - 220 + i * 70
                draw_icon(surface, name, (icon_x, panel.top + 60), scale=1.1)
        elif icon:
            draw_icon(surface, icon, (panel.right - 60, panel.top + 60), scale=1.4)

        y = panel.top + 96
        for para in lines:
            for line in wrap_text(para, self.font, panel.width - 48):
                text = self.font.render(line, True, COLOR_TEXT)
                surface.blit(text, (panel.left + 24, y))
                y += 26
            y += 14

        page_label = self.font_small.render(f"Page {self.help_page + 1} / {len(HELP_PAGES)}", True, COLOR_TEXT_DIM)
        surface.blit(page_label, (panel.centerx - page_label.get_width() // 2, panel.bottom - 40))

        self.help_prev_button.enabled = self.help_page > 0
        self.help_next_button.enabled = self.help_page < len(HELP_PAGES) - 1
        self.help_prev_button.draw(surface)
        self.help_next_button.draw(surface)
        self.help_close_button.draw(surface)

    def _draw_achievements(self):
        surface = self.screen
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        surface.blit(overlay, (0, 0))

        panel = pygame.Rect(0, 0, 700, 560)
        panel.center = (WIDTH // 2, HEIGHT // 2)
        pygame.draw.rect(surface, COLOR_PANEL, panel, border_radius=10)

        title = self.font_big.render("Achievements", True, COLOR_TEXT)
        surface.blit(title, (panel.left + 24, panel.top + 20))

        unlocked_ids = self.tracker.unlocked if self.tracker is not None else set(self.save_data.achievements)
        y = panel.top + 72
        for ach in ACHIEVEMENTS:
            got = ach.id in unlocked_ids
            marker = "[x]" if got else "[ ]"
            color = (240, 210, 90) if got else COLOR_TEXT_DIM
            line = f"{marker} {ach.name} — {ach.description}"
            for wrapped in wrap_text(line, self.font_small, panel.width - 48):
                text = self.font_small.render(wrapped, True, color)
                surface.blit(text, (panel.left + 24, y))
                y += 22
            y += 8

        self.achievements_close_button.draw(surface)

    # ------------------------------------------------------------------
    # Rendering — Home
    # ------------------------------------------------------------------

    def _village_positions(self):
        center = (WIDTH // 2, 300)
        radius = 195
        players = self.game.players
        count = len(players)
        positions = {}
        angles = {}
        for i, p in enumerate(players):
            angle = (i / count) * 2 * math.pi - math.pi / 2
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            positions[p.id] = (x, y)
            angles[p.id] = angle
        return center, positions, angles

    def _draw_home(self):
        surface = self.screen
        surface.fill(COLOR_BG_HOME)

        center, positions, angles = self._village_positions()
        anchors = {
            p.id: homestead_anchor(positions[p.id], angles[p.id]) for p in self.game.players
        }

        # Curved dirt roads from the central marketplace out to each
        # villager's house, drawn first so everything else sits on top.
        for p in self.game.players:
            road = _road_points(center, anchors[p.id])
            pygame.draw.lines(surface, ROAD_COLOR, False, road, 5)

        # Central marketplace plaza — the village hub every road leads to,
        # replacing the old single shared hut.
        plaza_r = 52
        pygame.draw.circle(surface, (196, 182, 150), center, plaza_r)
        pygame.draw.circle(surface, (150, 136, 104), center, plaza_r, 3)
        pygame.draw.circle(surface, (120, 120, 120), center, 12)
        pygame.draw.circle(surface, (80, 80, 80), center, 12, 2)
        for i, stall_color in enumerate(((204, 76, 76), (222, 189, 61), (140, 90, 191))):
            stall_angle = -math.pi / 2 + i * (2 * math.pi / 3)
            sx = center[0] + math.cos(stall_angle) * plaza_r * 0.65
            sy = center[1] + math.sin(stall_angle) * plaza_r * 0.65
            tri = [(sx - 8, sy + 5), (sx + 8, sy + 5), (sx, sy - 8)]
            pygame.draw.polygon(surface, stall_color, tri)
            pygame.draw.polygon(surface, (30, 24, 18), tri, 1)
        market_label = self.font_small.render("Village Market", True, (60, 48, 34))
        surface.blit(market_label, (center[0] - market_label.get_width() // 2, center[1] + plaza_r + 4))

        # Every villager's own house, field, and animal pen.
        for i, p in enumerate(self.game.players):
            draw_homestead(surface, anchors[p.id], scale=1.0, animal_variant=i)

        # Connection lines
        for p in self.game.players:
            for other_id in p.connection_ids:
                if other_id < p.id:
                    continue  # draw each pair once
                a = positions[p.id]
                b = positions.get(other_id)
                if b:
                    pygame.draw.line(surface, COLOR_LINE, a, b, 2)

        # Avatars — skill-tinted clothing only once you actually know their
        # trade (Approached or scouted them); a neutral gray otherwise, so
        # the map itself doesn't give away for free what the picker hides.
        for p in self.game.players:
            pos = positions[p.id]
            if p.is_human:
                color = COLOR_HUMAN
            elif p.id in self._known_players:
                color = SKILL_COLORS.get(p.skill, (150, 150, 150))
            else:
                color = COLOR_UNKNOWN_SKILL
            draw_person(surface, pos, color, scale=0.72)
            if p.is_human:
                label = self.font_small.render("You", True, COLOR_TEXT)
                surface.blit(label, (pos[0] - label.get_width() // 2, pos[1] - 34))

        self._draw_hud()
        self._draw_narration_panel(self.home_narration)
        for b in self.action_buttons:
            b.draw(surface)

        self.menu_button.draw(surface)
        self.ingame_help_button.draw(surface)

        if self.target_picker_open:
            self._draw_target_picker()
        elif self.hover_tooltip:
            self._draw_tooltip(*self.hover_tooltip)

    def _draw_hud(self):
        panel = pygame.Rect(20, 20, 300, 180)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=6)
        lines = [
            self.round_text, self.points_text, self.connections_text,
            f"Zone: {self.zone_text}", f"Rank: {self.rank_text}",
        ]
        for i, line in enumerate(lines):
            text = self.font.render(line, True, COLOR_TEXT)
            self.screen.blit(text, (panel.left + 14, panel.top + 14 + i * 32))

        hint = self.font_small.render("(hover Solo / Approach / Intel for details)", True, COLOR_TEXT_DIM)
        self.screen.blit(hint, (panel.left, panel.bottom + 6))

    def _draw_tooltip(self, lines, pos):
        padding = 8
        line_h = 18
        width = max(self.font_small.size(line)[0] for line in lines) + padding * 2
        height = len(lines) * line_h + padding * 2
        x = min(pos[0] + 16, WIDTH - width - 8)
        y = max(pos[1] - height - 10, 8)
        box = pygame.Rect(x, y, width, height)
        pygame.draw.rect(self.screen, (15, 15, 20), box, border_radius=6)
        pygame.draw.rect(self.screen, (100, 100, 112), box, 1, border_radius=6)
        for i, line in enumerate(lines):
            text = self.font_small.render(line, True, COLOR_TEXT)
            self.screen.blit(text, (box.left + padding, box.top + padding + i * line_h))

    def _draw_narration_panel(self, text: str):
        panel = pygame.Rect(20, HEIGHT - 110, WIDTH - 40, 90)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=6)
        lines = wrap_text(text, self.font_small, panel.width - 24)
        for i, line in enumerate(lines[:4]):
            text = self.font_small.render(line, True, COLOR_TEXT)
            self.screen.blit(text, (panel.left + 12, panel.top + 10 + i * 20))

    def _network_visibility(self):
        """Which players the human has real information about, mirroring
        Granovetter's weak-ties idea that what you know about someone
        depends on your position in the network, not on omniscience:
        - direct connection: exact connection count, real burnout status
        - one hop out (a connection of a connection): a fuzzy bucket only,
          credited to whichever mutual connection is the source
        - anyone else: unknown — that's what the paid Intelligence action
          is for
        Returns {player_id: ("direct"|"indirect", extra)} where extra is
        None for direct and the mutual connection's name for indirect.
        """
        human = self.game.human
        by_id = {p.id: p for p in self.game.players}
        direct = set(human.connection_ids)
        tiers = {pid: ("direct", None) for pid in direct}
        for pid in direct:
            mutual = by_id.get(pid)
            if not mutual:
                continue
            for hop_id in mutual.connection_ids:
                if hop_id == human.id or hop_id in direct or hop_id in tiers:
                    continue
                tiers[hop_id] = ("indirect", mutual.name)
        return tiers

    @staticmethod
    def _connection_bucket(count: int) -> str:
        if count == 0:
            return "no connections yet"
        if count <= 3:
            return "a few connections"
        if count <= 7:
            return "several connections"
        return "many connections"

    def _player_profile_lines(self, p) -> list[str]:
        """Hover-tooltip content for a villager on the Home screen map —
        "doesn't explain what different bots do" feedback: skill labels
        alone (Marketing, Ops, ...) meant nothing without a one-line
        translation of what that specialty actually does."""
        if p.is_human:
            return ["You", "The entrepreneur — that's you."]
        known = p.id in self._known_players
        if known:
            trade_name, trade_desc = SKILL_INFO[p.skill]
            lines = [p.name, f"{trade_name} — {trade_desc}"]
            if p.persona_trait:
                lines.append(p.persona_trait.capitalize())
        else:
            lines = [p.name, "Trade unknown — Approach or Intelligence to find out."]
        tier, extra = self._network_visibility().get(p.id, (None, None))
        if tier == "direct":
            info = f"{p.connection_count} connections"
            if p.is_burned_out:
                info += " (burned out)"
        elif tier == "indirect":
            info = f"~{self._connection_bucket(p.connection_count)} (via {extra})"
        else:
            info = "connections unknown"
        lines.append(info)
        return lines

    def _draw_target_picker(self):
        others = self.game.get_other_players()
        visibility = self._network_visibility()
        row_h = 34
        panel_height = min(HEIGHT - 140, 40 + len(others) * row_h)
        panel = pygame.Rect(WIDTH - 300, 130, 280, panel_height)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=6)

        title = self.font_small.render("Choose a target:", True, COLOR_TEXT)
        self.screen.blit(title, (panel.left + 12, panel.top + 8))

        # Cancel lives in the title bar (not a separate bottom row) so the
        # full panel body is available for target rows — with up to 15
        # targets and two lines of info each, a bottom-anchored button ate
        # into the list and clipped the last few entries.
        self.cancel_picker_button.rect = pygame.Rect(panel.right - 76, panel.top + 5, 66, 22)

        self._picker_rows = []
        for i, p in enumerate(others):
            row_rect = pygame.Rect(panel.left + 10, panel.top + 32 + i * row_h, panel.width - 20, row_h - 4)
            if row_rect.bottom > panel.bottom - 4:
                break
            pygame.draw.rect(self.screen, (40, 60, 100), row_rect, border_radius=4)
            # Trade stays unknown until you've actually approached or
            # scouted this person — not free information just for being
            # listed here.
            if p.id in self._known_players:
                skill_label = SKILL_INFO[p.skill][0]
            else:
                skill_label = "unknown trade"
            label = self.font_small.render(f"{p.name} ({skill_label})", True, COLOR_TEXT)
            self.screen.blit(label, (row_rect.left + 8, row_rect.top + 2))

            tier, extra = visibility.get(p.id, (None, None))
            if tier == "direct":
                info = f"{p.connection_count} connections"
                if p.is_burned_out:
                    info += " • burned out"
                info_color = (150, 220, 150)
            elif tier == "indirect":
                info = f"~{self._connection_bucket(p.connection_count)} (via {extra})"
                info_color = COLOR_TEXT_DIM
            else:
                info = "connections unknown"
                info_color = COLOR_TEXT_DIM
            info_surf = self.font_small.render(info, True, info_color)
            self.screen.blit(info_surf, (row_rect.left + 8, row_rect.top + 18))

            self._picker_rows.append((row_rect, p))

        self.cancel_picker_button.draw(self.screen)

    # ------------------------------------------------------------------
    # Rendering — Market
    # ------------------------------------------------------------------

    def _draw_market(self):
        surface = self.screen
        _draw_vertical_gradient(surface, (0, 0, WIDTH, MARKET_HORIZON_Y), SKY_TOP, SKY_HORIZON)
        surface.blit(self._market_ground_texture, (0, MARKET_HORIZON_Y))

        self._draw_tree(surface, (55, MARKET_HORIZON_Y + 10), 1.0)
        self._draw_tree(surface, (135, MARKET_HORIZON_Y + 35), 0.75)
        self._draw_tree(surface, (WIDTH - 60, MARKET_HORIZON_Y + 5), 1.1)
        self._draw_tree(surface, (WIDTH - 150, MARKET_HORIZON_Y + 40), 0.8)

        stalls = [
            (WIDTH // 2 - 260, 300, (204, 76, 76), "Produce"),
            (WIDTH // 2, 270, (222, 189, 61), "Goods"),
            (WIDTH // 2 + 260, 300, (140, 90, 191), "Crafts"),
        ]
        for x, y, awning_color, sign in stalls:
            self._draw_stall(surface, (x, y), awning_color, sign)

        bob = math.sin(self.market_time * 2.4) * 3
        human_pos = (WIDTH // 2 - 55, 470)
        draw_person(surface, human_pos, COLOR_HUMAN, scale=1.5, bob=bob, facing=1)
        label = self.font.render("You", True, COLOR_TEXT)
        surface.blit(label, (human_pos[0] - label.get_width() // 2, human_pos[1] - 66 + bob))

        if self.market_target is not None:
            bob2 = math.sin(self.market_time * 2.4 + math.pi * 0.6) * 3
            target_pos = (WIDTH // 2 + 55, 470)
            color = SKILL_COLORS.get(self.market_target.skill, (150, 150, 150))
            draw_person(surface, target_pos, color, scale=1.5, bob=bob2, facing=-1)
            label = self.font.render(self.market_target.name, True, COLOR_TEXT)
            surface.blit(label, (target_pos[0] - label.get_width() // 2, target_pos[1] - 66 + bob2))

        self._draw_dialogue_box(surface)
        self.return_button.draw(surface)
        self.menu_button.draw(surface)

    def _draw_tree(self, surface, pos, scale):
        x, y = pos
        trunk = pygame.Rect(0, 0, 10 * scale, 34 * scale)
        trunk.midbottom = (x, y)
        pygame.draw.rect(surface, (96, 66, 40), trunk, border_radius=2)
        for dx, dy, r in ((0, -34, 24), (-16, -22, 18), (16, -22, 18)):
            pygame.draw.circle(surface, (58, 110, 56), (x + dx * scale, y + dy * scale), r * scale)

    def _draw_stall(self, surface, pos, awning_color, sign_text):
        x, y = pos

        shadow_surf = pygame.Surface((160, 16), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, 70), shadow_surf.get_rect())
        surface.blit(shadow_surf, (x - 80, y + 66))

        counter = pygame.Rect(0, 0, 150, 30)
        counter.center = (x, y + 58)
        pygame.draw.rect(surface, (120, 88, 58), counter, border_radius=3)
        pygame.draw.rect(surface, (90, 64, 40), counter, 2, border_radius=3)

        for pole_x in (-68, 68):
            pygame.draw.line(surface, (90, 65, 40), (x + pole_x, y + 6), (x + pole_x, y + 58), 5)

        # Scalloped awning: a solid peaked band plus alternating triangle teeth.
        awning_w, awning_h, teeth = 168, 20, 7
        peak = [(x - awning_w / 2, y - 4), (x + awning_w / 2, y - 4), (x, y - 26)]
        pygame.draw.polygon(surface, awning_color, peak)
        pygame.draw.polygon(surface, (30, 24, 18), peak, 2)
        band = pygame.Rect(0, 0, awning_w, awning_h)
        band.midtop = (x, y - 4)
        pygame.draw.rect(surface, awning_color, band)
        tooth_w = awning_w / teeth
        tooth_color = (255, 255, 255) if awning_color != (255, 255, 255) else (230, 230, 230)
        for i in range(teeth):
            if i % 2:
                continue
            tx = band.left + i * tooth_w
            pygame.draw.polygon(
                surface, tooth_color,
                [(tx, band.bottom - 2), (tx + tooth_w, band.bottom - 2), (tx + tooth_w / 2, band.bottom + 8)],
            )

        sign = pygame.Rect(0, 0, 78, 20)
        sign.center = (x, y - 40)
        pygame.draw.rect(surface, (245, 235, 215), sign, border_radius=3)
        pygame.draw.rect(surface, (60, 45, 30), sign, 1, border_radius=3)
        sign_label = self.font_small.render(sign_text, True, (40, 30, 20))
        surface.blit(sign_label, (sign.centerx - sign_label.get_width() // 2, sign.centery - sign_label.get_height() // 2))

        fruit_colors = [(217, 51, 51), (222, 189, 26), (77, 166, 89), (204, 122, 51)]
        for i in range(5):
            fx = x - 56 + i * 28
            pygame.draw.circle(surface, fruit_colors[i % len(fruit_colors)], (fx, y + 48), 7)
            pygame.draw.circle(surface, (20, 20, 20), (fx, y + 48), 7, 1)

        crate = pygame.Rect(0, 0, 24, 24)
        crate.center = (x + 92, y + 62)
        pygame.draw.rect(surface, (128, 90, 51), crate)
        pygame.draw.rect(surface, (90, 62, 34), crate, 2)

        sack = pygame.Rect(0, 0, 22, 26)
        sack.center = (x - 92, y + 60)
        pygame.draw.ellipse(surface, (172, 148, 104), sack)
        pygame.draw.ellipse(surface, (120, 100, 68), sack, 2)

    # ------------------------------------------------------------------
    # Rendering — dialogue box (Market)
    # ------------------------------------------------------------------

    def _draw_dialogue_box(self, surface):
        panel = pygame.Rect(20, HEIGHT - 150, WIDTH - 40, 130)
        pygame.draw.rect(surface, COLOR_PANEL, panel, border_radius=8)

        # The result used to be shown before the conversation even played —
        # "result comes before conversation." It now only appears once the
        # exchange has fully revealed, like actually hearing how it went.
        complete = self._market_dialogue_ready and self.market_dialogue_index >= len(self.market_dialogue) - 1
        footer_h = 34 if complete else 0

        y = panel.top + 10
        visible = self.market_dialogue[: self.market_dialogue_index + 1]
        line_h = 22
        max_rows = max(1, (panel.bottom - footer_h - 10 - y) // line_h)
        shown = visible[-max_rows:]

        for i, (speaker, line) in enumerate(shown):
            is_latest = i == len(shown) - 1
            text_color = COLOR_TEXT if is_latest else COLOR_TEXT_DIM
            text_x = panel.left + 14
            if speaker:
                speaker_color = COLOR_HUMAN if speaker == self._market_actor_name else (230, 179, 51)
                name_surf = self.font_small.render(f"{speaker}:", True, speaker_color if is_latest else COLOR_TEXT_DIM)
                surface.blit(name_surf, (text_x, y))
                text_x += name_surf.get_width() + 8
            wrapped = wrap_text(line, self.font_small, panel.right - text_x - 14) or [line]
            text_surf = self.font_small.render(wrapped[0], True, text_color)
            surface.blit(text_surf, (text_x, y))
            y += line_h

        if complete:
            div_y = panel.bottom - footer_h
            pygame.draw.line(surface, (55, 55, 65), (panel.left + 14, div_y), (panel.right - 14, div_y), 1)
            text, color = self._approach_outcome_summary(self._last_approach_result)
            summary_surf = self.font_small.render(text, True, color)
            surface.blit(summary_surf, (panel.left + 14, div_y + 8))
            # No auto-close timer — "ends automatically... end the page
            # after click only" — so spell out that it's waiting on you.
            hint_surf = self.font_small.render("Click Return to Village to continue", True, COLOR_TEXT_DIM)
            surface.blit(hint_surf, (panel.right - hint_surf.get_width() - 14, div_y + 8))
        elif self.market_dialogue_index < len(self.market_dialogue) - 1:
            dots = self.font_small.render("...", True, COLOR_TEXT_DIM)
            surface.blit(dots, (panel.right - dots.get_width() - 12, panel.bottom - 22))

    # ------------------------------------------------------------------
    # Rendering — end of game
    # ------------------------------------------------------------------

    def _draw_end_overlay(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.screen.blit(overlay, (0, 0))

        panel = pygame.Rect(0, 0, 640, 660)
        panel.center = (WIDTH // 2, HEIGHT // 2)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=8)

        title = self.font_big.render("Game Over", True, COLOR_TEXT)
        self.screen.blit(title, (panel.left + 20, panel.top + 16))

        y = panel.top + 56
        if self.final_standings:
            winner = self.final_standings[0]
            winner_text = self.font.render(f"Winner: {winner.name} with {winner.points} pts", True, (255, 215, 0))
            self.screen.blit(winner_text, (panel.left + 20, y))
        y += 34

        for i, p in enumerate(self.final_standings):
            line = f"{i + 1}. {p.name}: {p.points} pts ({p.connection_count} connections)"
            text = self.font_small.render(line, True, COLOR_TEXT)
            self.screen.blit(text, (panel.left + 20, y))
            y += 19

        y += 10
        if self.newly_unlocked_this_game:
            names = ", ".join(a.name for a in self.newly_unlocked_this_game)
            header = self.font_small.render("Achievements unlocked this game:", True, (240, 210, 90))
            self.screen.blit(header, (panel.left + 20, y))
            y += 20
            for line in wrap_text(names, self.font_small, panel.width - 40):
                text = self.font_small.render(line, True, COLOR_TEXT)
                self.screen.blit(text, (panel.left + 20, y))
                y += 20
        else:
            text = self.font_small.render("No new achievements this game.", True, COLOR_TEXT_DIM)
            self.screen.blit(text, (panel.left + 20, y))
            y += 20

        y += 8
        sd = self.save_data
        profile = self.font_small.render(
            f"Career: {sd.games_played} games played, best score {sd.best_score}, "
            f"{len(sd.achievements)}/{len(ACHIEVEMENTS)} achievements",
            True, COLOR_TEXT_DIM,
        )
        self.screen.blit(profile, (panel.left + 20, y))

        self.play_again_button.rect.centerx = panel.centerx
        self.play_again_button.rect.bottom = panel.bottom - 20
        self.play_again_button.draw(self.screen)


def main():
    App().run()


if __name__ == "__main__":
    main()
