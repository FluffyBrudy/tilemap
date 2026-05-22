"""
Character Collision Editor — Define collision shapes for character sprites.

Layout:
    +----------------------------------------------------+
    | Toolbar: [Name: _______] [Shape Type Buttons]      |
    +----------------------------------------------------+
    |                                                    |
    |              Shape Editor                          |
    |              (visual shape editing)                |
    |                                                    |
    +----------------------------------------------------+
    | Properties: [Width/Height/Radius/etc.]             |
    +----------------------------------------------------+
"""

from __future__ import annotations

import re
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

import pygame
from pygame import Rect, Surface

from .models import CharacterCollisionData
from .shape_editor import ShapeEditor, ShapeType
from utils.font_manager import font_manager, FontWeight
from utils.icon_manager import icon_manager
from utils.error_handler import error_handler, error_context
from widgets.ui.theme import COLORS, FONTS
from widgets.ui.draw_utils import draw_panel, draw_button
from widgets.ui.collision_layer_sidebar import CollisionLayerSidebar
from widgets.input import InlineTextInput


class CharacterCollisionEditor:
    """Main editor for character collision shapes."""

    def __init__(
        self,
        rect: Rect,
        sprite_surface: Surface,
        character_name: str = "Character",
    ):
        self.rect = rect
        self.sprite_surface = sprite_surface
        self.character_name = character_name
        self._data_root: Path = None
        self.visible = True

        # UI layout
        self.toolbar_height = 50
        self.properties_height = 100

        shape_editor_rect = Rect(
            rect.x,
            rect.y + self.toolbar_height,
            rect.w,
            rect.h - self.toolbar_height - self.properties_height
        )

        # Shape editor
        self.shape_editor = ShapeEditor(shape_editor_rect, sprite_surface)

        # Collision layer/mask sidebar (toggleable overlay)
        self.layer_sidebar = CollisionLayerSidebar(
            rect,
            max_layers=16,
            initial_layer=1,
            initial_mask=0xFFFF,
        )

        # Fonts
        self._font = font_manager.get_font(FONTS.name, FONTS.size_md, FontWeight.REGULAR)
        self._font_sm = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)

        # Editable name input
        self._name_input = InlineTextInput("char_name", default_val=self.character_name)

        # Shape type buttons
        self.shape_buttons: Dict[ShapeType, Rect] = {}
        self._init_shape_buttons()

    def _init_shape_buttons(self) -> None:
        """Initialize shape type button rects"""
        button_w = 100
        button_h = 30
        button_spacing = 10
        start_x = self.rect.x + 250

        shapes: list[ShapeType] = ["rectangle", "circle", "capsule"]
        for i, shape in enumerate(shapes):
            x = start_x + i * (button_w + button_spacing)
            y = self.rect.y + 10
            self.shape_buttons[shape] = Rect(x, y, button_w, button_h)

    def resize(self, rect: Rect) -> None:
        """Resize the editor"""
        self.rect = rect

        shape_editor_rect = Rect(
            rect.x,
            rect.y + self.toolbar_height,
            rect.w,
            rect.h - self.toolbar_height - self.properties_height
        )

        self.shape_editor.resize(shape_editor_rect)
        self.layer_sidebar.resize(rect)

        self._init_shape_buttons()

    def _get_save_name(self) -> str:
        """Build filename from the name input.

        Returns "<safe-name>-character.collision.json" if non-empty,
        "character.collision.json" otherwise.
        """
        name = self._name_input.text.strip()
        if name:
            safe = re.sub(r'[^\w\-]+', '-', name).strip('-').lower()
            return f"{safe}-character.collision.json"
        return "character.collision.json"

    def get_collision_data(self) -> CharacterCollisionData:
        """Get the current collision data"""
        shape_data = self.shape_editor.get_shape_data()
        
        # Import shape data classes
        from .models import (
            RectangleCollisionData,
            CircleCollisionData,
            CapsuleCollisionData,
            PolygonCollisionData,
        )

        shape_type = shape_data["type"]
        if shape_type == "rectangle":
            shape = RectangleCollisionData(
                width=shape_data["width"],
                height=shape_data["height"],
                offset=shape_data["offset"],
            )
        elif shape_type == "circle":
            shape = CircleCollisionData(
                radius=shape_data["radius"],
                offset=shape_data["offset"],
            )
        elif shape_type == "capsule":
            shape = CapsuleCollisionData(
                radius=shape_data["radius"],
                height=shape_data["height"],
                offset=shape_data["offset"],
            )
        elif shape_type == "polygon":
            shape = PolygonCollisionData(
                vertices=shape_data["vertices"],
                offset=shape_data["offset"],
            )
        else:
            raise ValueError(f"Unknown shape type: {shape_type}")

        return CharacterCollisionData(
            name=self._name_input.text.strip() or self.character_name,
            shape=shape,
            properties={
                "collision_layer": self.layer_sidebar.get_layer(),
                "collision_mask": self.layer_sidebar.get_mask(),
            },
        )

    def load_collision_data(self, data: CharacterCollisionData) -> None:
        """Load collision data"""
        self.character_name = data.name
        self._name_input.text = data.name
        self._name_input.cursor_pos = len(data.name)
        self.shape_editor.load_shape_data(data.shape.to_dict())
        layer = data.properties.get("collision_layer", 1)
        mask = data.properties.get("collision_mask", 0xFFFF)
        self.layer_sidebar.set_layer(layer)
        self.layer_sidebar.set_mask(mask)

    def _get_save_path(self) -> Path:
        """Full path for saving/loading collision data."""
        collision_dir = self._get_collision_dir()
        return collision_dir / self._get_save_name()

    def _get_load_path(self) -> Path:
        """Path to load from — name-priority, fallback to default."""
        collision_dir = self._get_collision_dir()
        name_path = collision_dir / self._get_save_name()
        if name_path.exists():
            return name_path
        # Fallback to default
        return collision_dir / "character.collision.json"

    def _get_collision_dir(self) -> Path:
        """Get collision data directory (data_root/character_collision)"""
        if self._data_root is None:
            raise RuntimeError("data_root is required. Initialize via from_path() with data_root parameter.")
        return self._data_root / "character_collision"

    def save_to_file(self, path: Path) -> None:
        """Save collision data to file"""
        try:
            import json
            data = self.get_collision_data()
            with open(path, 'w') as f:
                json.dump(data.to_dict(), f, indent=2)
        except Exception as e:
            error_handler.capture(e, context="save_character_collision")

    def load_from_file(self, path: Path) -> None:
        """Load collision data from file"""
        try:
            import json
            with open(path, 'r') as f:
                data_dict = json.load(f)
            data = CharacterCollisionData.from_dict(data_dict)
            self.load_collision_data(data)
        except Exception as e:
            error_handler.capture(e, context="load_character_collision")

    def _name_input_rect(self) -> Rect:
        """Screen rect for the editable name field in the toolbar."""
        return Rect(self.rect.x + 62, self.rect.y + 10, 175, 28)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle input events"""
        if not self.visible:
            return False

        mouse = pygame.mouse.get_pos()

        # Layer/mask sidebar handles events when open
        if self.layer_sidebar.handle_event(event):
            return True

        # Toggle button
        if self.layer_sidebar.handle_toggle_event(event):
            return True

        # Keyboard shortcut: L to toggle sidebar
        if event.type == pygame.KEYDOWN and event.key == pygame.K_l:
            mods = pygame.key.get_mods()
            if not (mods & (pygame.KMOD_CTRL | pygame.KMOD_LMETA)):
                self.layer_sidebar.toggle()
                return True

        # Name input handling
        if self._name_input.is_focused:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    self._name_input.is_focused = False
                    return True
                elif event.key == pygame.K_ESCAPE:
                    self._name_input.is_focused = False
                    return True
            if self._name_input.handle_event(event, self._font):
                return True
            # Tab/click outside handled below

        # Click-to-focus name input
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._name_input_rect().collidepoint(mouse):
                self._name_input.is_focused = True
                self._name_input.cursor_pos = len(self._name_input.text)
                self._name_input.selection_start = None
                return True
            elif self._name_input.is_focused:
                self._name_input.is_focused = False

        # Let shape editor handle events next
        if self.shape_editor.handle_event(event):
            return True

        # Shape type button clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for shape_type, button_rect in self.shape_buttons.items():
                if button_rect.collidepoint(mouse):
                    self.shape_editor.set_shape_type(shape_type)
                    return True

        return False

    def draw(self, screen: Surface) -> None:
        """Draw the editor"""
        if not self.visible:
            return

        # Draw toolbar
        self._draw_toolbar(screen)

        # Draw shape editor
        self.shape_editor.draw(screen)

        # Draw toggle button
        self.layer_sidebar.draw_toggle_button(screen)

        # Draw collision layer/mask sidebar (only when visible)
        self.layer_sidebar.draw(screen)

        # Draw properties panel
        self._draw_properties(screen)

    def _draw_toolbar(self, screen: Surface) -> None:
        """Draw the toolbar"""
        toolbar_rect = Rect(self.rect.x, self.rect.y, self.rect.w, self.toolbar_height)
        draw_panel(screen, toolbar_rect, COLORS.header, COLORS.border)

        # "Name:" label
        label = self._font_sm.render("Name:", True, COLORS.text)
        screen.blit(label, (toolbar_rect.x + 10, toolbar_rect.y + 17))

        # Editable name field
        name_rect = self._name_input_rect()
        bg_color = COLORS.panel if self._name_input.is_focused else COLORS.panel_alt
        pygame.draw.rect(screen, bg_color, name_rect, border_radius=4)
        pygame.draw.rect(
            screen, COLORS.accent if self._name_input.is_focused else COLORS.border,
            name_rect, 1, border_radius=4,
        )

        # Render input text
        display_name = self._name_input.text or "character"
        txt = self._font_sm.render(display_name, True, COLORS.text)
        screen.blit(txt, (name_rect.x + 4, name_rect.y + 5))

        # Cursor when focused
        if self._name_input.is_focused and (pygame.time.get_ticks() // 400) % 2:
            pre = self._font_sm.render(self._name_input.text[:self._name_input.cursor_pos], True, (0, 0, 0))
            cx = name_rect.x + 4 + pre.get_width()
            cy = name_rect.y + 5
            pygame.draw.line(screen, COLORS.text, (cx, cy), (cx, cy + txt.get_height()), 1)

        # Shape type buttons
        for shape_type, button_rect in self.shape_buttons.items():
            is_active = (self.shape_editor.shape_type == shape_type)
            
            # Render label
            label_surf = self._font_sm.render(shape_type.capitalize(), True, COLORS.text)
            
            draw_button(screen, button_rect, label_surf, active=is_active)

    def _draw_properties(self, screen: Surface) -> None:
        """Draw the properties panel"""
        props_rect = Rect(
            self.rect.x,
            self.rect.bottom - self.properties_height,
            self.rect.w,
            self.properties_height
        )
        draw_panel(screen, props_rect, COLORS.panel, COLORS.border)

        # Display current shape properties
        shape_data = self.shape_editor.get_shape_data()
        y = props_rect.y + 10
        x = props_rect.x + 10

        title = self._font.render("Properties:", True, COLORS.text)
        screen.blit(title, (x, y))
        y += 25

        if shape_data["type"] == "rectangle":
            text = self._font_sm.render(
                f"Width: {shape_data['width']:.1f}  Height: {shape_data['height']:.1f}  Offset: ({shape_data['offset'][0]:.1f}, {shape_data['offset'][1]:.1f})",
                True,
                COLORS.text_dim
            )
            screen.blit(text, (x, y))
        elif shape_data["type"] == "circle":
            text = self._font_sm.render(
                f"Radius: {shape_data['radius']:.1f}  Offset: ({shape_data['offset'][0]:.1f}, {shape_data['offset'][1]:.1f})",
                True,
                COLORS.text_dim
            )
            screen.blit(text, (x, y))
        elif shape_data["type"] == "capsule":
            text = self._font_sm.render(
                f"Radius: {shape_data['radius']:.1f}  Height: {shape_data['height']:.1f}  Offset: ({shape_data['offset'][0]:.1f}, {shape_data['offset'][1]:.1f})",
                True,
                COLORS.text_dim
            )
            screen.blit(text, (x, y))
        elif shape_data["type"] == "polygon":
            vertex_count = len(shape_data["vertices"])
            text = self._font_sm.render(
                f"Vertices: {vertex_count}",
                True,
                COLORS.text_dim
            )
            screen.blit(text, (x, y))

    @classmethod
    def from_path(
        cls,
        sprite_path: Path,
        window_size: Tuple[int, int] = (1000, 800),
        character_name: str = "Character",
        data_root: Path = None,
    ) -> "CharacterCollisionEditor":
        """Create editor from sprite image path (for standalone use)"""
        surface = pygame.image.load(sprite_path).convert_alpha()
        rect = Rect(0, 0, window_size[0], window_size[1])
        editor = cls(rect, surface, character_name)
        editor._data_root = data_root
        return editor

    def run(self) -> None:
        """Run standalone editor (for standalone use)"""
        screen = pygame.display.get_surface()
        if screen is None:
            raise RuntimeError("pygame display not initialized")

        clock = pygame.time.Clock()
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_s and (
                        pygame.key.get_mods() & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA)
                    ):
                        # Ctrl+S / Cmd+S to save
                        collision_dir = self._get_collision_dir()
                        collision_dir.mkdir(parents=True, exist_ok=True)
                        save_path = self._get_save_path()
                        self.save_to_file(save_path)
                        print(f"Saved collision data to {save_path}")
                    elif event.key == pygame.K_l and (
                        pygame.key.get_mods() & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA)
                    ):
                        # Ctrl+L / Cmd+L to load
                        load_path = self._get_load_path()
                        if load_path.exists():
                            self.load_from_file(load_path)
                            print(f"Loaded collision data from {load_path}")

                self.handle_event(event)

            screen.fill((20, 20, 20))
            self.draw(screen)
            pygame.display.flip()
            clock.tick(60)
