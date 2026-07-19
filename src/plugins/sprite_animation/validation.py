"""Lightweight animation clip checks for the editor (and optional runtime use)."""

from __future__ import annotations

from .models import Animation


def collect_clip_warnings(anim: Animation, max_variant_index: int) -> list[str]:
    """Return human-readable issues: out-of-range tiles, non-positive durations."""
    out: list[str] = []
    if max_variant_index < 0:
        return out
    for i, fr in enumerate(anim.frames):
        if fr.duration_ms <= 0:
            out.append(f"Frame {i + 1}: duration {fr.duration_ms:g} ms (need > 0)")
        if fr.variant_id < 0 or fr.variant_id > max_variant_index:
            out.append(
                f"Frame {i + 1}: variant {fr.variant_id} out of range "
                f"(need 0..{max_variant_index})"
            )
    return out
