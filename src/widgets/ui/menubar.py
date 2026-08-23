from collections.abc import Callable

import pygame
from pygame import Rect

from widgets.ui.theme import COLORS, FONTS, SHAPE


class MenuAction:
    def __init__(
        self,
        label: str,
        callback: Callable,
        shortcut: str = "",
        is_checked: Callable[[], bool] | None = None,
        is_enabled: Callable[[], bool] | None = None,
    ):
        self.label = label
        self.callback = callback
        self.shortcut = shortcut
        self.is_checked = is_checked
        self.is_enabled = is_enabled


class MenuSeparator:
    """Drop-in entry for menu action lists: renders a horizontal divider."""


class Menu:
    def __init__(self, label: str, actions: list[MenuAction]):
        self.label = label
        self.actions = actions
        self.is_open = False
        self.rect = Rect(0, 0, 0, 0)
        self.dropdown_rect = Rect(0, 0, 0, 0)


class MenuBar:
    def __init__(self, editor, width: int, height: int = 30, menus=None):
        self.editor = editor
        self.rect = Rect(0, 0, width, height)
        self.font = FONTS.get_medium_font()
        self.font_shortcut = FONTS.get_small_font()
        self._custom_menus = menus

        self.menus = menus if menus is not None else self._build_default_menus()

        self._layout_menus()

    def _build_default_menus(self) -> list[Menu]:
        editor = self.editor
        return [
            Menu(
                "File",
                [
                    MenuAction("New Project", self.editor.open_map_setup, "Ctrl+N"),
                    MenuAction("Open Map", self.editor.perform_load, "Ctrl+O"),
                    MenuAction("Save Map", self.editor.perform_quick_save, "Ctrl+S"),
                    MenuAction(
                        "Save As...", self.editor.open_save_as_dialog, "Ctrl+Shift+S"
                    ),
                    MenuAction("Map Properties", self.editor.open_map_properties),
                    MenuAction("Resize Map", self.editor.open_resize_map_dialog),
                    MenuAction("Exit", self.editor.exit_editor),
                ],
            ),
            Menu(
                "Edit",
                [
                    MenuAction("Undo", self.editor.undo, "Ctrl+Z"),
                    MenuAction("Redo", self.editor.redo, "Ctrl+Y"),
                ],
            ),
            Menu(
                "Tools",
                [
                    MenuAction(
                        "Autotile Designer", self.editor.toggle_autotiler, "Ctrl+R"
                    ),
                    MenuAction(
                        "Regex Automap Designer",
                        self.editor.toggle_regex_automap,
                        "Ctrl+M",
                    ),
                    MenuAction("Animation Editor", self.editor.launch_animation_editor),
                    MenuAction("Sprite Editor", self.editor.launch_sprite_editor),
                    MenuAction(
                        "Character Collision Editor",
                        self.editor.launch_character_collision_editor,
                    ),
                    MenuAction(
                        "Autotile Active Layer", self.editor.autotile_active, "Ctrl+A"
                    ),
                    MenuAction("Flood Fill Tool", self.editor.flood_fill_active, "F"),
                    MenuAction(
                        "Toggle Auto-Autotile", self.editor.toggle_auto_autotile
                    ),
                    MenuAction(
                        "Export Selection as PNG",
                        self.editor.export_selection_as_png,
                        "Ctrl+Shift+E",
                    ),
                    MenuAction(
                        "Launch External Viewer", self.editor.launch_external_automap
                    ),
                ],
            ),
            Menu(
                "View",
                [
                    MenuAction(
                        "Toggle Grid",
                        self.editor.toggle_grid,
                        "G",
                        is_checked=lambda: self.editor.tile_grid_widget.show_grid
                        if self.editor.tile_grid_widget
                        else False,
                    ),
                    MenuAction(
                        "Toggle Map Boundary",
                        editor.toggle_map_boundary,
                        "Ctrl+B",
                        is_checked=lambda: editor.tile_grid_widget.show_map_boundary
                        if editor.tile_grid_widget
                        else True,
                    ),
                ],
            ),
        ]

    def resize(self, width: int):
        self.rect.width = width
        self._layout_menus()

    ITEM_H = 28
    SEP_H = 10

    def _layout_menus(self):
        x = 5
        for menu in self.menus:
            txt_surf = self.font.render(menu.label, True, COLORS.text)
            w = txt_surf.get_width() + 24
            menu.rect = Rect(x, 0, w, self.rect.height)

            max_w = 180
            for action in menu.actions:
                if isinstance(action, MenuSeparator):
                    continue
                label_w = self.font.render(
                    action.label, True, COLORS.text
                ).get_width()
                if action.shortcut:
                    shortcut_w = self.font_shortcut.render(
                        action.shortcut, True, COLORS.text_dim
                    ).get_width()
                    max_w = max(max_w, label_w + shortcut_w + 40)
                else:
                    max_w = max(max_w, label_w + 30)

            total_h = sum(
                self.SEP_H if isinstance(a, MenuSeparator) else self.ITEM_H
                for a in menu.actions
            )
            menu.dropdown_rect = Rect(x, self.rect.height, max_w, total_h + 10)

            item_rects = []
            iy = menu.dropdown_rect.y + 5
            for action in menu.actions:
                h = self.SEP_H if isinstance(action, MenuSeparator) else self.ITEM_H
                item_rects.append(
                    (
                        Rect(menu.dropdown_rect.x + 2, iy, menu.dropdown_rect.width - 4, h),
                        action,
                    )
                )
                iy += h
            menu.item_rects = item_rects
            x += w

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse_pos = getattr(event, "pos", None) or pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                for menu in self.menus:
                    if menu.is_open and menu.dropdown_rect.collidepoint(mouse_pos):
                        for item_rect, action in menu.item_rects:
                            if not item_rect.collidepoint(mouse_pos):
                                continue
                            if isinstance(action, MenuSeparator):
                                return True
                            enabled = (
                                action.is_enabled is None or action.is_enabled()
                            )
                            if not enabled:
                                return True
                            action.callback()
                            menu.is_open = False
                            return True
                        return True

                for menu in self.menus:
                    if menu.rect.collidepoint(mouse_pos):
                        was_open = menu.is_open
                        for m in self.menus:
                            m.is_open = False
                        menu.is_open = not was_open
                        return True

                for m in self.menus:
                    m.is_open = False

        elif event.type == pygame.MOUSEMOTION:
            any_open = any(m.is_open for m in self.menus)
            if any_open:
                for menu in self.menus:
                    if menu.rect.collidepoint(mouse_pos) and not menu.is_open:
                        for m in self.menus:
                            m.is_open = False
                        menu.is_open = True
                        break

        if event.type == pygame.MOUSEWHEEL:
            # wheel events carry no position: only block the canvas while a
            # dropdown is actually open
            return any(m.is_open for m in self.menus)

        if event.type in (
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
        ):
            if mouse_pos is None:
                return False
            return any(
                m.is_open and m.dropdown_rect.collidepoint(mouse_pos)
                for m in self.menus
            ) or self.rect.collidepoint(mouse_pos)

        return False

    def draw(self, screen: pygame.Surface):

        pygame.draw.rect(screen, COLORS.header, self.rect)
        pygame.draw.line(
            screen,
            COLORS.border_soft,
            (0, self.rect.height - 1),
            (self.rect.width, self.rect.height - 1),
        )

        mouse_pos = pygame.mouse.get_pos()

        for menu in self.menus:
            is_hover = menu.rect.collidepoint(mouse_pos)
            if menu.is_open:
                pygame.draw.rect(screen, COLORS.panel_alt, menu.rect)
                pygame.draw.rect(
                    screen,
                    COLORS.accent,
                    (menu.rect.x, menu.rect.height - 2, menu.rect.width, 2),
                )
            elif is_hover:
                pygame.draw.rect(screen, COLORS.hover, menu.rect)

            txt_surf = self.font.render(menu.label, True, COLORS.text)
            screen.blit(txt_surf, txt_surf.get_rect(center=menu.rect.center))

            if menu.is_open:
                shadow_rect = menu.dropdown_rect.copy()
                shadow_rect.inflate_ip(8, 8)
                shadow = pygame.Surface((shadow_rect.w, shadow_rect.h), pygame.SRCALPHA)
                shadow.fill((*COLORS.shadow, 60))
                pygame.draw.rect(shadow, (*COLORS.shadow, 60), shadow.get_rect(), border_radius=SHAPE.radius)
                screen.blit(shadow, shadow_rect.topleft)

                pygame.draw.rect(screen, COLORS.panel, menu.dropdown_rect, border_radius=SHAPE.radius_sm)
                pygame.draw.rect(screen, COLORS.border, menu.dropdown_rect, 1, border_radius=SHAPE.radius_sm)

                for item_rect, action in menu.item_rects:
                    if isinstance(action, MenuSeparator):
                        mid_y = item_rect.centery
                        pygame.draw.line(
                            screen,
                            COLORS.border_soft,
                            (item_rect.x + 8, mid_y),
                            (item_rect.right - 8, mid_y),
                            1,
                        )
                        continue

                    disabled = action.is_enabled is not None and not action.is_enabled()
                    hovered = (
                        item_rect.collidepoint(mouse_pos) and not disabled
                    )
                    if hovered:
                        pygame.draw.rect(screen, COLORS.accent, item_rect, border_radius=SHAPE.radius_sm)
                        color = COLORS.text_on_accent
                        shortcut_color = COLORS.text_on_accent
                    elif disabled:
                        color = COLORS.text_muted
                        shortcut_color = COLORS.text_muted
                    else:
                        color = COLORS.text
                        shortcut_color = COLORS.text_dim

                    label_x = item_rect.x + 10
                    if action.is_checked and action.is_checked():
                        from utils.icon_manager import icon_manager

                        check_icon = icon_manager.get_icon("check", 14, COLORS.success)
                        if check_icon:
                            screen.blit(check_icon, (item_rect.x + 5, item_rect.y + 6))
                        label_x = item_rect.x + 24

                    label_surf = self.font.render(action.label, True, color)
                    screen.blit(label_surf, (label_x, item_rect.y + 5))

                    if action.shortcut:
                        sh_surf = self.font_shortcut.render(
                            action.shortcut, True, shortcut_color
                        )
                        screen.blit(
                            sh_surf,
                            (
                                item_rect.right - sh_surf.get_width() - 10,
                                item_rect.y + 7,
                            ),
                        )
