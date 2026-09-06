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


_CARDINAL_4 = (L, R, U, D)


def motif_dist2(motif_cells: set[tuple[int, int]], col: int, row: int) -> frozenset:
    """Distance-2 presence signature of a motif cell.

    The motif bounds act as the mass (outside = absent), mirroring off-map
    semantics at classify time, so motif-derived and map-derived
    signatures agree on motif-shaped masses.
    """
    return frozenset(
        d for d in _CARDINAL_4
        if (col + 2 * d[0], row + 2 * d[1]) in motif_cells
    )


def _cardinal_grid_mappings(w: int, h: int):
    """Position-based cardinal neighbor sets, same border rule as 3x3.

    Cell (c, r) needs L iff c > 0, R iff c < w - 1, U iff r > 0,
    D iff r < h - 1. Diagonals are ignored. Interior/edge cells share
    patterns and collapse into variants of the same rule on apply.
    """
    mappings: list[tuple[int, int, set[tuple[int, int]]]] = []
    for r in range(h):
        for c in range(w):
            neighbors: set[tuple[int, int]] = set()
            if r > 0:
                neighbors.add(U)
            if r < h - 1:
                neighbors.add(D)
            if c > 0:
                neighbors.add(L)
            if c < w - 1:
                neighbors.add(R)
            mappings.append((c, r, neighbors))
    return mappings


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
    TemplateDefinition(
        "Standard 4x4 (Cardinal)",
        _cardinal_grid_mappings(4, 4),
    ),
    TemplateDefinition(
        "Standard 5x5 (Cardinal)",
        _cardinal_grid_mappings(5, 5),
    ),
    TemplateDefinition("Horizontal 3x1", [(0, 0, {R}), (1, 0, {L, R}), (2, 0, {L})]),
    TemplateDefinition("Vertical 1x3", [(0, 0, {D}), (0, 1, {U, D}), (0, 2, {U})]),
    # Strips reuse the cardinal border rule (same helper as the blobs):
    # ends need the inward direction only, every interior cell shares
    # {L, R} / {U, D} and collapses into variants. Parity is irrelevant
    # for 1-wide strips (no center cell exists).
    TemplateDefinition(
        "Horizontal 4x1",
        _cardinal_grid_mappings(4, 1),
    ),
    TemplateDefinition(
        "Vertical 1x4",
        _cardinal_grid_mappings(1, 4),
    ),
    TemplateDefinition(
        "Horizontal 5x1",
        _cardinal_grid_mappings(5, 1),
    ),
    TemplateDefinition(
        "Vertical 1x5",
        _cardinal_grid_mappings(1, 5),
    ),
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
        # Pending 3-way collision choice: None or dict with
        # template/items/collisions/target_idx/ts_index.
        self.pending_collision: dict | None = None
        self.collision_rect = Rect(0, 0, 260, 10)
        self._collision_options = ("Merge", "Move", "Cancel")

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
        if self.pending_collision is not None:
            if self._handle_collision_event(event):
                return True
            # Pending choice takes over input until resolved.
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                return True
        if not self.visible:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.rect.collidepoint(event.pos):
                    rel_y = event.pos[1] - self.rect.y - 5
                    idx = rel_y // 25
                    if 0 <= idx < len(self.active_templates):
                        self.request_apply_template(self.active_templates[idx])
                    self.visible = False
                    return True
                self.visible = False
            return False
        return False

    def _owner_map(self, ts_index: int, exclude_group_idx: int | None = None):
        """First-group-wins owner of (ts_index, vid) -> group name.

        Matches ``AutotileRuleDesigner.variant_to_group`` precedence so
        paint-time, inspect-time and template planning agree.
        """
        owners: dict[int, str] = {}
        for gi, group in enumerate(self.designer.groups):
            if exclude_group_idx is not None and gi == exclude_group_idx:
                continue
            for rule in group.rules:
                if rule.tileset_index != ts_index:
                    continue
                for vid in rule.variant_ids:
                    if vid not in owners:
                        owners[vid] = group.name
        return owners

    def plan_template_application(self, template: TemplateDefinition):
        """Compute template vids without mutating rules.

        Returns ``(items, collisions, error)`` where items is a list of
        ``(vid, neighbors)`` in-bounds of the current tileset selection,
        collisions maps ``vid -> owner group name`` for vids already
        claimed by a *different* group on the same tileset, and error is
        a message string (items/collisions empty) when planning fails.
        """
        tile_selector = getattr(self.designer.editor, "tileset_widget", None)
        if not tile_selector or not tile_selector.selected_tile:
            return [], {}, "No selection in tileset"
        ts = tile_selector.get_active_tile()
        if not ts:
            return [], {}, "No active tileset"
        if self.designer.selected_group_idx == -1:
            return [], {}, "No group selected"

        rx, ry, rw, rh = tile_selector.selected_tile
        tile_w, tile_h = self.designer.editor.tilemap.tile_size
        sheet_cols = ts.surface.get_width() // tile_w
        start_col = rx // tile_w
        start_row = ry // tile_h
        ts_index = tile_selector.active_idx

        items: list[tuple[int, set[tuple[int, int]]]] = []
        for rel_col, rel_row, neighbors in template.mappings:
            if (rel_col * tile_w) >= rw or (rel_row * tile_h) >= rh:
                continue
            abs_col = start_col + rel_col
            abs_row = start_row + rel_row
            vid = (abs_row * sheet_cols) + abs_col
            items.append((vid, set(neighbors)))

        if not items:
            return [], {}, "Selection smaller than template"

        owners = self._owner_map(ts_index, self.designer.selected_group_idx)
        collisions = {vid: owners[vid] for vid, _ in items if vid in owners}
        return items, collisions, ""

    def _steal_vids(self, ts_index: int, vids: set[int], exclude_group_idx: int):
        """Remove vids from other groups (Move choice); prune emptied rules."""
        moved = 0
        for gi, group in enumerate(self.designer.groups):
            if gi == exclude_group_idx:
                continue
            for rule in list(group.rules):
                if rule.tileset_index != ts_index:
                    continue
                before = len(rule.variant_ids)
                rule.variant_ids = [v for v in rule.variant_ids if v not in vids]
                moved += before - len(rule.variant_ids)
                for key in list(rule.subcases):
                    leaf = [v for v in rule.subcases[key] if v not in vids]
                    if leaf:
                        rule.subcases[key] = leaf
                    else:
                        del rule.subcases[key]
            group.rules = [r for r in group.rules if r.variant_ids]
        return moved

    def request_apply_template(self, template: TemplateDefinition):
        """Apply with UI collision flow: warn on cross-group overlap."""
        items, collisions, error = self.plan_template_application(template)
        if error:
            print(f"Template Error: {error}")
            self._notify(f"Template: {error}", error=True)
            return {"added": 0, "updated": 0, "moved": 0, "error": error}

        if collisions:
            owners = sorted(set(collisions.values()))
            self.pending_collision = {
                "template": template,
                "target_idx": self.designer.selected_group_idx,
                "ts_index": getattr(
                    self.designer.editor.tileset_widget, "active_idx", None
                ),
                "collisions": collisions,
            }
            self._layout_collision_popup()
            self._notify(
                f"Template overlaps {len(collisions)} tile(s) owned by "
                f"{', '.join(owners)}. Choose Merge / Move / Cancel."
            )
            return {"added": 0, "updated": 0, "moved": 0, "pending": True,
                    "collisions": collisions}
        return self.apply_template(template, collision_choice="merge")

    def resolve_pending_collision(self, choice: str):
        """Resolve the pending 3-way choice: merge | move | cancel."""
        pending = self.pending_collision
        self.pending_collision = None
        if not pending:
            return {"added": 0, "updated": 0, "moved": 0}
        choice = (choice or "").lower()
        if choice == "cancel":
            print("Template cancelled (collision kept).")
            return {"added": 0, "updated": 0, "moved": 0, "cancelled": True}
        if choice == "move":
            return self.apply_template(
                pending["template"], collision_choice="move")
        return self.apply_template(pending["template"], collision_choice="merge")

    def _notify(self, text: str, error: bool = False):
        notifications = getattr(self.designer.editor, "notifications", None)
        if notifications is not None:
            try:
                if error:
                    notifications.error(text)
                else:
                    notifications.notify(text)
            except Exception:
                pass

    def _layout_collision_popup(self):
        ed = self.designer.editor
        w, h = 280, 30 + len(self._collision_options) * 28
        x = min(max(0, getattr(ed, "width", 800) // 2 - w // 2), max(0, getattr(ed, "width", 800) - w))
        y = min(max(0, getattr(ed, "height", 600) // 2 - h // 2), max(0, getattr(ed, "height", 600) - h))
        self.collision_rect = Rect(x, y, w, h)

    def _handle_collision_event(self, event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = getattr(event, "pos", None)
            if pos is None:
                return False
            for i, _opt in enumerate(self._collision_options):
                row = Rect(
                    self.collision_rect.x + 8,
                    self.collision_rect.y + 28 + i * 28,
                    self.collision_rect.width - 16,
                    24,
                )
                if row.collidepoint(pos):
                    self.resolve_pending_collision(_opt)
                    return True
            # Click elsewhere dismisses as cancel.
            if not self.collision_rect.collidepoint(pos):
                self.resolve_pending_collision("cancel")
                return True
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.resolve_pending_collision("cancel")
            return True
        return False

    def _selection_origin(self):
        """(start_col, start_row, sheet_cols) of the tileset selection, or None."""
        tile_selector = getattr(self.designer.editor, "tileset_widget", None)
        if not tile_selector or not tile_selector.selected_tile:
            return None
        ts = tile_selector.get_active_tile()
        if not ts:
            return None
        rx, ry, _rw, _rh = tile_selector.selected_tile
        tile_w, tile_h = self.designer.editor.tilemap.tile_size
        sheet_cols = ts.surface.get_width() // tile_w
        if not sheet_cols:
            return None
        return rx // tile_w, ry // tile_h, sheet_cols

    def apply_template(self, template: TemplateDefinition, collision_choice: str = "merge"):
        from .autotiler import AutotileRule

        items, collisions, error = self.plan_template_application(template)
        if error:
            print(f"Template Error: {error}")
            return {"added": 0, "updated": 0, "moved": 0, "error": error}

        if self.designer.selected_group_idx == -1:
            print("Template Error: No group selected. Please select a group first.")
            return {"added": 0, "updated": 0, "moved": 0, "error": "no-group"}

        if collisions and collision_choice == "cancel":
            print(
                f"Template cancelled: {len(collisions)} tile(s) already owned "
                f"by another group."
            )
            return {"added": 0, "updated": 0, "moved": 0, "cancelled": True,
                    "collisions": collisions}

        tile_selector = getattr(self.designer.editor, "tileset_widget", None)
        ts = tile_selector.get_active_tile() if tile_selector else None
        ts_index = tile_selector.active_idx if tile_selector else None
        target_group = self.designer.groups[self.designer.selected_group_idx]

        # Motif-relative coords per applied vid (clipped to the selection):
        # the applied cells are the mass for distance-2 signatures.
        motif_rel: dict[int, tuple[int, int]] = {}
        origin = self._selection_origin()
        if origin is not None:
            start_col, start_row, sheet_cols = origin
            applied = {vid for vid, _ in items}
            for rel_col, rel_row, _ in template.mappings:
                vid = ((start_row + rel_row) * sheet_cols) + (start_col + rel_col)
                if vid in applied:
                    motif_rel[vid] = (rel_col, rel_row)
        motif_cells = set(motif_rel.values())

        moved_count = 0
        if collisions and collision_choice == "move":
            moved_count = self._steal_vids(
                ts_index, set(collisions), self.designer.selected_group_idx)

        added_count = 0
        updated_count = 0

        for vid, neighbors in items:
            matched_rule = None
            for r in target_group.rules:
                if r.neighbors == neighbors and r.tileset_index == ts_index:
                    matched_rule = r
                    break

            if matched_rule:
                if vid not in matched_rule.variant_ids:
                    matched_rule.variant_ids.append(vid)
                    updated_count += 1
                rel = motif_rel.get(vid)
                if rel is not None:
                    key = motif_dist2(motif_cells, *rel)
                    leaf = matched_rule.subcases.setdefault(key, [])
                    if vid not in leaf:
                        leaf.append(vid)
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
                    tileset_path=str(ts.path) if ts else "",
                    variant_ids=[vid],
                    tileset_index=ts_index,
                    group_id=target_group.name,
                )
                rel = motif_rel.get(vid)
                if rel is not None:
                    new_rule.subcases[motif_dist2(motif_cells, *rel)] = [vid]
                target_group.rules.append(new_rule)
                added_count += 1

        print(
            f"Template Applied: {template.name} to Group '{target_group.name}'. "
            f"{added_count} rules added, {updated_count} rules updated, "
            f"{moved_count} tiles moved."
        )
        return {"added": added_count, "updated": updated_count,
                "moved": moved_count, "collisions": collisions}

    def _draw_collision_popup(self, screen: Surface):
        if self.pending_collision is None:
            return
        pending = self.pending_collision
        collisions = pending.get("collisions", {})
        owners = sorted(set(collisions.values()))
        target = ""
        try:
            target = self.designer.groups[pending.get("target_idx", -1)].name
        except Exception:
            pass
        pygame.draw.rect(screen, COLORS.panel, self.collision_rect)
        pygame.draw.rect(screen, COLORS.warning, self.collision_rect, 2)
        title = self.font.render(
            f"{len(collisions)} tile(s) owned by {', '.join(owners)}", True, COLORS.text)
        screen.blit(title, (self.collision_rect.x + 10, self.collision_rect.y + 6))
        mouse_pos = pygame.mouse.get_pos()
        hints = {"Merge": "share tiles", "Move": f"move to {target}",
                 "Cancel": "abort"}
        for i, opt in enumerate(self._collision_options):
            row = Rect(
                self.collision_rect.x + 8,
                self.collision_rect.y + 28 + i * 28,
                self.collision_rect.width - 16,
                24,
            )
            if row.collidepoint(mouse_pos):
                pygame.draw.rect(screen, COLORS.accent, row, border_radius=4)
                color = COLORS.text_on_accent
            else:
                pygame.draw.rect(screen, COLORS.panel_alt, row, border_radius=4)
                color = COLORS.text
            txt = self.font.render(f"{opt} ({hints.get(opt, '')})", True, color)
            screen.blit(txt, (row.x + 10, row.y + 4))

    def draw(self, screen: Surface):
        self._draw_collision_popup(screen)
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
