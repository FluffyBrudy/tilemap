
from __future__ import annotations

import re
from pathlib import Path

import pygame
from pygame import Rect, Surface

from utils.error_handler import error_handler
from utils.font_manager import FontWeight, font_manager
from widgets.filemanager import FileManager
from widgets.input import InputBox
from widgets.ui.button import Button
from widgets.ui.collision_layer_sidebar import CollisionLayerSidebar
from widgets.ui.draw_utils import draw_panel
from widgets.ui.theme import COLORS, FONTS, SHAPE
from widgets.ui.toast import ToastManager

from .models import CharacterCollisionData
from .shape_editor import ShapeEditor, ShapeType


class CharacterCollisionEditor:
    """Main editor for character collision shapes."""

    def __init__(
        self,
        rect: Rect,
        sprite_surface: Surface | None = None,
        character_name: str = "Character",
    ):
        self.rect = rect
        self.sprite_surface = sprite_surface
        self.character_name = character_name
        self._data_root: Path = None
        self._image_path: str | None = None
        self.visible = True

        self.toolbar_height = 50
        self.properties_height = 100

        shape_editor_rect = Rect(
            rect.x,
            rect.y + self.toolbar_height,
            rect.w,
            rect.h - self.toolbar_height - self.properties_height,
        )

        self.shape_editor = ShapeEditor(shape_editor_rect, sprite_surface)

        self.layer_sidebar = CollisionLayerSidebar(
            rect,
            max_layers=16,
            initial_layer=1,
            initial_mask=0xFFFF,
        )

        self._font = font_manager.get_font(
            FONTS.name, FONTS.size_md, FontWeight.REGULAR
        )
        self._font_sm = font_manager.get_font(
            FONTS.name, FONTS.size_sm, FontWeight.REGULAR
        )

        self._name_input = InputBox(self._name_input_rect(), font=self._font_sm)
        self._name_input.text = self.character_name

        self._toast_manager = ToastManager()
        self._load_dialog: FileManager | None = None

        self._buttons: list[Button] = []
        self._shape_btns: list[Button] = []
        self._load_btn: Button | None = None
        self._open_image_btn: Button | None = None
        self._init_buttons()

    def _init_buttons(self) -> None:
        self._buttons.clear()
        self._load_btn = Button(
            Rect(0, 0, 60, 28),
            "Load",
            on_click=self._open_load_dialog,
        )
        self._open_image_btn = Button(
            Rect(0, 0, 60, 28),
            "Open",
            on_click=self._open_image_dialog,
        )
        self._buttons.append(self._load_btn)
        self._buttons.append(self._open_image_btn)

        shape_types: list[ShapeType] = ["rectangle", "circle", "capsule"]
        self._shape_btns.clear()
        for stype in shape_types:
            btn = Button(
                Rect(0, 0, 100, 28),
                stype.capitalize(),
                on_click=lambda s=stype: self.shape_editor.set_shape_type(s),
            )
            self._shape_btns.append(btn)
            self._buttons.append(btn)

        self._layout_buttons()

    def _layout_buttons(self) -> None:
        y = self.rect.y + 10
        name_right = self._name_input.rect.right
        x = name_right + 12

        self._load_btn.resize(x, y, 60, 28)
        x += 60 + 8

        self._open_image_btn.resize(x, y, 60, 28)
        x += 60 + 32

        for btn in self._shape_btns:
            btn.resize(x, y, 100, 28)
            x += 100 + 8

    def _rel_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self._data_root)) if self._data_root else str(path.resolve())
        except ValueError:
            return str(path.resolve())

    def _resolve_image_path(self, image_path: str) -> Path | None:
        p = Path(image_path)
        if not p.is_absolute() and self._data_root:
            p = self._data_root / p
        return p if p.exists() else None

    def _load_sprite_from_path(self, path: Path) -> bool:
        try:
            raw = pygame.image.load(str(path))
            surf = raw.convert_alpha() if raw.get_flags() & pygame.SRCALPHA else raw.convert()
            self.sprite_surface = surf
            self.shape_editor.load_sprite(surf)
            return True
        except Exception:
            return False

    def _on_load_selected(self, path: Path) -> None:
        try:
            self.load_from_file(path)
            self._toast_manager.success("Collision data loaded")
        except ValueError as e:
            self._toast_manager.error(str(e))
        except Exception as e:
            self._toast_manager.error(f"Failed to load: {e}")
        finally:
            self._load_dialog = None

    def _open_load_dialog(self) -> None:
        try:
            collision_dir = self._get_collision_dir()
            collision_dir.mkdir(parents=True, exist_ok=True)
            sw = pygame.display.get_surface().get_width()
            sh = pygame.display.get_surface().get_height()
            dialog_rect = Rect((sw - 800) // 2, (sh - 600) // 2, 800, 600)
            self._load_dialog = FileManager(
                rect=dialog_rect,
                initial_dir=collision_dir,
                allowed_exts=[".json"],
                on_select=self._on_load_selected,
                on_cancel=lambda: setattr(self, "_load_dialog", None),
                mode="open",
                draw_overlay=True,
            )
        except RuntimeError:
            self._toast_manager.error("Data root not set")

    def _on_image_selected(self, path: Path) -> None:
        try:
            raw = pygame.image.load(str(path))
            surface = raw.convert_alpha() if raw.get_flags() & pygame.SRCALPHA else raw.convert()
            self.sprite_surface = surface
            self.shape_editor.load_sprite(surface)
            self.character_name = path.stem
            self._name_input.text = path.stem
            self._name_input.cursor_pos = len(path.stem)
            self._image_path = self._rel_path(path)
            pygame.display.set_caption(f"Character Collision Editor — {path.stem}")
            self._toast_manager.success(f"Loaded sprite: {path.name}")
        except Exception as e:
            self._toast_manager.error(f"Failed to load image: {e}")
        finally:
            self._image_dialog = None

    def _open_image_dialog(self) -> None:
        try:
            data_root = self._data_root or Path.cwd()
            sw = pygame.display.get_surface().get_width()
            sh = pygame.display.get_surface().get_height()
            dialog_rect = Rect((sw - 800) // 2, (sh - 600) // 2, 800, 600)
            self._image_dialog = FileManager(
                rect=dialog_rect,
                initial_dir=data_root,
                allowed_exts=[".png", ".jpg", ".jpeg"],
                on_select=self._on_image_selected,
                on_cancel=lambda: setattr(self, "_image_dialog", None),
                mode="open",
                draw_overlay=True,
            )
        except Exception as e:
            self._toast_manager.error(str(e))

    def resize(self, rect: Rect) -> None:
        """Resize the editor"""
        self.rect = rect

        shape_editor_rect = Rect(
            rect.x,
            rect.y + self.toolbar_height,
            rect.w,
            rect.h - self.toolbar_height - self.properties_height,
        )

        self.shape_editor.resize(shape_editor_rect)
        self.layer_sidebar.resize(rect)

        self._name_input.resize(self._name_input_rect())
        self._layout_buttons()

    def _get_save_name(self) -> str:
        name = self._name_input.text.strip()
        if name:
            safe = re.sub(r"[^\w\-]+", "-", name).strip("-").lower()
            return f"{safe}.collision.json"
        return "character.collision.json"

    def get_collision_data(self) -> CharacterCollisionData:
        """Get the current collision data"""
        shape_data = self.shape_editor.get_shape_data()

        from .models import (
            CapsuleCollisionData,
            CircleCollisionData,
            PolygonCollisionData,
            RectangleCollisionData,
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
            image_path=self._image_path,
            properties={
                "collision_layer": self.layer_sidebar.get_layer(),
                "collision_mask": self.layer_sidebar.get_mask(),
            },
        )

    def load_collision_data(self, data: CharacterCollisionData) -> None:
        """Load collision data + auto-resolve sprite from image_path"""
        self.character_name = data.name
        self._name_input.text = data.name
        self._name_input.cursor_pos = len(data.name)

        # Load sprite first so _center_shape() sets sensible defaults,
        # THEN apply saved shape data (overrides centered defaults)
        self._image_path = data.image_path
        if self._image_path:
            resolved = self._resolve_image_path(self._image_path)
            if resolved:
                self._load_sprite_from_path(resolved)
                self._toast_manager.success(f"Sprite loaded: {resolved.name}")

        if data.name and self.sprite_surface is None:
            for d in [self._data_root]:
                if d is None:
                    continue
                for ext in (".png", ".jpg", ".jpeg"):
                    candidate = d / f"{data.name}{ext}"
                    if candidate.exists():
                        if self._load_sprite_from_path(candidate):
                            self._image_path = self._rel_path(candidate)
                            self._toast_manager.success(f"Sprite loaded: {candidate.name}")
                            break

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
        collision_dir = self._get_collision_dir()
        name_path = collision_dir / self._get_save_name()
        if name_path.exists():
            return name_path

        files = sorted(collision_dir.glob("*.collision.json"))
        if files:
            return files[0]

        return collision_dir / self._get_save_name()

    def _get_collision_dir(self) -> Path:
        """Get collision data directory (data_root/character_collision)"""
        if self._data_root is None:
            raise RuntimeError(
                "data_root is required. Initialize via from_path() with data_root parameter."
            )
        return self._data_root / "character_collision"

    def save_to_file(self, path: Path) -> None:
        """Save collision data to file"""
        try:
            import json

            data = self.get_collision_data()
            with open(path, "w") as f:
                json.dump(data.to_dict(), f, indent=2)
        except Exception as e:
            error_handler.capture(e, context="save_character_collision")

    def _validate_collision_data(self, data: dict) -> None:
        if not isinstance(data, dict):
            raise ValueError("Invalid collision file: expected a JSON object")
        if "name" not in data or not isinstance(data.get("name"), str):
            raise ValueError("Invalid collision file: missing 'name' field")
        shape = data.get("shape")
        if not isinstance(shape, dict):
            raise ValueError("Invalid collision file: missing or invalid 'shape' field")
        shape_type = shape.get("type")
        valid_types = ("rectangle", "circle", "capsule", "polygon")
        if shape_type not in valid_types:
            raise ValueError(
                f"Invalid collision file: unknown shape type '{shape_type}'"
                f" — expected one of {', '.join(valid_types)}"
            )

    def load_from_file(self, path: Path) -> None:
        """Load collision data from file"""
        try:
            import json

            with open(path) as f:
                data_dict = json.load(f)
            self._validate_collision_data(data_dict)
            data = CharacterCollisionData.from_dict(data_dict)
            self.load_collision_data(data)
        except json.JSONDecodeError:
            raise ValueError("Invalid collision file: not valid JSON") from None
        except KeyError as e:
            raise ValueError(f"Invalid collision file: missing field {e}") from None
        except ValueError:
            raise
        except Exception as e:
            error_handler.capture(e, context="load_character_collision")
            raise ValueError(f"Failed to load collision data: {e}") from None

    def _name_input_rect(self) -> Rect:
        """Screen rect for the editable name field in the toolbar."""
        label_w = self._font_sm.size("Name:")[0]
        return Rect(self.rect.x + 10 + label_w + 8, self.rect.y + 10, 160, 28)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle input events"""
        if not self.visible:
            return False

        if self._load_dialog is not None:
            if self._load_dialog.handle_event(event):
                return True
            return True

        if getattr(self, "_image_dialog", None) is not None:
            if self._image_dialog.handle_event(event):
                return True
            return True

        mouse = pygame.mouse.get_pos()

        if self.layer_sidebar.handle_event(event):
            return True

        if self.layer_sidebar.handle_toggle_event(event):
            return True

        if (
            event.type == pygame.KEYDOWN
            and event.key == pygame.K_l
            and not self._name_input.is_focused
        ):
            mods = pygame.key.get_mods()
            if not (mods & (pygame.KMOD_CTRL | pygame.KMOD_LMETA)):
                self.layer_sidebar.toggle()
                return True

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl_or_cmd = mods & (pygame.KMOD_CTRL | pygame.KMOD_LMETA)
            if ctrl_or_cmd and event.key in (pygame.K_s, pygame.K_l):
                if self._name_input.is_focused:
                    self._name_input.is_focused = False
                return False

        if self._name_input.handle_event(event):
            return True
        if self._name_input.is_focused and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self._name_input.is_focused = False
                return True

        if self.shape_editor.handle_event(event):
            return True

        return any(btn.handle_event(event) for btn in self._buttons)

    def draw(self, screen: Surface) -> None:
        """Draw the editor"""
        if not self.visible:
            return

        if self._load_dialog is not None:
            self._load_dialog.draw(screen)
            return

        if getattr(self, "_image_dialog", None) is not None:
            self._image_dialog.draw(screen)
            return

        self._draw_toolbar(screen)

        self.shape_editor.draw(screen)

        self.layer_sidebar.draw_toggle_button(screen)

        self.layer_sidebar.draw(screen)

        self._draw_properties(screen)

    def _draw_toolbar(self, screen: Surface) -> None:
        """Draw the toolbar"""
        toolbar_rect = Rect(self.rect.x, self.rect.y, self.rect.w, self.toolbar_height)
        draw_panel(screen, toolbar_rect, COLORS.header, COLORS.border)

        label = self._font_sm.render("Name:", True, COLORS.text)
        screen.blit(label, (toolbar_rect.x + 10, toolbar_rect.y + 17))

        self._name_input.draw(screen)

        for btn in self._buttons:
            if hasattr(btn, "_active") and btn.text in ("Rectangle", "Circle", "Capsule"):
                btn.active = (self.shape_editor.shape_type == btn.text.lower())
            btn.draw(screen)

    def _draw_properties(self, screen: Surface) -> None:
        """Draw the properties panel"""
        props_rect = Rect(
            self.rect.x,
            self.rect.bottom - self.properties_height,
            self.rect.w,
            self.properties_height,
        )
        draw_panel(screen, props_rect, COLORS.panel, COLORS.border)

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
                COLORS.text_dim,
            )
            screen.blit(text, (x, y))
        elif shape_data["type"] == "circle":
            text = self._font_sm.render(
                f"Radius: {shape_data['radius']:.1f}  Offset: ({shape_data['offset'][0]:.1f}, {shape_data['offset'][1]:.1f})",
                True,
                COLORS.text_dim,
            )
            screen.blit(text, (x, y))
        elif shape_data["type"] == "capsule":
            text = self._font_sm.render(
                f"Radius: {shape_data['radius']:.1f}  Height: {shape_data['height']:.1f}  Offset: ({shape_data['offset'][0]:.1f}, {shape_data['offset'][1]:.1f})",
                True,
                COLORS.text_dim,
            )
            screen.blit(text, (x, y))
        elif shape_data["type"] == "polygon":
            vertex_count = len(shape_data["vertices"])
            text = self._font_sm.render(
                f"Vertices: {vertex_count}", True, COLORS.text_dim
            )
            screen.blit(text, (x, y))

    @classmethod
    def from_path(
        cls,
        sprite_path: Path | None = None,
        window_size: tuple[int, int] = (1000, 800),
        character_name: str = "Character",
        data_root: Path = None,
    ) -> CharacterCollisionEditor:
        """Create editor from sprite image path (for standalone use)"""
        surface = None
        image_path = None
        if sprite_path is not None:
            raw = pygame.image.load(str(sprite_path))
            surface = raw.convert_alpha() if raw.get_flags() & pygame.SRCALPHA else raw.convert()
            try:
                image_path = str(sprite_path.relative_to(data_root)) if data_root else str(sprite_path)
            except ValueError:
                image_path = str(sprite_path)
        rect = Rect(0, 0, window_size[0], window_size[1])
        editor = cls(rect, surface, character_name)
        editor._data_root = data_root
        editor._image_path = image_path
        return editor

    def run(self) -> None:
        """Run standalone editor (for standalone use)"""
        screen = pygame.display.get_surface()
        if screen is None:
            raise RuntimeError("pygame display not initialized")

        clock = pygame.time.Clock()
        running = True

        while running:
            dt = clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self._load_dialog is None and getattr(self, "_image_dialog", None) is None:
                            running = False
                    elif event.key == pygame.K_s and (
                        pygame.key.get_mods() & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA)
                    ):
                        collision_dir = self._get_collision_dir()
                        collision_dir.mkdir(parents=True, exist_ok=True)
                        save_path = self._get_save_path()
                        try:
                            self.save_to_file(save_path)
                            self._toast_manager.success("Collision data saved")
                            print(f"Saved collision data to {save_path}")
                        except Exception as e:
                            self._toast_manager.error(f"Save failed: {e}")
                        continue
                    elif event.key == pygame.K_l and (
                        pygame.key.get_mods() & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA)
                    ):
                        load_path = self._get_load_path()
                        if load_path.exists():
                            try:
                                self.load_from_file(load_path)
                                self._toast_manager.success("Collision data loaded")
                                print(f"Loaded collision data from {load_path}")
                            except Exception as e:
                                self._toast_manager.error(f"Load failed: {e}")
                        continue

                self.handle_event(event)

            self._toast_manager.update(screen, dt)

            screen.fill(COLORS.bg)
            self.draw(screen)
            self._toast_manager.draw(screen)
            pygame.display.flip()
