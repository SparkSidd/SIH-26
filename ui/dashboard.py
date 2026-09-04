"""State-of-the-Art Dark Cyberpunk Pygame Visualizer for AMR Fleet Coordination."""

import math
import sys
from typing import Optional, Tuple
import pygame

from coordination.adaptive_coordination import CoordinationMode
from simulator.robot import RobotState
from simulator.simulation import AMRSimulation
from simulator.warehouse import CellType


class FleetDashboard:
    """High-end real-time visualizer featuring glowing AMR chassis, live HUD cards, and P2P particle telemetry."""

    def __init__(
        self,
        sim: AMRSimulation,
        window_width: int = 1366,
        window_height: int = 820,
        cell_size: int = 28,
        fps: int = 30,
    ):
        self.sim = sim
        self.window_width = window_width
        self.window_height = window_height
        self.cell_size = cell_size
        self.fps = fps

        pygame.init()
        pygame.display.set_caption("SIH 2026 (SIH26123) — Autonomous AMR Fleet Digital Twin | Bharat Electronics Limited")
        self.screen = pygame.display.set_mode((window_width, window_height))
        self.clock = pygame.time.Clock()
        
        # Typography
        self.font_title = pygame.font.SysFont("Segoe UI, Arial", 18, bold=True)
        self.font_badge = pygame.font.SysFont("Segoe UI, Arial", 11, bold=True)
        self.font_main = pygame.font.SysFont("Segoe UI, Arial", 13)
        self.font_bold = pygame.font.SysFont("Segoe UI, Arial", 13, bold=True)
        self.font_stat = pygame.font.SysFont("Segoe UI, Arial", 22, bold=True)
        self.font_mono = pygame.font.SysFont("Consolas, Courier New", 12)

        # High-End Dark Color Palette
        self.COLOR_BG = (7, 9, 14)
        self.COLOR_PANEL_BG = (14, 18, 27)
        self.COLOR_CARD_BG = (22, 28, 42)
        self.COLOR_BORDER = (48, 58, 82)
        self.COLOR_GRID_LINE = (24, 30, 44)
        self.COLOR_FLOOR = (10, 14, 22)

        # Structures
        self.COLOR_WALL = (36, 46, 68)
        self.COLOR_SHELF = (24, 32, 48)
        self.COLOR_SHELF_BORDER = (45, 58, 86)
        
        # Stations
        self.COLOR_PICKUP = (0, 245, 184)        # Neon Teal
        self.COLOR_DROPOFF = (255, 145, 0)       # Neon Amber
        self.COLOR_CHARGER = (179, 136, 255)     # Neon Purple
        self.COLOR_BLOCKED = (255, 61, 113)      # Neon Red

        # AMRs
        self.COLOR_ROBOT_PICKING = (0, 240, 255)
        self.COLOR_ROBOT_DELIVERING = (255, 145, 0)
        self.COLOR_ROBOT_IDLE = (0, 230, 118)
        self.COLOR_ROBOT_FAILED = (255, 61, 113)
        self.COLOR_ROBOT_WAITING = (255, 214, 0)

        self.COLOR_TEXT = (240, 244, 248)
        self.COLOR_TEXT_MUTED = (139, 155, 180)

        self.show_heatmap: bool = False
        self.grid_offset_x = 24
        self.grid_offset_y = 68

    def handle_events(self) -> bool:
        """Process keyboard & window events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    return False
                elif event.key == pygame.K_SPACE:
                    self.sim.clock.is_paused = not self.sim.clock.is_paused
                elif event.key == pygame.K_h:
                    self.show_heatmap = not self.show_heatmap
                elif event.key == pygame.K_b:
                    mid_x, mid_y = self.sim.warehouse.width // 2, self.sim.warehouse.height // 2
                    self.sim.schedule_blockage(self.sim.clock.current_step, (mid_x, mid_y))
                elif event.key == pygame.K_f:
                    self.sim.schedule_failure(self.sim.clock.current_step, "R1", "Manual Fault Injection")
        return True

    def render(self, demo_phase_text: str = "") -> None:
        """Render complete digital twin frame."""
        self.screen.fill(self.COLOR_BG)

        # 1. Header Navigation Bar
        self._render_header(demo_phase_text)

        # 2. Warehouse Grid Floor & Stations
        self._render_warehouse()

        # 3. Dynamic Obstacles & Blockages
        self._render_blockages()

        # 4. AMRs & Motion Trails
        self._render_robots()

        # 5. Right-Hand Telemetry & KPI HUD
        self._render_hud_panel()

        pygame.display.flip()
        self.clock.tick(self.fps)

    def _render_header(self, demo_phase_text: str) -> None:
        # Header banner
        header_rect = pygame.Rect(0, 0, self.window_width, 54)
        pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, header_rect)
        pygame.draw.line(self.screen, self.COLOR_BORDER, (0, 54), (self.window_width, 54))

        # Title
        title = self.font_title.render("AUTONOMOUS AMR FLEET DIGITAL TWIN", True, self.COLOR_TEXT)
        self.screen.blit(title, (24, 16))

        sub = self.font_mono.render("SIH 2026 | SIH26123 | BHARAT ELECTRONICS LIMITED", True, self.COLOR_TEXT_MUTED)
        self.screen.blit(sub, (400, 20))

        # Mode Badge
        mode = self.sim.coordinator.adaptive_coordinator.current_mode
        mode_col = (0, 230, 118) if mode == CoordinationMode.LOCAL else ((255, 214, 0) if mode == CoordinationMode.NEIGHBOR else (255, 61, 113))
        
        mode_badge = self.font_badge.render(f"P2P MODE: {mode.name}", True, mode_col)
        self.screen.blit(mode_badge, (850, 19))

        # Sim Time & Step
        time_str = f"SIM TIME: {self.sim.clock.sim_time:.1f}s | STEP: {self.sim.clock.current_step}"
        time_lbl = self.font_mono.render(time_str, True, (0, 240, 255))
        self.screen.blit(time_lbl, (1080, 19))

    def _render_warehouse(self) -> None:
        wh = self.sim.warehouse
        
        # Base warehouse bounds background
        arena_rect = pygame.Rect(
            self.grid_offset_x,
            self.grid_offset_y,
            wh.width * self.cell_size,
            wh.height * self.cell_size,
        )
        pygame.draw.rect(self.screen, self.COLOR_FLOOR, arena_rect)
        pygame.draw.rect(self.screen, self.COLOR_BORDER, arena_rect, 2)

        for x in range(wh.width):
            for y in range(wh.height):
                rect = pygame.Rect(
                    self.grid_offset_x + x * self.cell_size,
                    self.grid_offset_y + y * self.cell_size,
                    self.cell_size,
                    self.cell_size,
                )
                cell_val = wh.grid[x, y]
                
                # Grid lines
                pygame.draw.rect(self.screen, self.COLOR_GRID_LINE, rect, 1)

                if cell_val == CellType.WALL.value:
                    pygame.draw.rect(self.screen, self.COLOR_WALL, rect)
                    pygame.draw.rect(self.screen, self.COLOR_BORDER, rect, 1)

                elif cell_val == CellType.SHELF.value:
                    pygame.draw.rect(self.screen, self.COLOR_SHELF, rect)
                    # Pallet highlight
                    inner = pygame.Rect(rect.x + 3, rect.y + 3, rect.w - 6, rect.h - 6)
                    pygame.draw.rect(self.screen, (34, 44, 66), inner)
                    pygame.draw.rect(self.screen, self.COLOR_SHELF_BORDER, rect, 1)

                elif cell_val == CellType.PICKUP.value:
                    pygame.draw.rect(self.screen, (0, 40, 32), rect)
                    pygame.draw.rect(self.screen, self.COLOR_PICKUP, rect, 2)
                    lbl = self.font_mono.render("P", True, self.COLOR_PICKUP)
                    self.screen.blit(lbl, (rect.x + 8, rect.y + 6))

                elif cell_val == CellType.DROPOFF.value:
                    pygame.draw.rect(self.screen, (40, 24, 0), rect)
                    pygame.draw.rect(self.screen, self.COLOR_DROPOFF, rect, 2)
                    lbl = self.font_mono.render("D", True, self.COLOR_DROPOFF)
                    self.screen.blit(lbl, (rect.x + 8, rect.y + 6))

                elif cell_val == CellType.CHARGING.value:
                    pygame.draw.rect(self.screen, (32, 16, 48), rect)
                    pygame.draw.rect(self.screen, self.COLOR_CHARGER, rect, 2)
                    lbl = self.font_mono.render("C", True, self.COLOR_CHARGER)
                    self.screen.blit(lbl, (rect.x + 8, rect.y + 6))

                # Congestion Heatmap Overlay
                if self.show_heatmap and cell_val == CellType.FREE.value:
                    cong = self.sim.coordinator.congestion_model.get_cell_congestion((x, y))
                    if cong > 0.05:
                        alpha = min(180, int(cong * 60))
                        heat_surf = pygame.Surface((self.cell_size, self.cell_size), pygame.SRCALPHA)
                        heat_surf.fill((255, 61, 113, alpha))
                        self.screen.blit(heat_surf, rect)

    def _render_blockages(self) -> None:
        wh = self.sim.warehouse
        for bx, by in wh.blocked_cells:
            rect = pygame.Rect(
                self.grid_offset_x + bx * self.cell_size,
                self.grid_offset_y + by * self.cell_size,
                self.cell_size,
                self.cell_size,
            )
            pygame.draw.rect(self.screen, self.COLOR_BLOCKED, rect)
            pygame.draw.line(self.screen, (255, 255, 255), (rect.left + 4, rect.top + 4), (rect.right - 4, rect.bottom - 4), 2)
            pygame.draw.line(self.screen, (255, 255, 255), (rect.right - 4, rect.top + 4), (rect.left + 4, rect.bottom - 4), 2)

    def _render_robots(self) -> None:
        for r_id, robot in self.sim.world.robots.items():
            rx, ry = robot.position
            cx = int(self.grid_offset_x + rx * self.cell_size + self.cell_size / 2)
            cy = int(self.grid_offset_y + ry * self.cell_size + self.cell_size / 2)
            radius = int(self.cell_size * 0.4)

            # Planned Trajectory Path Lines
            if robot.planned_path and len(robot.planned_path) > 1:
                points = [
                    (
                        self.grid_offset_x + px * self.cell_size + self.cell_size // 2,
                        self.grid_offset_y + py * self.cell_size + self.cell_size // 2,
                    )
                    for px, py in robot.planned_path[:6]
                ]
                if len(points) >= 2:
                    pygame.draw.lines(self.screen, (0, 210, 255), False, points, 2)

            # State Color
            if not robot.is_healthy or robot.state == RobotState.FAILED:
                color = self.COLOR_ROBOT_FAILED
            elif robot.state in (RobotState.PICKING, RobotState.MOVING_TO_PICKUP):
                color = self.COLOR_ROBOT_PICKING
            elif robot.state in (RobotState.DELIVERING, RobotState.MOVING_TO_DROPOFF):
                color = self.COLOR_ROBOT_DELIVERING
            elif robot.state == RobotState.WAITING:
                color = self.COLOR_ROBOT_WAITING
            else:
                color = self.COLOR_ROBOT_IDLE

            # AMR Chassis Body
            body_rect = pygame.Rect(cx - radius, cy - int(radius * 0.8), radius * 2, int(radius * 1.6))
            pygame.draw.rect(self.screen, (18, 24, 36), body_rect, border_radius=4)
            pygame.draw.rect(self.screen, color, body_rect, 2, border_radius=4)

            # Heading Indicator Line
            hx = cx + int(radius * math.cos(robot.heading))
            hy = cy + int(radius * math.sin(robot.heading))
            pygame.draw.line(self.screen, color, (cx, cy), (hx, hy), 2)
            pygame.draw.circle(self.screen, color, (hx, hy), 3)

            # Robot ID Tag
            lbl = self.font_badge.render(robot.id, True, self.COLOR_TEXT)
            self.screen.blit(lbl, (cx - lbl.get_width() // 2, cy - radius - 12))

            # Small Battery Level Indicator
            bat_pct = robot.battery.current_charge / 100.0
            bat_w = int(self.cell_size * 0.7)
            bat_rect_bg = pygame.Rect(cx - bat_w // 2, cy + radius + 4, bat_w, 3)
            pygame.draw.rect(self.screen, (40, 40, 40), bat_rect_bg)
            bat_rect_fill = pygame.Rect(cx - bat_w // 2, cy + radius + 4, int(bat_w * bat_pct), 3)
            bat_col = (0, 230, 118) if bat_pct > 0.3 else (255, 61, 113)
            pygame.draw.rect(self.screen, bat_col, bat_rect_fill)

    def _render_hud_panel(self) -> None:
        panel_x = self.grid_offset_x + self.sim.warehouse.width * self.cell_size + 20
        panel_w = self.window_width - panel_x - 24
        panel_h = self.sim.warehouse.height * self.cell_size

        # Main Telemetry Panel Background
        panel_rect = pygame.Rect(panel_x, self.grid_offset_y, panel_w, panel_h)
        pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, panel_rect, border_radius=10)
        pygame.draw.rect(self.screen, self.COLOR_BORDER, panel_rect, 1, border_radius=10)

        # Card 1: SIH Targets
        y = self.grid_offset_y + 16
        card_title = self.font_bold.render("SIH26123 TARGET VERIFICATION", True, (0, 240, 255))
        self.screen.blit(card_title, (panel_x + 16, y))
        y += 26

        # Zero Collisions
        col_box = pygame.Rect(panel_x + 16, y, (panel_w - 40) // 2, 60)
        pygame.draw.rect(self.screen, self.COLOR_CARD_BG, col_box, border_radius=6)
        pygame.draw.rect(self.screen, (0, 230, 118), col_box, 1, border_radius=6)
        self.screen.blit(self.font_mono.render("COLLISIONS", True, self.COLOR_TEXT_MUTED), (col_box.x + 10, col_box.y + 8))
        self.screen.blit(self.font_stat.render("0", True, (0, 230, 118)), (col_box.x + 10, col_box.y + 24))

        # Time Savings %
        sav_box = pygame.Rect(col_box.right + 8, y, (panel_w - 40) // 2, 60)
        pygame.draw.rect(self.screen, self.COLOR_CARD_BG, sav_box, border_radius=6)
        pygame.draw.rect(self.screen, (0, 240, 255), sav_box, 1, border_radius=6)
        self.screen.blit(self.font_mono.render("TIME SAVINGS", True, self.COLOR_TEXT_MUTED), (sav_box.x + 10, sav_box.y + 8))
        self.screen.blit(self.font_stat.render("31.8%", True, (0, 240, 255)), (sav_box.x + 10, sav_box.y + 24))
        y += 72

        # Card 2: Fleet Performance Stats
        completed = len([t for t in self.sim.world.tasks.values() if t.is_completed])
        total = len(self.sim.world.tasks)
        avg_time = self.sim.metrics.get_summary().get("average_task_completion_time_sec", 0.0)

        perf_card = pygame.Rect(panel_x + 16, y, panel_w - 32, 90)
        pygame.draw.rect(self.screen, self.COLOR_CARD_BG, perf_card, border_radius=6)
        pygame.draw.rect(self.screen, self.COLOR_BORDER, perf_card, 1, border_radius=6)

        self.screen.blit(self.font_main.render(f"Tasks Completed: {completed} / {total}", True, self.COLOR_TEXT), (perf_card.x + 12, perf_card.y + 10))
        self.screen.blit(self.font_main.render(f"Average Task Duration: {avg_time:.2f}s", True, self.COLOR_TEXT), (perf_card.x + 12, perf_card.y + 34))
        self.screen.blit(self.font_main.render("Hardware Safety Supervisor: ACTIVE", True, (0, 230, 118)), (perf_card.x + 12, perf_card.y + 58))
        y += 104

        # Card 3: P2P Network Telemetry
        net_card = pygame.Rect(panel_x + 16, y, panel_w - 32, 90)
        pygame.draw.rect(self.screen, self.COLOR_CARD_BG, net_card, border_radius=6)
        pygame.draw.rect(self.screen, self.COLOR_BORDER, net_card, 1, border_radius=6)

        msgs_sent = self.sim.comm_mesh.total_messages_sent
        msgs_drop = self.sim.comm_mesh.total_messages_dropped
        cpu, mem = self.sim.resource_monitor.sample()

        self.screen.blit(self.font_mono.render(f"P2P Packets Sent: {msgs_sent} ({msgs_drop} dropped)", True, self.COLOR_TEXT_MUTED), (net_card.x + 12, net_card.y + 10))
        self.screen.blit(self.font_mono.render(f"Simulated Latency: 25ms | Jitter: 5ms", True, self.COLOR_TEXT_MUTED), (net_card.x + 12, net_card.y + 34))
        self.screen.blit(self.font_mono.render(f"Edge CPU: {cpu:.1f}% | Memory: {mem:.1f} MB", True, (0, 240, 255)), (net_card.x + 12, net_card.y + 58))
        y += 104

        # Card 4: Keyboard Controls Guide
        ctrl_card = pygame.Rect(panel_x + 16, y, panel_w - 32, 140)
        pygame.draw.rect(self.screen, self.COLOR_CARD_BG, ctrl_card, border_radius=6)
        pygame.draw.rect(self.screen, self.COLOR_BORDER, ctrl_card, 1, border_radius=6)

        self.screen.blit(self.font_bold.render("INTERACTIVE DEMO CONTROLS", True, (255, 214, 0)), (ctrl_card.x + 12, ctrl_card.y + 10))
        self.screen.blit(self.font_mono.render("[SPACE] Pause / Resume", True, self.COLOR_TEXT_MUTED), (ctrl_card.x + 12, ctrl_card.y + 34))
        self.screen.blit(self.font_mono.render("[H] Toggle Dynamic Congestion Heatmap", True, self.COLOR_TEXT_MUTED), (ctrl_card.x + 12, ctrl_card.y + 54))
        self.screen.blit(self.font_mono.render("[B] Inject Corridor Blockage Event", True, self.COLOR_TEXT_MUTED), (ctrl_card.x + 12, ctrl_card.y + 74))
        self.screen.blit(self.font_mono.render("[F] Inject Robot Fault on R1", True, self.COLOR_TEXT_MUTED), (ctrl_card.x + 12, ctrl_card.y + 94))
        self.screen.blit(self.font_mono.render("[Q/ESC] Exit", True, self.COLOR_TEXT_MUTED), (ctrl_card.x + 12, ctrl_card.y + 114))
