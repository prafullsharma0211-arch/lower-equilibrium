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

SKILL_COLORS = {
    SkillType.MARKETING: (217, 76, 76),
    SkillType.CREATIVITY: (76, 166, 230),
    SkillType.FINANCE_ANALYTICS: (89, 191, 102),
    SkillType.OPERATIONS: (230, 179, 51),
}

JOB_ANIM = {
    JobType.FARMING: "farming",
    JobType.ANIMAL_HUSBANDRY: "tending animals",
    JobType.MAINTENANCE: "doing upkeep",
}

RISK_STYLE_INFO = {
    RiskStyle.CAUTIOUS: ("Cautious", "Cheaper approaches, smaller payoffs, higher accept chance. Safer, steadier."),
    RiskStyle.BALANCED: ("Balanced", "The proposal's numbers, unmodified. A bit of everything."),
    RiskStyle.BOLD: ("Bold", "Same cost, bigger payoffs, lower accept chance. Bigger swings both ways."),
}

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


def draw_homestead(surface, pos, angle, scale=1.0, animal_variant=0):
    """A tiny tilled field + fenced pen with one animal, offset from a
    player's position toward their feet — so every villager reads as
    standing on their own little plot of land instead of empty grass, not
    just the human at a single shared farm/pen/shed. The horizontal offset
    follows the village-circle angle (spreads plots sideways for players on
    the left/right of the ring); the vertical offset is always downward, so
    the plot never floats above a player's head for the top row.
    """
    cx = pos[0] + math.cos(angle) * 24 * scale
    cy = pos[1] + (22 + max(0.0, math.sin(angle)) * 10) * scale

    field = pygame.Rect(0, 0, round(22 * scale), round(15 * scale))
    field.center = (cx - 10 * scale, cy)
    pygame.draw.rect(surface, (101, 82, 46), field, border_radius=2)
    for i in range(3):
        fx = field.left + 3 + i * (field.width - 6) / 2
        pygame.draw.line(surface, (75, 60, 32), (fx, field.top + 2), (fx, field.bottom - 2), 1)

    pen = pygame.Rect(0, 0, round(20 * scale), round(15 * scale))
    pen.center = (cx + 12 * scale, cy)
    pygame.draw.rect(surface, (156, 182, 112), pen, border_radius=2)
    pygame.draw.rect(surface, (120, 90, 55), pen, max(1, round(scale)), border_radius=2)

    animal_color = (245, 245, 245) if animal_variant % 2 == 0 else (176, 132, 88)
    body = pygame.Rect(0, 0, round(9 * scale), round(6 * scale))
    body.center = (pen.centerx, pen.centery + scale)
    pygame.draw.ellipse(surface, animal_color, body)
    pygame.draw.circle(surface, animal_color, (body.left, body.centery - scale), max(2, round(2.5 * scale)))


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
        # Separate narration per screen — round-summary text (Home) must never
        # stomp on the market visit's own narration, and vice versa.
        self.home_narration = "Welcome. Choose an action once the round begins."

        self.screen_state = "style_select"  # "style_select" | "home" | "market"
        self.target_picker_open = False
        self.pending_action = None  # ActionType.APPROACH | ActionType.INTELLIGENCE
        self._picker_rows = []

        self.market_target = None
        self.market_timer = 0.0
        self.market_auto_return = 6.0
        self.market_time = 0.0  # drives idle bob animation, independent of the return timer

        # Dialogue exchange shown on the Market screen (see facilitator.parse_dialogue)
        self.market_dialogue: list[tuple[str, str]] = []
        self.market_dialogue_index = 0
        self.market_dialogue_timer = 0.0
        self.market_line_duration = 2.2
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
        self.home_narration = (
            "Welcome. Choose an action once the round begins."
            if self.has_key
            else "Welcome. (No API key set — using local narration.) Choose an action once the round begins."
        )
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
        self._set_buttons_enabled(False)

        self.cancel_picker_button = Button((WIDTH - 250, HEIGHT - 60, 220, 36), "Cancel", self._close_target_picker, self.font_small)
        self.return_button = Button((WIDTH // 2 - 110, HEIGHT - 170, 220, 44), "Return to Village", self._return_home, self.font)
        self.play_again_button = Button((WIDTH // 2 - 110, HEIGHT - 60, 220, 44), "Play Again", self._play_again, self.font)

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
    # GameManager callbacks
    # ------------------------------------------------------------------

    def _on_round_started(self, round_num):
        self.round_text = f"Round {round_num} / {self.game.total_rounds}"

    def _on_human_state_changed(self, human):
        self.points_text = f"Points: {human.points}"
        self.connections_text = f"Connections: {human.connection_count}"
        self.zone_text = get_zone_name(human.connection_count)

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
            self.facilitator.request_solo_narration(result, self._set_home_narration)
        elif isinstance(result, ApproachResult):
            self.market_target = result.target
            self.market_timer = 0.0
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
            self.facilitator.request_approach_narration(result, self._set_market_narration)
        elif isinstance(result, IntelligenceResult):
            self.facilitator.request_intelligence_narration(result, self._set_home_narration)

    def _set_home_narration(self, text: str):
        self.home_narration = text

    def _set_market_narration(self, text: str):
        self.market_dialogue = parse_dialogue(text, self._market_actor_name, self._market_target_name)
        self.market_dialogue_index = 0
        self.market_dialogue_timer = 0.0
        self.market_auto_return = max(6.0, 1.5 + len(self.market_dialogue) * self.market_line_duration)

    # ------------------------------------------------------------------
    # UI actions
    # ------------------------------------------------------------------

    def _on_solo_clicked(self):
        self.game.submit_solo()
        self._set_buttons_enabled(False)

    def _open_target_picker(self, action):
        self.pending_action = action
        self.target_picker_open = True

    def _close_target_picker(self):
        self.target_picker_open = False
        self.pending_action = None

    def _choose_target(self, target_id: int):
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
                    self.market_timer += dt
                    self.market_time += dt
                    if self.market_dialogue_index < len(self.market_dialogue) - 1:
                        self.market_dialogue_timer += dt
                        if self.market_dialogue_timer >= self.market_line_duration:
                            self.market_dialogue_timer = 0.0
                            self.market_dialogue_index += 1
                    if self.market_timer >= self.market_auto_return:
                        self._return_home()

            if self.screen_state == "style_select":
                self._draw_style_select()
            elif self.screen_state == "home":
                self._draw_home()
            else:
                self._draw_market()

            if self.toast_timer > 0:
                self._draw_toast()

            if self.game_over:
                self._draw_end_overlay()

            pygame.display.flip()

        pygame.quit()

    def _handle_click(self, pos):
        if self.game_over:
            self.play_again_button.handle_click(pos)
            return

        if self.screen_state == "style_select":
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

        subtitle = self.font.render("Choose how you'll play:", True, COLOR_TEXT_DIM)
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

    def _draw_toast(self):
        text = self.font.render(self.toast_text, True, (20, 20, 20))
        padding = 16
        box = pygame.Rect(0, 0, text.get_width() + padding * 2, text.get_height() + padding)
        box.centerx = WIDTH // 2
        box.top = 16
        pygame.draw.rect(self.screen, (240, 210, 90), box, border_radius=8)
        self.screen.blit(text, (box.centerx - text.get_width() // 2, box.centery - text.get_height() // 2))

    # ------------------------------------------------------------------
    # Rendering — Home
    # ------------------------------------------------------------------

    def _village_positions(self):
        center = (WIDTH // 2, 335)
        radius = 185
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

        # Every villager's own little plot — a tilled field + fenced pen with
        # one animal, offset outward (away from the shared village center) so
        # everyone reads as standing on their own land, not empty grass.
        # Drawn first so figures and connection lines sit on top of them.
        for i, p in enumerate(self.game.players):
            draw_homestead(surface, positions[p.id], angles[p.id], scale=0.62, animal_variant=i)

        # Hut — the shared village meeting point at the center of the ring.
        hut_rect = pygame.Rect(0, 0, 70, 55)
        hut_rect.center = center
        pygame.draw.rect(surface, (140, 97, 56), hut_rect)
        roof_points = [
            (hut_rect.left - 8, hut_rect.top),
            (hut_rect.right + 8, hut_rect.top),
            (hut_rect.centerx, hut_rect.top - 32),
        ]
        pygame.draw.polygon(surface, (107, 46, 36), roof_points)

        # Connection lines
        for p in self.game.players:
            for other_id in p.connection_ids:
                if other_id < p.id:
                    continue  # draw each pair once
                a = positions[p.id]
                b = positions.get(other_id)
                if b:
                    pygame.draw.line(surface, COLOR_LINE, a, b, 2)

        # Avatars
        for p in self.game.players:
            pos = positions[p.id]
            color = COLOR_HUMAN if p.is_human else SKILL_COLORS.get(p.skill, (150, 150, 150))
            draw_person(surface, pos, color, scale=0.85)
            if p.is_human:
                label = self.font_small.render("You", True, COLOR_TEXT)
                surface.blit(label, (pos[0] - label.get_width() // 2, pos[1] - 40))

        self._draw_hud()
        self._draw_narration_panel(self.home_narration)
        for b in self.action_buttons:
            b.draw(surface)

        if self.target_picker_open:
            self._draw_target_picker()

    def _draw_hud(self):
        panel = pygame.Rect(20, 20, 300, 150)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=6)
        lines = [self.round_text, self.points_text, self.connections_text, f"Zone: {self.zone_text}"]
        for i, line in enumerate(lines):
            text = self.font.render(line, True, COLOR_TEXT)
            self.screen.blit(text, (panel.left + 14, panel.top + 14 + i * 32))

    def _draw_narration_panel(self, text: str):
        panel = pygame.Rect(20, HEIGHT - 110, WIDTH - 40, 90)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=6)
        lines = wrap_text(text, self.font_small, panel.width - 24)
        for i, line in enumerate(lines[:4]):
            text = self.font_small.render(line, True, COLOR_TEXT)
            self.screen.blit(text, (panel.left + 12, panel.top + 10 + i * 20))

    def _draw_target_picker(self):
        others = self.game.get_other_players()
        panel_height = min(HEIGHT - 140, 40 + len(others) * 28)
        panel = pygame.Rect(WIDTH - 270, 130, 250, panel_height)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=6)

        title = self.font_small.render("Choose a target:", True, COLOR_TEXT)
        self.screen.blit(title, (panel.left + 12, panel.top + 8))

        self._picker_rows = []
        for i, p in enumerate(others):
            row_rect = pygame.Rect(panel.left + 10, panel.top + 32 + i * 28, panel.width - 20, 24)
            if row_rect.bottom > panel.bottom - 4:
                break
            pygame.draw.rect(self.screen, (40, 60, 100), row_rect, border_radius=4)
            skill_label = p.skill.name.replace("_", " ").title()
            label = self.font_small.render(f"{p.name} ({skill_label})", True, COLOR_TEXT)
            self.screen.blit(label, (row_rect.left + 8, row_rect.top + 3))
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

        visible = self.market_dialogue[: self.market_dialogue_index + 1]
        line_h = 24
        max_rows = (panel.height - 20) // line_h
        shown = visible[-max_rows:]

        y = panel.top + 12
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

        if self.market_dialogue_index < len(self.market_dialogue) - 1:
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
