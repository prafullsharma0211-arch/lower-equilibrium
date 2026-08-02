"""Lower Equilibrium — Pygame edition.

A single window with two screens: Home (village circle around the hut, farm
patch, animal pen, tool shed, and the action buttons) and Market (loaded in
whenever you choose Approach). Bots resolve instantly and silently; only your
actions get narrated by the AI facilitator.
"""

from __future__ import annotations

import math
import os

import pygame

from facilitator import FacilitatorClient
from game_logic import (
    ActionType,
    ApproachResult,
    GameManager,
    IntelligenceResult,
    JobType,
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

        has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GEMINI_API_KEY"))
        self.facilitator = FacilitatorClient(enabled=has_key)

        self.game = GameManager(total_players=16, total_rounds=20, delay_between_rounds=1.2)
        self.game.on_round_started.append(self._on_round_started)
        self.game.on_human_state_changed.append(self._on_human_state_changed)
        self.game.on_round_summary.append(self._on_round_summary)
        self.game.on_game_ended.append(self._on_game_ended)
        self.game.on_human_action_result.append(self._on_human_action_result)

        self.round_text = f"Round 0 / {self.game.total_rounds}"
        self.points_text = "Points: 0"
        self.connections_text = "Connections: 0"
        self.zone_text = "Zone: -"
        # Separate narration per screen — round-summary text (Home) must never
        # stomp on the market visit's own narration, and vice versa.
        welcome_text = (
            "Welcome. Choose an action once the round begins."
            if has_key
            else "Welcome. (No API key set — using local narration.) Choose an action once the round begins."
        )
        self.home_narration = welcome_text
        self.market_narration = ""

        self.screen_state = "home"  # "home" | "market"
        self.target_picker_open = False
        self.pending_action = None  # ActionType.APPROACH | ActionType.INTELLIGENCE
        self._picker_rows = []

        self.market_target = None
        self.market_timer = 0.0
        self.market_auto_return = 6.0

        self.game_over = False
        self.final_standings = []

        self._build_buttons()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

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

    def _on_human_action_result(self, result):
        if isinstance(result, SoloResult):
            self.facilitator.request_solo_narration(result, self._set_home_narration)
        elif isinstance(result, ApproachResult):
            self.market_target = result.target
            self.market_timer = 0.0
            self.screen_state = "market"
            self.game.set_paused(True)
            self.market_narration = (
                f"You head to the market to find {result.target.name}..."
                if result.target else "You head to the market..."
            )
            self.facilitator.request_approach_narration(result, self._set_market_narration)
        elif isinstance(result, IntelligenceResult):
            self.facilitator.request_intelligence_narration(result, self._set_home_narration)

    def _set_home_narration(self, text: str):
        self.home_narration = text

    def _set_market_narration(self, text: str):
        self.market_narration = text

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

            self.game.update(dt)
            self.facilitator.poll()

            if self.screen_state == "market":
                self.market_timer += dt
                if self.market_timer >= self.market_auto_return:
                    self._return_home()

            if self.screen_state == "home":
                self._draw_home()
            else:
                self._draw_market()

            if self.game_over:
                self._draw_end_overlay()

            pygame.display.flip()

        pygame.quit()

    def _handle_click(self, pos):
        if self.game_over:
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
    # Rendering — Home
    # ------------------------------------------------------------------

    def _village_positions(self):
        center = (WIDTH // 2, 350)
        radius = 210
        players = self.game.players
        count = len(players)
        positions = {}
        for i, p in enumerate(players):
            angle = (i / count) * 2 * math.pi - math.pi / 2
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            positions[p.id] = (x, y)
        return center, positions

    def _draw_home(self):
        surface = self.screen
        surface.fill(COLOR_BG_HOME)

        center, positions = self._village_positions()

        # Hut
        hut_rect = pygame.Rect(0, 0, 70, 55)
        hut_rect.center = center
        pygame.draw.rect(surface, (140, 97, 56), hut_rect)
        roof_points = [
            (hut_rect.left - 8, hut_rect.top),
            (hut_rect.right + 8, hut_rect.top),
            (hut_rect.centerx, hut_rect.top - 32),
        ]
        pygame.draw.polygon(surface, (107, 46, 36), roof_points)

        # Farm patch / animal pen / tool shed
        self._draw_dressing(surface, (center[0] - 150, center[1] + 40), (60, 40, 25), "Farm")
        self._draw_dressing(surface, (center[0] + 150, center[1] + 40), (120, 100, 70), "Pen")
        self._draw_dressing(surface, (center[0], center[1] + 110), (95, 75, 55), "Shed")

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
            pygame.draw.circle(surface, color, pos, 14)
            pygame.draw.circle(surface, (20, 20, 20), pos, 14, 2)
            if p.is_human:
                label = self.font_small.render("You", True, COLOR_TEXT)
                surface.blit(label, (pos[0] - label.get_width() // 2, pos[1] - 32))

        self._draw_hud()
        self._draw_narration_panel(self.home_narration)
        for b in self.action_buttons:
            b.draw(surface)

        if self.target_picker_open:
            self._draw_target_picker()

    def _draw_dressing(self, surface, center, color, label):
        rect = pygame.Rect(0, 0, 46, 32)
        rect.center = center
        pygame.draw.rect(surface, color, rect, border_radius=4)
        text = self.font_small.render(label, True, COLOR_TEXT)
        surface.blit(text, (center[0] - text.get_width() // 2, rect.bottom + 3))

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
        surface.fill(COLOR_BG_MARKET)

        stall_positions = [(WIDTH // 2 - 260, 260, (204, 51, 51)), (WIDTH // 2, 230, (217, 191, 38)), (WIDTH // 2 + 260, 260, (140, 64, 191))]
        for x, y, awning_color in stall_positions:
            self._draw_stall(surface, (x, y), awning_color)

        human_pos = (WIDTH // 2 - 40, 420)
        pygame.draw.circle(surface, COLOR_HUMAN, human_pos, 16)
        pygame.draw.circle(surface, (20, 20, 20), human_pos, 16, 2)
        label = self.font_small.render("You", True, COLOR_TEXT)
        surface.blit(label, (human_pos[0] - label.get_width() // 2, human_pos[1] - 36))

        if self.market_target is not None:
            target_pos = (WIDTH // 2 + 40, 420)
            color = SKILL_COLORS.get(self.market_target.skill, (150, 150, 150))
            pygame.draw.circle(surface, color, target_pos, 16)
            pygame.draw.circle(surface, (20, 20, 20), target_pos, 16, 2)
            label = self.font_small.render(self.market_target.name, True, COLOR_TEXT)
            surface.blit(label, (target_pos[0] - label.get_width() // 2, target_pos[1] - 36))

        self._draw_narration_panel(self.market_narration)
        self.return_button.draw(surface)

    def _draw_stall(self, surface, pos, awning_color):
        x, y = pos
        counter = pygame.Rect(0, 0, 140, 26)
        counter.center = (x, y + 40)
        pygame.draw.rect(surface, (110, 82, 55), counter)

        awning = pygame.Rect(0, 0, 160, 18)
        awning.center = (x, y)
        pygame.draw.rect(surface, awning_color, awning)

        for i, pole_x in enumerate((-65, 65)):
            pygame.draw.line(surface, (90, 65, 40), (x + pole_x, y + 9), (x + pole_x, y + 53), 4)

        fruit_colors = [(217, 51, 51), (222, 189, 26), (77, 166, 89)]
        for i in range(5):
            fx = x - 56 + i * 28
            pygame.draw.circle(surface, fruit_colors[i % len(fruit_colors)], (fx, y + 34), 7)

        crate = pygame.Rect(0, 0, 24, 24)
        crate.center = (x + 90, y + 48)
        pygame.draw.rect(surface, (128, 90, 51), crate)

    # ------------------------------------------------------------------
    # Rendering — end of game
    # ------------------------------------------------------------------

    def _draw_end_overlay(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.screen.blit(overlay, (0, 0))

        panel = pygame.Rect(0, 0, 560, 460)
        panel.center = (WIDTH // 2, HEIGHT // 2)
        pygame.draw.rect(self.screen, COLOR_PANEL, panel, border_radius=8)

        title = self.font_big.render("Game Over", True, COLOR_TEXT)
        self.screen.blit(title, (panel.left + 20, panel.top + 16))

        if self.final_standings:
            winner = self.final_standings[0]
            winner_text = self.font.render(f"Winner: {winner.name} with {winner.points} pts", True, (255, 215, 0))
            self.screen.blit(winner_text, (panel.left + 20, panel.top + 56))

        for i, p in enumerate(self.final_standings):
            line = f"{i + 1}. {p.name}: {p.points} pts ({p.connection_count} connections)"
            text = self.font_small.render(line, True, COLOR_TEXT)
            self.screen.blit(text, (panel.left + 20, panel.top + 96 + i * 22))


def main():
    App().run()


if __name__ == "__main__":
    main()
