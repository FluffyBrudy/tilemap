"""
Menu Bar

Dropdown menu system.
"""
import pygame
from pygame import Rect, Color
from typing import List, Callable

from .theme import COLORS, FONTS
from utils.font_manager import font_manager, FontWeight


class MenuAction:
    def __init__(self, label: str, callback: Callable, shortcut: str = ""):
        self.label = label
        self.callback = callback
        self.shortcut = shortcut


class Menu:
    def __init__(self, label: str, actions: List[MenuAction]):
        self.label = label
        self.actions = actions
        self.is_open = False
        self.rect = Rect(0, 0, 0, 0)
        self.dropdown_rect = Rect(0, 0, 0, 0)


class MenuBar:
    def __init__(self, editor, width: int, height: int = 30):
        self.editor = editor
        self.rect = Rect(0, 0, width, height)
        self.bg_color = COLORS.header
        self.border_color = COLORS.border_soft
        self.text_color = COLORS.text
        self.hover_color = COLORS.hover
        self.open_color = COLORS.panel_alt
        self.accent_color = COLORS.accent

        self.font = font_manager.get_font(FONTS.name, FONTS.size_md, FontWeight.REGULAR)
        self.font_shortcut = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)

        self.menus = [
            Menu(
                "File",
                [
                    MenuAction("New Project", self.editor.open_map_setup, "Ctrl+N"),
                    MenuAction("Open Map", self.editor.perform_load, "Ctrl+O"),
                    MenuAction("Save Map", self.editor.perform_quick_save, "Ctrl+S"),
                    MenuAction(
                        "Save As...", self.editor.open_save_as_dialog, "Ctrl+Shift+S"
                    ),
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
                    MenuAction("Character Collision Editor", self.editor.launch_character_collision_editor),
                    MenuAction(
                        "Autotile Active Layer", self.editor.autotile_active, "Ctrl+A"
                    ),
                    MenuAction("Flood Fill Tool", self.editor.flood_fill_active, "F"),
                    MenuAction(
                        "Toggle Auto-Autotile", self.editor.toggle_auto_autotile
                    ),
                    MenuAction(
                        "Launch External Viewer", self.editor.launch_external_automap
                    ),
                ],
            ),
            Menu(
                "View",
                [
                    MenuAction("Toggle Grid", self.editor.toggle_grid, "G"),
                ],
            ),
        ]

        self._layout_menus()

    def resize(self, width: int):
        self.rect.width = width
        self._layout_menus()

    def _layout_menus(self):
        x = 5
        for menu in self.menus:
            txt_surf = self.font.render(menu.label, True, self.text_color)
            w = txt_surf.get_width() + 24
            menu.rect = Rect(x, 0, w, self.rect.height)

            # Dropdown calculation
            item_h = 26
            max_w = 180
            for action in menu.actions:
                label_w = self.font.render(
                    action.label, True, self.text_color
                ).get_width()
                if action.shortcut:
                    shortcut_w = self.font_shortcut.render(
                        action.shortcut, True, COLORS.text_dim
                    ).get_width()
                    max_w = max(max_w, label_w + shortcut_w + 40)
                else:
                    max_w = max(max_w, label_w + 30)

            menu.dropdown_rect = Rect(
                x, self.rect.height, max_w, len(menu.actions) * item_h + 10
            )
            x += w

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse_pos = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                # Check dropdowns first
                for menu in self.menus:
                    if menu.is_open and menu.dropdown_rect.collidepoint(mouse_pos):
                        rel_y = mouse_pos[1] - menu.dropdown_rect.y - 5
                        idx = rel_y // 26
                        if 0 <= idx < len(menu.actions):
                            menu.actions[idx].callback()
                            menu.is_open = False
                            return True

                # Check top level
                for menu in self.menus:
                    if menu.rect.collidepoint(mouse_pos):
                        was_open = menu.is_open
                        for m in self.menus:
                            m.is_open = False
                        menu.is_open = not was_open
                        return True

                # Close all if clicked elsewhere
                for m in self.menus:
                    m.is_open = False

        elif event.type == pygame.MOUSEMOTION:
            # If a menu is open, handle "sliding" selection
            any_open = any(m.is_open for m in self.menus)
            if any_open:
                for menu in self.menus:
                    if menu.rect.collidepoint(mouse_pos) and not menu.is_open:
                        for m in self.menus:
                            m.is_open = False
                        menu.is_open = True
                        break

        # Only consume mouse events that are within the menu bar or open dropdowns
        if event.type in (
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
            pygame.MOUSEWHEEL,
        ):
            return any(
                m.is_open and m.dropdown_rect.collidepoint(mouse_pos)
                for m in self.menus
            ) or self.rect.collidepoint(mouse_pos)

        return False

    def draw(self, screen: pygame.Surface):
        # Bar background
        pygame.draw.rect(screen, self.bg_color, self.rect)
        pygame.draw.line(
            screen,
            self.border_color,
            (0, self.rect.height - 1),
            (self.rect.width, self.rect.height - 1),
        )

        mouse_pos = pygame.mouse.get_pos()

        for menu in self.menus:
            # Draw host item
            is_hover = menu.rect.collidepoint(mouse_pos)
            if menu.is_open:
                pygame.draw.rect(screen, self.open_color, menu.rect)
                pygame.draw.rect(
                    screen,
                    self.accent_color,
                    (menu.rect.x, menu.rect.height - 2, menu.rect.width, 2),
                )
            elif is_hover:
                pygame.draw.rect(screen, self.hover_color, menu.rect)

            txt_surf = self.font.render(menu.label, True, self.text_color)
            screen.blit(txt_surf, txt_surf.get_rect(center=menu.rect.center))

            # Draw dropdown
            if menu.is_open:
                # Dropdown shadow/background
                shadow_rect = menu.dropdown_rect.copy()
                shadow_rect.inflate_ip(4, 4)
                pygame.draw.rect(
                    screen, (20, 20, 25, 100), shadow_rect
                )  # Simple shadow

                pygame.draw.rect(screen, self.bg_color, menu.dropdown_rect)
                pygame.draw.rect(screen, self.border_color, menu.dropdown_rect, 1)

                for i, action in enumerate(menu.actions):
                    item_rect = Rect(
                        menu.dropdown_rect.x + 2,
                        menu.dropdown_rect.y + 5 + i * 26,
                        menu.dropdown_rect.width - 4,
                        26,
                    )
                    if item_rect.collidepoint(mouse_pos):
                        pygame.draw.rect(screen, self.accent_color, item_rect)
                        color = Color("white")
                        shortcut_color = Color("white")
                    else:
                        color = self.text_color
                        shortcut_color = COLORS.text_dim

                    label_surf = self.font.render(action.label, True, color)
                    screen.blit(label_surf, (item_rect.x + 10, item_rect.y + 5))

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
