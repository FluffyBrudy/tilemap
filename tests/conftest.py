"""Suite-wide bootstrap: headless pygame, import path.

Everything in here applies to the whole suite, so it stays minimal:
environment setup only. Feature fixtures live in the test files (or
`e2e/conftest.py`) that need them - never here.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pygame  # noqa: E402

pygame.init()
pygame.display.set_mode((1, 1))
