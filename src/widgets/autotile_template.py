from typing import TYPE_CHECKING

import pygame
from pygame import Rect, Surface

from .ui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from .autotiler import AutotileRule


U = (0, -1)
D = (0, 1)
L = (-1, 0)
R = (1, 0)
UL = (-1, -1)
UR = (1, -1)
DL = (-1, 1)
DR = (1, 1)


class TemplateDefinition:
    def __init__(
        self, name: str, mappings: list[tuple[int, int, set[tuple[int, int]]]]
    ):
        self.name = name
        self.mappings = mappings


TEMPLATES = [
    TemplateDefinition(
        "Standard 3x3 (Cardinal)",
        [
            (0, 0, {R, D}),
            (1, 0, {L, R, D}),
            (2, 0, {L, D}),
            (0, 1, {U, R, D}),
            (1, 1, {U, D, L, R}),
            (2, 1, {U, L, D}),
            (0, 2, {U, R}),
            (1, 2, {U, L, R}),
            (2, 2, {U, L}),
        ],
    ),
    TemplateDefinition("Horizontal 3x1", [(0, 0, {R}), (1, 0, {L, R}), (2, 0, {L})]),
    TemplateDefinition("Vertical 1x3", [(0, 0, {D}), (0, 1, {U, D}), (0, 2, {U})]),
    TemplateDefinition(
        "Corner Set (2x2)",
        [(0, 0, {R, D}), (1, 0, {L, D}), (0, 1, {U, R}), (1, 1, {U, L})],
    ),
]


class AutotileTemplateApplier:
    """Helper class to apply rule templates to selections."""

    def __init__(self, designer):
        self.designer = designer
        self.visible = False
        self.active_templates: list[TemplateDefinition] = []
        self.rect = Rect(0, 0, 200, 10)
        self.font = FONTS.get_font(12)

    def show_at(self, pos: tuple[int, int]):
        self.active_templates = self._get_active_templates()
        self.rect.height = len(self.active_templates) * 25 + 10
        self.rect.topleft = pos

        if self.rect.bottom > self.designer.editor.height:
            self.rect.bottom = self.designer.editor.height
        if self.rect.right > self.designer.editor.width:
            self.rect.right = self.designer.editor.width

        self.visible = True

    def _get_active_templates(self) -> list[TemplateDefinition]:
        all_templates = list(TEMPLATES)

        rules_by_ts = {}
        ts_widget = getattr(self.designer.editor, "tileset_widget", None)
        if not ts_widget:
            return all_templates

        for rule in self.designer.rules:
            ts_idx = rule.tileset_index
            if ts_idx is not None and 0 <= ts_idx < len(ts_widget.tilesets):
                if ts_idx not in rules_by_ts:
                    rules_by_ts[ts_idx] = []
                rules_by_ts[ts_idx].append(rule)

        for ts_idx, rules in rules_by_ts.items():
            ts_name = ts_widget.tilesets[ts_idx].name

            if ts_idx == ts_widget.active_idx:
                continue

            all_templates.append(
                self._create_template_from_rules(f"Ruleset: {ts_name}", rules)
            )

        return all_templates

    def _create_template_from_rules(
        self, name: str, rules: list["AutotileRule"]
    ) -> TemplateDefinition:
        if not rules:
            return TemplateDefinition(name, [])

        ts_widget = self.designer.editor.tileset_widget
        tile_w, tile_h = self.designer.editor.tilemap.tile_size
        ts_idx = rules[0].tileset_index
        if ts_idx is None:
            return TemplateDefinition(name, [])

        ts = ts_widget.tilesets[ts_idx]
        sheet_cols = ts.surface.get_width() // tile_w

        coords = []
        for r in rules:
            if not r.variant_ids:
                continue
            vid = r.variant_ids[0]
            col = vid % sheet_cols
            row = vid // sheet_cols
            coords.append((col, row, r.neighbors))

        if not coords:
            return TemplateDefinition(name, [])

        min_col = min(c[0] for c in coords)
        min_row = min(c[1] for c in coords)

        mappings = []
        for col, row, neighbors in coords:
            mappings.append((col - min_col, row - min_row, neighbors))

        return TemplateDefinition(name, mappings)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.rect.collidepoint(event.pos):
                    rel_y = event.pos[1] - self.rect.y - 5
                    idx = rel_y // 25
                    if 0 <= idx < len(self.active_templates):
                        self.apply_template(self.active_templates[idx])
                    self.visible = False
                    return True
                self.visible = False
            return False
        return False

    def apply_template(self, template: TemplateDefinition):
        from .autotiler import AutotileRule

        tile_selector = getattr(self.designer.editor, "tileset_widget", None)
        if not tile_selector or not tile_selector.selected_tile:
            print("Template Error: No selection in tileset")
            return

        ts = tile_selector.get_active_tile()
        if not ts:
            return

        if self.designer.selected_group_idx == -1:
            print("Template Error: No group selected. Please select a group first.")
            return

        target_group = self.designer.groups[self.designer.selected_group_idx]

        rx, ry, rw, rh = tile_selector.selected_tile
        tile_w, tile_h = self.designer.editor.tilemap.tile_size
        sheet_cols = ts.surface.get_width() // tile_w

        start_col = rx // tile_w
        start_row = ry // tile_h

        added_count = 0
        updated_count = 0

        for rel_col, rel_row, neighbors in template.mappings:
            if (rel_col * tile_w) >= rw or (rel_row * tile_h) >= rh:
                continue

            abs_col = start_col + rel_col
            abs_row = start_row + rel_row
            vid = (abs_row * sheet_cols) + abs_col

            ts_index = tile_selector.active_idx

            matched_rule = None
            for r in target_group.rules:
                if r.neighbors == neighbors and r.tileset_index == ts_index:
                    matched_rule = r
                    break

            if matched_rule:
                if vid not in matched_rule.variant_ids:
                    matched_rule.variant_ids.append(vid)
                    updated_count += 1
            else:
                rule_num = len(target_group.rules) + 1
                rule_name = f"Rule {rule_num}"

                existing_names = {r.name for r in target_group.rules}
                while rule_name in existing_names:
                    rule_num += 1
                    rule_name = f"Rule {rule_num}"

                new_rule = AutotileRule(
                    name=rule_name,
                    neighbors=set(neighbors),
                    tileset_path=str(ts.path),
                    variant_ids=[vid],
                    tileset_index=ts_index,
                    group_id=target_group.name,
                )
                target_group.rules.append(new_rule)
                added_count += 1

        print(
            f"Template Applied: {template.name} to Group '{target_group.name}'. {added_count} rules added, {updated_count} rules updated."
        )

    def draw(self, screen: Surface):
        if not self.visible:
            return

        pygame.draw.rect(screen, COLORS.panel, self.rect)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)

        mouse_pos = pygame.mouse.get_pos()

        for i, template in enumerate(self.active_templates):
            item_rect = Rect(
                self.rect.x + 2, self.rect.y + 5 + i * 25, self.rect.width - 4, 25
            )
            is_hover = item_rect.collidepoint(mouse_pos)

            if is_hover:
                pygame.draw.rect(screen, COLORS.accent, item_rect)

            txt_color = COLORS.text_on_accent if is_hover else COLORS.text_dim
            txt = self.font.render(template.name, True, txt_color)
            screen.blit(txt, (item_rect.x + 10, item_rect.y + 5))
