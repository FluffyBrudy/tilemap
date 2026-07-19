"""Best-effort system clipboard for plain text (no extra dependencies required)."""

from __future__ import annotations


def copy_plain_text(text: str) -> bool:
    """Copy text to clipboard using multiple fallback methods.

    Returns True if successful, False if all methods fail.
    """
    if not text:
        return False
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except Exception as e:
        try:
            from utils import error_handler

            error_handler.capture(e, context="clipboard_pyperclip", severity="warning")
        except ImportError:
            pass
    try:
        import subprocess

        proc = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE,
            text=True,
        )
        proc.communicate(text, timeout=5)
        if proc.returncode == 0:
            return True
    except Exception:
        pass
    try:
        import subprocess

        proc = subprocess.Popen(
            ["wl-copy"],
            stdin=subprocess.PIPE,
            text=True,
        )
        proc.communicate(text, timeout=5)
        if proc.returncode == 0:
            return True
    except Exception as e:
        try:
            from utils import error_handler

            error_handler.capture(
                e, context="clipboard_subprocess_wsl", severity="warning"
            )
        except ImportError:
            pass
    try:
        import tkinter as tk

        r = tk.Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
        return True
    except Exception as e:
        try:
            from utils import error_handler

            error_handler.capture(e, context="clipboard_tkinter", severity="warning")
        except ImportError:
            pass
        return False
