"""Best-effort system clipboard for plain text (no extra dependencies required)."""

from __future__ import annotations


def copy_plain_text(text: str) -> bool:
    """Copy UTF-8 text to the system clipboard. Returns True if likely succeeded."""
    if not text:
        return False
    try:
        import pyperclip  # type: ignore

        pyperclip.copy(text)
        return True
    except Exception:
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
    except Exception:
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
    except Exception:
        return False
