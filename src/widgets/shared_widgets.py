from pygame import display, Surface
from typing import TYPE_CHECKING, Tuple, cast
import pygame
from pygame_gui.core import ObjectID
from pygame_gui.windows import UIMessageWindow


if TYPE_CHECKING:
    from ttypes import TCoor


def alert(message: str, size: "None | TCoor" = None):
    scr_w, scr_h = cast(Surface, display.get_surface()).size
    if size is None:
        w, h = scr_w * 0.5, scr_h * 0.5
    else:
        w, h = size

    pos_x = int((scr_w - w) * 0.5)
    pos_y = int((scr_h - h) * 0.5)
    UIMessageWindow(
        rect=(pos_x, pos_y, w, h),
        html_message=f"<b>{message}</b>",
        always_on_top=True,
        object_id=ObjectID(class_id="@alert"),
    )
