import json
import os
import sys
from pathlib import Path

import pygame

sys.path.append(os.path.dirname(os.path.abspath(__file__)))



class StandaloneAutomap:
    def __init__(self, target_path: Path):
        pygame.init()
        self.target_path = target_path

        self.screen = pygame.display.set_mode((800, 600))
        title_suffix = self.target_path.name if self.target_path else "Unsaved Project"
        pygame.display.set_caption(f"Automap Viewer - {title_suffix}")
        self.clock = pygame.time.Clock()
        self.running = True

        self.bg_color = (30, 30, 35)
        self.text_color = (220, 220, 220)
        self.font = pygame.font.SysFont("Arial", 14)
        self.title_font = pygame.font.SysFont("Arial", 18, bold=True)

        self.rules = []
        self.load_rules()

    def load_rules(self):
        self.rules = []
        if not self.target_path or not self.target_path.exists():
            print(f"Target path does not exist: {self.target_path}")
            return

        if self.target_path.is_file():
            try:
                with open(self.target_path, encoding="utf-8") as f:
                    data = json.load(f)

                    project_state = data.get("project_state", {})
                    self.rules = project_state.get("rules", [])
                    print(
                        f"Loaded {len(self.rules)} rules from project file: {self.target_path.name}"
                    )
            except Exception as e:
                print(
                    f"Error loading rules from project file {self.target_path.name}: {e}"
                )
        else:
            for p in self.target_path.glob("*.json"):
                try:
                    with open(p, encoding="utf-8") as f:
                        data = json.load(f)
                        self.rules.append(data)
                except Exception as e:
                    print(f"Error loading rule file {p.name}: {e}")
            print(f"Loaded {len(self.rules)} rules from directory: {self.target_path}")

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        self.load_rules()
                    if event.key == pygame.K_ESCAPE:
                        self.running = False

            self.screen.fill(self.bg_color)

            title_surf = self.title_font.render(
                f"Automap Rules: {len(self.rules)}", True, (255, 255, 255)
            )
            self.screen.blit(title_surf, (20, 20))

            hint_surf = self.font.render(
                "Press 'R' to reload rules | 'ESC' to quit", True, (150, 150, 150)
            )
            self.screen.blit(hint_surf, (20, 50))

            for i, rule in enumerate(self.rules):
                y = 100 + i * 30
                name = rule.get("name", "Unnamed Rule")
                rule_surf = self.font.render(f"{i + 1}. {name}", True, self.text_color)
                self.screen.blit(rule_surf, (40, y))

                neighbors = rule.get("neighbors", [])
                self._draw_mini_grid(self.screen, (250, y), neighbors)

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

    def _draw_mini_grid(self, screen, pos, neighbors):
        size = 8
        gap = 1
        for r in range(3):
            for c in range(3):
                ox = c - 1
                oy = r - 1
                color = (60, 60, 60)
                if ox == 0 and oy == 0:
                    color = (100, 150, 255)
                elif [ox, oy] in neighbors or (ox, oy) in neighbors:
                    color = (150, 255, 150)

                rect = pygame.Rect(
                    pos[0] + c * (size + gap), pos[1] + r * (size + gap), size, size
                )
                pygame.draw.rect(screen, color, rect)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: standalone_automap.py <target_path>", file=sys.stderr)
        sys.exit(1)
    target = Path(sys.argv[1])
    app = StandaloneAutomap(target)
    app.run()
