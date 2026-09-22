"""Keyboard-modifier helpers: Ctrl on win/linux, Cmd on mac."""

from __future__ import annotations

import pygame

CTRL_OR_CMD = pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_GUI


def is_cmd_or_ctrl(mods: int) -> bool:
    return bool(mods & CTRL_OR_CMD)
