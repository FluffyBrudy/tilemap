import pygame
from pygame import Rect, Surface

from widgets.input import SignedIntInput
from widgets.ui.button import Button
from widgets.ui.dialog_base import DialogBase
from widgets.ui.theme import COLORS, FONTS, SHAPE


class ResizeMapDialog(DialogBase):
    def __init__(self, editor_rect: Rect):
        super().__init__(editor_rect, (460, 280), "Resize Map")
        self.error_message = ""

        self.inputs = []
        self.offset_x_input = SignedIntInput(
            Rect(0, 0, 0, 0),
            "Offset X",
            "offset_x",
            default_val="0",
        )
        self.offset_y_input = SignedIntInput(
            Rect(0, 0, 0, 0),
            "Offset Y",
            "offset_y",
            default_val="0",
        )
        self.width_input = SignedIntInput(
            Rect(0, 0, 0, 0),
            "Width",
            "width",
            default_val="50",
        )
        self.height_input = SignedIntInput(
            Rect(0, 0, 0, 0),
            "Height",
            "height",
            default_val="50",
        )
        self.inputs = [
            self.offset_x_input,
            self.offset_y_input,
            self.width_input,
            self.height_input,
        ]

        self.btn_apply = Button(
            Rect(0, 0, 120, 36),
            "Apply",
            bg=COLORS.success,
            border_radius=SHAPE.radius_sm,
            font=FONTS.get_medium_font(),
            on_click=self.submit,
        )
        self.btn_cancel = Button(
            Rect(0, 0, 120, 36),
            "Cancel",
            bg=COLORS.danger,
            border_radius=SHAPE.radius_sm,
            font=FONTS.get_medium_font(),
            on_click=self.hide,
        )
        self._layout()

    def _layout(self):
        self.rect.center = self.editor_rect.center
        self._update_content_rect()

        content_x = self.rect.x + 30
        content_w = self.rect.width - 60
        input_w = (content_w - 20) // 2
        input_h = 70
        start_y = self.rect.y + 70

        self.offset_x_input.resize(Rect(content_x, start_y, input_w, input_h))
        self.offset_y_input.resize(Rect(content_x + input_w + 20, start_y, input_w, input_h))
        self.width_input.resize(Rect(content_x, start_y + 90, input_w, input_h))
        self.height_input.resize(Rect(content_x + input_w + 20, start_y + 90, input_w, input_h))

        # Increased spacing from 10px to 30px between buttons
        self.btn_cancel.rect = Rect(
            self.rect.centerx - 135, self.rect.bottom - 46, 120, 36
        )
        self.btn_apply.rect = Rect(
            self.rect.centerx + 15, self.rect.bottom - 46, 120, 36
        )

    def open(self):
        self.error_message = ""
        if self.editor_rect is None:
            return
        tm = getattr(self.editor, "tilemap", None)
        if tm is None:
            return
        self.offset_x_input.text = str(tm.offset[0])
        self.offset_y_input.text = str(tm.offset[1])
        self.width_input.text = str(tm.map_size[0])
        self.height_input.text = str(tm.map_size[1])
        self.offset_x_input.cursor_pos = len(self.offset_x_input.text)
        self.offset_y_input.cursor_pos = len(self.offset_y_input.text)
        self.width_input.cursor_pos = len(self.width_input.text)
        self.height_input.cursor_pos = len(self.height_input.text)
        self.active = True
        self.center()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False

        if self.handle_event_base(event):
            return True

        if self.btn_apply.handle_event(event):
            return True
        if self.btn_cancel.handle_event(event):
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.hide()
                return True
            if event.key == pygame.K_RETURN:
                self.submit()
                return True

        for widget in self.inputs:
            if widget.handle_event(event):
                return True

        return True

    def _check_tiles_outside_bounds(
        self, new_offset: tuple[int, int], new_size: tuple[int, int]
    ) -> bool:
        """Check if any tiles would be outside the new bounds."""
        tm = self.editor.tilemap
        ox, oy = new_offset
        w, h = new_size

        for layer in tm.layer_manager.layers:
            for (tx, ty), _tile in layer.tiles.items():
                if tx < ox or tx >= ox + w or ty < oy or ty >= oy + h:
                    return True

            if layer.layer_type == "object":
                for obj in layer.objects.values():
                    area = obj["area"]
                    obj_x = area["x"] // tm.tile_size[0]
                    obj_y = area["y"] // tm.tile_size[1]
                    if obj_x < ox or obj_x >= ox + w or obj_y < oy or obj_y >= oy + h:
                        return True

        return False

    def submit(self):
        tm = getattr(self.editor, "tilemap", None)
        if tm is None:
            self.error_message = "No map available"
            return

        try:
            offset_x = int(self.offset_x_input.text.strip() or "0")
            offset_y = int(self.offset_y_input.text.strip() or "0")
            width = int(self.width_input.text.strip() or "0")
            height = int(self.height_input.text.strip() or "0")
            if width <= 0 or height <= 0:
                raise ValueError("Width and height must be greater than 0")

            # Check if resize would make tiles inaccessible
            if self._check_tiles_outside_bounds((offset_x, offset_y), (width, height)):
                self.editor.confirm_dialog.show(
                    "Confirm Resize",
                    "Resizing will make tiles outside the new bounds inaccessible (but not deleted). Continue?",
                    on_confirm=lambda: self._do_resize(
                        offset_x, offset_y, width, height
                    ),
                    on_cancel=lambda: None,
                )
                return

            self._do_resize(offset_x, offset_y, width, height)
        except ValueError as exc:
            self.error_message = str(exc)

    def _do_resize(self, offset_x: int, offset_y: int, width: int, height: int):
        """Actually perform the resize after confirmation."""
        tm = self.editor.tilemap
        tm.capture_history("Resize Map")
        tm.resize((offset_x, offset_y), (width, height))
        self.editor.notifications.notify(
            f"Map resized to {width}x{height} at offset ({offset_x}, {offset_y})"
        )
        self.error_message = ""
        self.hide()

    def draw(self, surface: Surface):
        if not self.active:
            return

        self._layout()
        overlay = pygame.Surface((self.editor.width, self.editor.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        super().draw_base(surface)
        self._draw_title(surface, color=COLORS.text)

        info = FONTS.get_small_font().render(
            "Enter the new map bounds and top-left offset.",
            True,
            COLORS.text_dim,
        )
        surface.blit(info, (self.rect.x + 30, self.rect.y + 48))

        for widget in self.inputs:
            widget.draw(surface)

        self.btn_apply.draw(surface)
        self.btn_cancel.draw(surface)

        if self.error_message:
            err = FONTS.get_small_font().render(self.error_message, True, COLORS.danger)
            surface.blit(err, (self.rect.x + 30, self.btn_apply.rect.y - 20))
