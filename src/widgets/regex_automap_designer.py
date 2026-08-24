"""
RegexAutomapDesigner UI component for pattern-based tile transformations.

This module provides a visual interface for creating and managing automap pattern rules,
allowing users to define input patterns that match tiles and output patterns that replace them.

.. deprecated::
    This designer is scheduled for removal. Its rules persist positional
    ``tileset_index`` values that are NOT remapped when a tileset is removed
    from the widget; saved rules may silently re-point at the wrong tileset.
    Use the autotiler (``widgets/autotiler.py``) instead.
"""

import warnings
from typing import TYPE_CHECKING

import pygame
from pygame import Color, Rect, Surface

from utils import error_handler
from widgets.automap_models import (
    AutomapEngine,
    MatchMode,
    PatternCell,
    PatternGrid,
    PatternRule,
)

if TYPE_CHECKING:
    from editor import Editor


WINDOW_BG = (40, 44, 52)
PANEL_BG = (33, 37, 43)
BORDER_COLOR = (24, 26, 31)
HEADER_COLOR = (44, 132, 250)
TEXT_COLOR = (220, 220, 220)
HIGHLIGHT_COLOR = (65, 70, 80)
GRID_ACTIVE = (152, 195, 121)
GRID_INACTIVE = (60, 64, 72)
GRID_CENTER = (97, 175, 239)


MATCH_MODE_COLORS = {
    MatchMode.EXACT: (152, 195, 121),
    MatchMode.WILDCARD: (60, 64, 72),
    MatchMode.ANY_FILLED: (229, 192, 123),
    MatchMode.ANY_EMPTY: (97, 175, 239),
}


class RegexAutomapDesigner:
    """UI component for creating and managing regex-like pattern rules for automap.

    .. deprecated::
        Scheduled for removal. Saved ``pattern_rules`` keep raw
        ``tileset_index`` values; removing/reordering tilesets makes them
        stale (they are intentionally not remapped here). Prefer the
        autotiler, which re-resolves rules by persisted ``tileset_path``.

    Provides a dual-grid interface where users can define input patterns (what to match)
    and output patterns (what to replace with). Supports various match modes including
    wildcards, exact matches, and special conditions.

    Attributes:
        editor: Reference to the main editor
        rect: Window rectangle
        visible: Whether the designer window is shown
        pattern_rules: List of saved pattern rules
        selected_rule_idx: Index of currently selected rule (-1 for none)
        input_pattern_grid: Current input pattern being edited
        output_pattern_grid: Current output pattern being edited
    """

    def __init__(self, editor: "Editor", x: int, y: int):
        """Initialize the regex automap designer.

        Args:
            editor: Reference to the main editor
            x: Initial X position
            y: Initial Y position
        """
        warnings.warn(
            "RegexAutomapDesigner is deprecated and will be removed in a "
            "future release. Its rules are not resilient to tileset removal.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.editor = editor
        self.rect = Rect(x, y, 700, 500)
        self.header_height = 30

        self.visible = False
        self.is_dragging = False
        self.drag_offset = (0, 0)

        self.pattern_rules: list[PatternRule] = []
        self.selected_rule_idx: int = -1

        self.pattern_width = 3
        self.pattern_height = 3
        self.input_pattern_grid = PatternGrid(self.pattern_width, self.pattern_height)
        self.output_pattern_grid = PatternGrid(self.pattern_width, self.pattern_height)

        self.cell_size = 40

        self.current_tile_id: int | None = None
        self.current_tileset_index: int | None = None
        self.current_preview_surf: Surface | None = None

        self.current_match_mode = MatchMode.EXACT

        self.font = pygame.font.SysFont("Arial", 12)
        self.title_font = pygame.font.SysFont("Arial", 14, bold=True)

        self.match_mode_icons = self._create_match_mode_icons()

        self._update_layout()

    def _create_match_mode_icons(self) -> dict:
        """Create and cache icon surfaces for each match mode.

        Returns:
            Dictionary mapping MatchMode to icon Surface
        """
        icon_size = 16
        icons = {}

        wildcard_surf = Surface((icon_size, icon_size), pygame.SRCALPHA)
        pygame.draw.circle(
            wildcard_surf,
            (80, 80, 100),
            (icon_size // 2, icon_size // 2),
            icon_size // 2 - 1,
        )
        pygame.draw.circle(
            wildcard_surf,
            (120, 120, 140),
            (icon_size // 2, icon_size // 2),
            icon_size // 2 - 1,
            1,
        )

        font = pygame.font.SysFont("Arial", 14, bold=True)
        asterisk = font.render("*", True, (220, 220, 240))
        wildcard_surf.blit(asterisk, (icon_size // 2 - 4, icon_size // 2 - 8))
        icons[MatchMode.WILDCARD] = wildcard_surf

        filled_surf = Surface((icon_size, icon_size), pygame.SRCALPHA)
        pygame.draw.rect(
            filled_surf, (229, 192, 123), Rect(2, 2, icon_size - 4, icon_size - 4)
        )
        pygame.draw.rect(
            filled_surf, (180, 150, 90), Rect(2, 2, icon_size - 4, icon_size - 4), 2
        )

        f_text = pygame.font.SysFont("Arial", 10, bold=True).render(
            "F", True, (80, 60, 30)
        )
        filled_surf.blit(f_text, (5, 3))
        icons[MatchMode.ANY_FILLED] = filled_surf

        empty_surf = Surface((icon_size, icon_size), pygame.SRCALPHA)

        dash_color = (97, 175, 239)
        dash_length = 3

        for x in range(2, icon_size - 2, dash_length * 2):
            pygame.draw.line(
                empty_surf,
                dash_color,
                (x, 2),
                (min(x + dash_length, icon_size - 2), 2),
                2,
            )

        for x in range(2, icon_size - 2, dash_length * 2):
            pygame.draw.line(
                empty_surf,
                dash_color,
                (x, icon_size - 3),
                (min(x + dash_length, icon_size - 2), icon_size - 3),
                2,
            )

        for y in range(2, icon_size - 2, dash_length * 2):
            pygame.draw.line(
                empty_surf,
                dash_color,
                (2, y),
                (2, min(y + dash_length, icon_size - 2)),
                2,
            )

        for y in range(2, icon_size - 2, dash_length * 2):
            pygame.draw.line(
                empty_surf,
                dash_color,
                (icon_size - 3, y),
                (icon_size - 3, min(y + dash_length, icon_size - 2)),
                2,
            )

        e_text = pygame.font.SysFont("Arial", 10, bold=True).render(
            "E", True, (70, 130, 180)
        )
        empty_surf.blit(e_text, (5, 3))
        icons[MatchMode.ANY_EMPTY] = empty_surf

        exact_surf = Surface((icon_size, icon_size), pygame.SRCALPHA)
        pygame.draw.circle(
            exact_surf,
            (152, 195, 121),
            (icon_size // 2, icon_size // 2),
            icon_size // 2 - 1,
        )
        pygame.draw.circle(
            exact_surf,
            (120, 160, 90),
            (icon_size // 2, icon_size // 2),
            icon_size // 2 - 1,
            1,
        )

        check_color = (50, 80, 40)
        pygame.draw.line(exact_surf, check_color, (4, 8), (7, 11), 2)
        pygame.draw.line(exact_surf, check_color, (7, 11), (12, 5), 2)
        icons[MatchMode.EXACT] = exact_surf

        return icons

    def _update_layout(self):
        """Update layout rectangles based on current window position."""

        self.close_btn_rect = Rect(
            self.rect.right - 30, self.rect.y, 30, self.header_height
        )

        body_y = self.rect.y + self.header_height
        body_h = self.rect.height - self.header_height

        sidebar_w = 180
        self.rule_list_area = Rect(self.rect.x, body_y, sidebar_w, body_h)

        self.edit_area = Rect(
            self.rect.x + sidebar_w, body_y, self.rect.width - sidebar_w, body_h
        )

        btn_y = self.edit_area.bottom - 40
        btn_w = 80
        btn_spacing = 10

        total_btn_width = btn_w * 3 + btn_spacing * 2
        start_x = self.edit_area.centerx - total_btn_width // 2

        self.save_btn_rect = Rect(start_x, btn_y, btn_w, 30)
        self.delete_btn_rect = Rect(start_x + btn_w + btn_spacing, btn_y, btn_w, 30)
        self.apply_btn_rect = Rect(
            start_x + (btn_w + btn_spacing) * 2, btn_y, btn_w, 30
        )

        self.new_rule_btn_rect = Rect(
            self.rule_list_area.x + 10,
            self.rule_list_area.bottom - 35,
            self.rule_list_area.width - 20,
            25,
        )

    def show(self) -> None:
        """Display the automap designer window."""
        self.visible = True
        self._update_preview_from_selector()

    def hide(self) -> None:
        """Hide the automap designer window."""
        self.visible = False
        self.is_dragging = False

    def handle_event(self, event) -> bool:
        """Process user input events.

        Args:
            event: Pygame event to process

        Returns:
            True if event was handled, False otherwise
        """
        if not self.visible:
            return False

        mouse_pos = pygame.mouse.get_pos()
        self._update_preview_from_selector()

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.hide()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                header_rect = Rect(
                    self.rect.x, self.rect.y, self.rect.width, self.header_height
                )
                if self.close_btn_rect.collidepoint(mouse_pos):
                    self.hide()
                    return True
                if header_rect.collidepoint(mouse_pos):
                    self.is_dragging = True
                    self.drag_offset = (
                        mouse_pos[0] - self.rect.x,
                        mouse_pos[1] - self.rect.y,
                    )
                    return True

                if self.rule_list_area.collidepoint(mouse_pos):
                    self._handle_rule_list_click(mouse_pos)
                    return True

                if self.save_btn_rect.collidepoint(mouse_pos):
                    self._save_pattern_rule()
                    return True
                if self.delete_btn_rect.collidepoint(mouse_pos):
                    self._delete_pattern_rule()
                    return True
                if self.apply_btn_rect.collidepoint(mouse_pos):
                    self._apply_automap()
                    return True
                if self.new_rule_btn_rect.collidepoint(mouse_pos):
                    self._reset_selection()
                    return True

                if self.edit_area.collidepoint(mouse_pos):
                    if self._handle_grid_click(mouse_pos, event.button):
                        return True

            elif event.button == 3:
                if self.edit_area.collidepoint(mouse_pos):
                    if self._handle_grid_click(mouse_pos, event.button):
                        return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.is_dragging = False

        elif event.type == pygame.MOUSEMOTION and self.is_dragging:
            self.rect.x = mouse_pos[0] - self.drag_offset[0]
            self.rect.y = mouse_pos[1] - self.drag_offset[1]
            self._update_layout()
            return True

        return not (not self.rect.collidepoint(mouse_pos) and not self.is_dragging)

    def draw(self, screen: Surface):
        """Render the automap designer UI.

        Args:
            screen: Pygame surface to draw on
        """
        if not self.visible:
            return

        pygame.draw.rect(screen, WINDOW_BG, self.rect)
        pygame.draw.rect(screen, BORDER_COLOR, self.rect, 1)

        pygame.draw.rect(
            screen,
            HEADER_COLOR,
            Rect(self.rect.x, self.rect.y, self.rect.width, self.header_height),
        )
        title = self.title_font.render("Regex Automap Designer", True, Color("white"))
        screen.blit(title, (self.rect.x + 10, self.rect.y + 5))

        pygame.draw.rect(screen, (200, 60, 60), self.close_btn_rect)
        x_lbl = self.title_font.render("X", True, Color("white"))
        screen.blit(x_lbl, (self.close_btn_rect.x + 10, self.close_btn_rect.y + 5))

        pygame.draw.rect(screen, PANEL_BG, self.rule_list_area)

        self._draw_rule_list(screen)
        self._draw_pattern_grids(screen)
        self._draw_buttons(screen)

    def _update_preview_from_selector(self):
        """Update current tile selection from the editor's tile selector."""
        tile_selector = getattr(self.editor, "tileset_widget", None)
        if tile_selector and tile_selector.selected_tile:
            ts = tile_selector.get_active_tile()
            if ts:
                current_rect = tile_selector.selected_tile
                tile_w, tile_h = self.editor.tilemap.tile_size
                sheet_cols = ts.surface.get_width() // tile_w

                rx, ry, rw, rh = current_rect
                start_cx = rx // tile_w
                start_cy = ry // tile_h

                vid = (start_cy * sheet_cols) + start_cx
                self.current_tile_id = vid
                self.current_tileset_index = tile_selector.active_idx

                sub_rect = Rect(start_cx * tile_w, start_cy * tile_h, tile_w, tile_h)
                try:
                    self.current_preview_surf = ts.surface.subsurface(sub_rect).copy()
                except Exception as e:
                    error_handler.capture(e, context="regex_automap_preview")

    def _handle_rule_list_click(self, mouse_pos):
        """Handle clicks on the rule list."""

        if self.new_rule_btn_rect.collidepoint(mouse_pos):
            self._reset_selection()
            return

        start_y = self.rule_list_area.y + 30
        item_h = 25
        for i, rule in enumerate(self.pattern_rules):
            item_rect = Rect(
                self.rule_list_area.x + 5,
                start_y + i * item_h,
                self.rule_list_area.width - 10,
                item_h,
            )
            if item_rect.collidepoint(mouse_pos):
                self.selected_rule_idx = i
                self._load_rule_to_editor(rule)
                break

    def _handle_grid_click(self, mouse_pos, button: int) -> bool:
        """Handle clicks on pattern grids.

        Args:
            mouse_pos: Mouse position tuple
            button: Mouse button (1=left, 3=right)

        Returns:
            True if a grid was clicked
        """

        input_grid_rect, output_grid_rect = self._get_grid_rects()

        clicked_grid = None
        if input_grid_rect.collidepoint(mouse_pos):
            clicked_grid = self.input_pattern_grid
            grid_rect = input_grid_rect
        elif output_grid_rect.collidepoint(mouse_pos):
            clicked_grid = self.output_pattern_grid
            grid_rect = output_grid_rect
        else:
            return False

        rel_x = mouse_pos[0] - grid_rect.x
        rel_y = mouse_pos[1] - grid_rect.y

        cell_x = rel_x // self.cell_size
        cell_y = rel_y // self.cell_size

        if 0 <= cell_x < self.pattern_width and 0 <= cell_y < self.pattern_height:
            if button == 1:
                self._set_pattern_cell(clicked_grid, cell_x, cell_y)
            elif button == 3:
                self._cycle_match_mode(clicked_grid, cell_x, cell_y)
            return True

        return False

    def _get_grid_rects(self) -> tuple[Rect, Rect]:
        """Calculate the rectangles for input and output pattern grids.

        Returns:
            Tuple of (input_grid_rect, output_grid_rect)
        """
        grid_w = self.pattern_width * self.cell_size
        grid_h = self.pattern_height * self.cell_size

        spacing = 40
        total_width = grid_w * 2 + spacing
        start_x = self.edit_area.centerx - total_width // 2
        start_y = self.edit_area.y + 100

        input_grid_rect = Rect(start_x, start_y, grid_w, grid_h)
        output_grid_rect = Rect(start_x + grid_w + spacing, start_y, grid_w, grid_h)

        return input_grid_rect, output_grid_rect

    def _set_pattern_cell(self, grid: PatternGrid, x: int, y: int):
        """Set a pattern cell with the current tile selection.

        Args:
            grid: The pattern grid to modify
            x: Cell X coordinate
            y: Cell Y coordinate
        """
        if self.current_tile_id is not None and self.current_tileset_index is not None:
            cell = PatternCell(
                tile_id=self.current_tile_id,
                tileset_index=self.current_tileset_index,
                match_mode=self.current_match_mode,
            )
            grid.set_cell(x, y, cell)

    def _cycle_match_mode(self, grid: PatternGrid, x: int, y: int):
        """Cycle through match modes for a pattern cell.

        Args:
            grid: The pattern grid to modify
            x: Cell X coordinate
            y: Cell Y coordinate
        """
        cell = grid.get_cell(x, y)

        mode_cycle = [
            MatchMode.EXACT,
            MatchMode.WILDCARD,
            MatchMode.ANY_FILLED,
            MatchMode.ANY_EMPTY,
        ]

        try:
            current_idx = mode_cycle.index(cell.match_mode)
            next_idx = (current_idx + 1) % len(mode_cycle)
        except ValueError:
            next_idx = 0

        tile_id = cell.tile_id if cell.tile_id is not None else self.current_tile_id
        tileset_index = (
            cell.tileset_index
            if cell.tileset_index is not None
            else self.current_tileset_index
        )

        next_mode = mode_cycle[next_idx]

        new_cell = PatternCell(
            tile_id=tile_id, tileset_index=tileset_index, match_mode=next_mode
        )

        grid.cells[(x, y)] = new_cell

    def _load_rule_to_editor(self, rule: PatternRule):
        """Load a pattern rule into the editor grids.

        Args:
            rule: The pattern rule to load
        """
        self.input_pattern_grid = PatternGrid(
            rule.input_pattern.width, rule.input_pattern.height
        )
        self.output_pattern_grid = PatternGrid(
            rule.output_pattern.width, rule.output_pattern.height
        )

        for (x, y), cell in rule.input_pattern.cells.items():
            self.input_pattern_grid.set_cell(x, y, cell)
        for (x, y), cell in rule.output_pattern.cells.items():
            self.output_pattern_grid.set_cell(x, y, cell)

        self.pattern_width = rule.input_pattern.width
        self.pattern_height = rule.input_pattern.height

    def _reset_selection(self):
        """Reset the editor to create a new rule."""
        self.selected_rule_idx = -1
        self.input_pattern_grid = PatternGrid(3, 3)
        self.output_pattern_grid = PatternGrid(3, 3)
        self.pattern_width = 3
        self.pattern_height = 3

    def _save_pattern_rule(self):
        """Save current input/output pattern as a rule."""
        try:
            if not self.input_pattern_grid.cells:
                print("Cannot save rule: input pattern is empty")
                return

            if self.selected_rule_idx >= 0:
                rule = self.pattern_rules[self.selected_rule_idx]
                rule.input_pattern = self.input_pattern_grid
                rule.output_pattern = self.output_pattern_grid
                print(f"Updated rule: {rule.name}")
            else:
                rule_name = f"Pattern Rule {len(self.pattern_rules) + 1}"
                try:
                    new_rule = PatternRule(
                        name=rule_name,
                        input_pattern=self.input_pattern_grid,
                        output_pattern=self.output_pattern_grid,
                        enabled=True,
                        priority=0,
                    )
                    self.pattern_rules.append(new_rule)
                    self.selected_rule_idx = len(self.pattern_rules) - 1
                    print(f"Created new rule: {rule_name}")
                except ValueError as e:
                    print(f"Cannot save rule: {e}")
                    return

            self._reset_selection()
        except Exception as e:
            import logging

            logging.error(f"Error saving pattern rule: {e}", exc_info=True)
            print(f"Error saving pattern rule: {e}")

    def _delete_pattern_rule(self):
        """Remove the currently selected pattern rule."""
        if 0 <= self.selected_rule_idx < len(self.pattern_rules):
            deleted_rule = self.pattern_rules.pop(self.selected_rule_idx)
            print(f"Deleted rule: {deleted_rule.name}")
            self._reset_selection()

    def _apply_automap(self):
        """Execute all pattern rules on the active layer."""
        layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not layer:
            print("No active layer to apply automap")
            return

        if not self.pattern_rules:
            print("No pattern rules to apply")
            return

        print(f"Applying automap to layer with {len(layer.tiles)} tiles")

        engine = AutomapEngine(self.editor.tilemap)
        transformation_count = engine.apply_rules(layer, self.pattern_rules)

        if transformation_count >= engine.max_transformations:
            print(
                f"WARNING: Transformation limit ({engine.max_transformations}) reached!"
            )
            print("This may indicate circular dependencies in your pattern rules.")
            print(
                "Consider reviewing your rules to ensure output patterns don't match input patterns."
            )
        else:
            print(f"Automap applied: {transformation_count} tile transformations")

    def serialize_rules(self) -> list[dict]:
        """Serialize all pattern rules to dictionary format with error handling.

        Returns:
            List of serialized rule dictionaries
        """
        import logging

        serialized_rules = []
        for i, rule in enumerate(self.pattern_rules):
            try:
                rule_dict = rule.to_dict()
                serialized_rules.append(rule_dict)
            except Exception as e:
                logging.error(
                    f"Error serializing rule '{rule.name}' (index {i}): {e}",
                    exc_info=True,
                )
                print(f"Warning: Failed to serialize rule '{rule.name}', skipping")

        return serialized_rules

    def deserialize_rules(self, rules_data: list[dict]) -> None:
        """Deserialize pattern rules from dictionary format with error handling.

        Args:
            rules_data: List of serialized rule dictionaries
        """
        import logging

        self.pattern_rules.clear()

        for i, rule_dict in enumerate(rules_data):
            try:
                rule = PatternRule.from_dict(rule_dict)
                self.pattern_rules.append(rule)
            except Exception as e:
                logging.warning(
                    f"Error deserializing rule at index {i}: {e}", exc_info=True
                )
                print(f"Warning: Skipping invalid rule at index {i}: {e}")

        print(f"Loaded {len(self.pattern_rules)} pattern rules")

    def _draw_rule_list(self, screen: Surface):
        """Draw the list of saved pattern rules."""

        title = self.title_font.render("Pattern Rules", True, (150, 150, 255))
        screen.blit(title, (self.rule_list_area.x + 5, self.rule_list_area.y + 5))

        start_y = self.rule_list_area.y + 30
        item_h = 25
        for i, rule in enumerate(self.pattern_rules):
            item_rect = Rect(
                self.rule_list_area.x + 5,
                start_y + i * item_h,
                self.rule_list_area.width - 10,
                item_h,
            )

            if i == self.selected_rule_idx:
                pygame.draw.rect(screen, HIGHLIGHT_COLOR, item_rect, border_radius=3)

            display_name = rule.name if len(rule.name) < 18 else rule.name[:15] + "..."
            text_surf = self.font.render(display_name, True, TEXT_COLOR)
            screen.blit(text_surf, (item_rect.x + 5, item_rect.y + 5))

        pygame.draw.rect(
            screen, (70, 130, 180), self.new_rule_btn_rect, border_radius=4
        )
        btn_text = self.font.render("+ New Rule", True, TEXT_COLOR)
        screen.blit(
            btn_text, (self.new_rule_btn_rect.x + 10, self.new_rule_btn_rect.y + 5)
        )

    def _draw_pattern_grids(self, screen: Surface):
        """Draw the input and output pattern grids."""
        input_grid_rect, output_grid_rect = self._get_grid_rects()

        input_label = self.title_font.render("Input Pattern", True, TEXT_COLOR)
        output_label = self.title_font.render("Output Pattern", True, TEXT_COLOR)
        screen.blit(input_label, (input_grid_rect.centerx - 50, input_grid_rect.y - 25))
        screen.blit(
            output_label, (output_grid_rect.centerx - 55, output_grid_rect.y - 25)
        )

        self._draw_grid(screen, self.input_pattern_grid, input_grid_rect)
        self._draw_grid(screen, self.output_pattern_grid, output_grid_rect)

        if self.current_preview_surf:
            preview_y = self.edit_area.y + 20
            scaled = pygame.transform.scale(self.current_preview_surf, (48, 48))
            screen.blit(scaled, (self.edit_area.centerx - 24, preview_y))

            mode_text = f"Mode: {self.current_match_mode.value}"
            mode_surf = self.font.render(mode_text, True, TEXT_COLOR)
            screen.blit(mode_surf, (self.edit_area.centerx - 40, preview_y + 55))

        self._draw_match_mode_legend(screen)

    def _draw_grid(self, screen: Surface, grid: PatternGrid, grid_rect: Rect):
        """Draw a single pattern grid.

        Args:
            screen: Surface to draw on
            grid: Pattern grid to draw
            grid_rect: Rectangle defining grid position
        """
        for y in range(self.pattern_height):
            for x in range(self.pattern_width):
                cell_rect = Rect(
                    grid_rect.x + x * self.cell_size,
                    grid_rect.y + y * self.cell_size,
                    self.cell_size,
                    self.cell_size,
                )

                cell = grid.get_cell(x, y)
                color = MATCH_MODE_COLORS.get(cell.match_mode, GRID_INACTIVE)

                pygame.draw.rect(screen, color, cell_rect)
                pygame.draw.rect(screen, (30, 30, 30), cell_rect, 1)

                if cell.match_mode == MatchMode.EXACT and cell.tile_id is not None:
                    self._draw_tile_in_cell(screen, cell, cell_rect)

                self._draw_match_mode_indicator(screen, cell, cell_rect)

    def _draw_tile_in_cell(self, screen: Surface, cell: PatternCell, cell_rect: Rect):
        """Draw a tile preview in a pattern cell.

        Args:
            screen: Surface to draw on
            cell: Pattern cell with tile data
            cell_rect: Rectangle of the cell
        """

        tile_selector = getattr(self.editor, "tileset_widget", None)
        if tile_selector and cell.tileset_index is not None:
            if 0 <= cell.tileset_index < len(tile_selector.tilesets):
                ts = tile_selector.tilesets[cell.tileset_index]
                tile_w, tile_h = self.editor.tilemap.tile_size
                sheet_cols = ts.surface.get_width() // tile_w

                tx = (cell.tile_id % sheet_cols) * tile_w
                ty = (cell.tile_id // sheet_cols) * tile_h

                try:
                    sub_rect = Rect(tx, ty, tile_w, tile_h)
                    tile_surf = ts.surface.subsurface(sub_rect)

                    scaled = pygame.transform.scale(
                        tile_surf, (self.cell_size - 4, self.cell_size - 4)
                    )
                    screen.blit(scaled, (cell_rect.x + 2, cell_rect.y + 2))
                except Exception as e:
                    error_handler.capture(e, "Error drawing tile in cell", "info")

    def _draw_match_mode_indicator(
        self, screen: Surface, cell: PatternCell, cell_rect: Rect
    ):
        """Draw a visual indicator for the cell's match mode.

        Args:
            screen: Surface to draw on
            cell: Pattern cell
            cell_rect: Rectangle of the cell
        """

        icon = self.match_mode_icons.get(cell.match_mode)
        if icon:
            icon_x = cell_rect.x + 2
            icon_y = cell_rect.y + 2
            screen.blit(icon, (icon_x, icon_y))

    def _draw_match_mode_legend(self, screen: Surface):
        """Draw a legend explaining the match mode icons.

        Args:
            screen: Surface to draw on
        """
        legend_x = self.edit_area.x + 10
        legend_y = self.edit_area.bottom - 120

        legend_rect = Rect(legend_x, legend_y, 160, 90)
        pygame.draw.rect(screen, PANEL_BG, legend_rect, border_radius=4)
        pygame.draw.rect(screen, BORDER_COLOR, legend_rect, 1, border_radius=4)

        title = self.font.render("Match Modes:", True, (150, 150, 255))
        screen.blit(title, (legend_x + 5, legend_y + 5))

        legend_items = [
            (MatchMode.EXACT, "Exact tile"),
            (MatchMode.WILDCARD, "Any tile"),
            (MatchMode.ANY_FILLED, "Any filled"),
            (MatchMode.ANY_EMPTY, "Empty only"),
        ]

        y_offset = legend_y + 25
        for mode, description in legend_items:
            icon = self.match_mode_icons.get(mode)
            if icon:
                screen.blit(icon, (legend_x + 8, y_offset))
                text = self.font.render(description, True, TEXT_COLOR)
                screen.blit(text, (legend_x + 28, y_offset + 1))
                y_offset += 16

    def _draw_buttons(self, screen: Surface):
        """Draw action buttons."""

        pygame.draw.rect(screen, (70, 180, 70), self.save_btn_rect, border_radius=4)
        save_text = self.font.render("Save", True, Color("white"))
        screen.blit(save_text, (self.save_btn_rect.x + 25, self.save_btn_rect.y + 8))

        if self.selected_rule_idx >= 0:
            pygame.draw.rect(
                screen, (180, 70, 70), self.delete_btn_rect, border_radius=4
            )
            del_text = self.font.render("Delete", True, Color("white"))
            screen.blit(
                del_text, (self.delete_btn_rect.x + 20, self.delete_btn_rect.y + 8)
            )

        pygame.draw.rect(screen, (100, 100, 200), self.apply_btn_rect, border_radius=4)
        apply_text = self.font.render("Apply", True, Color("white"))
        screen.blit(apply_text, (self.apply_btn_rect.x + 20, self.apply_btn_rect.y + 8))
