

from ..widget_base import WidgetBase
from .theme import COLORS, FONTS


class Label(WidgetBase):
    def __init__(
        self,
        rect,
        text: str,
        *,
        font=None,
        color=None,
        align="left",
        padding=None,
        padding_x=None,
        padding_y=None,
        bg=None,
        border_color=None,
        border_width=None,
        border_radius=None,
    ):
        bw = border_width if border_width is not None else 0
        super().__init__(
            rect,
            padding=padding,
            padding_x=padding_x,
            padding_y=padding_y,
            border_width=bw,
            border_radius=border_radius,
            bg=bg,
            border_color=border_color,
        )
        self.text = text
        self.font = font or FONTS.get_medium_font()
        self.color = color or COLORS.text
        self.align = align

    def handle_event(self, event) -> bool:
        return False

    def draw(self, surface):
        if self._bg is not None or self._border is not None or self.bw > 0:
            self.draw_base(surface)
        surf = self.font.render(self.text, True, self.color)
        y = self.content_rect.centery - surf.get_height() // 2
        if self.align == "left":
            x = self.content_rect.x
        elif self.align == "center":
            x = self.content_rect.centerx - surf.get_width() // 2
        elif self.align == "right":
            x = self.content_rect.right - surf.get_width()
        else:
            x = self.content_rect.x
        surface.blit(surf, (x, y))
