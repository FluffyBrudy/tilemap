"""Small collision-shape thumbnails for the file tree.

Renders the shape's bounding-box subsurface scaled into a square with the
shape outline on top, matching the shape editor colors. Broken images get
a drawn X placeholder (lines on a surface, no text or assets).
"""

from __future__ import annotations

import pygame
from pygame import Surface

FILL = (80, 180, 255, 80)
STROKE = (100, 200, 255, 255)


def broken_thumb(size: int = 20) -> Surface:
    thumb = Surface((size, size), pygame.SRCALPHA)
    thumb.fill((60, 60, 65, 255))
    inset = 4
    pygame.draw.line(thumb, (200, 80, 80), (inset, inset), (size - inset, size - inset), 2)
    pygame.draw.line(thumb, (200, 80, 80), (size - inset, inset), (inset, size - inset), 2)
    return thumb


def _offset(shape: dict) -> tuple[float, float]:
    try:
        ox, oy = shape.get("offset", (0.0, 0.0))
        return (float(ox), float(oy))
    except (TypeError, ValueError):
        return (0.0, 0.0)


def _aabb(shape: dict, sw: int, sh: int) -> tuple[int, int, int, int] | None:
    """Shape bounding box in sprite px, clipped to the sprite. None if empty."""
    try:
        stype = shape.get("type", "rectangle")
        if stype == "rectangle":
            ox, oy = _offset(shape)
            box = (ox, oy, float(shape.get("width", 0)), float(shape.get("height", 0)))
        elif stype == "circle":
            ox, oy = _offset(shape)
            r = float(shape.get("radius", 0))
            box = (ox - r, oy - r, r * 2, r * 2)
        elif stype == "capsule":
            ox, oy = _offset(shape)
            r = float(shape.get("radius", 0))
            h = float(shape.get("height", 0))
            box = (ox - r, oy - r, r * 2, h + r * 2)
        elif stype == "polygon":
            verts = shape.get("vertices", [])
            off = _offset(shape)
            if len(verts) < 1:
                return None
            xs = [float(v[0]) + off[0] for v in verts]
            ys = [float(v[1]) + off[1] for v in verts]
            box = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        else:
            return None
        clip = pygame.Rect(int(box[0]), int(box[1]), int(box[2]), int(box[3])).clip(
            pygame.Rect(0, 0, sw, sh)
        )
        if clip.w <= 0 or clip.h <= 0:
            return None
        return (clip.x, clip.y, clip.w, clip.h)
    except (TypeError, ValueError):
        return None


def render_thumb(sprite: Surface, shape: dict, size: int = 20) -> Surface | None:
    try:
        sw, sh = sprite.get_size()
        if sw <= 0 or sh <= 0:
            return None
        ax, ay = 0, 0
        src = sprite
        crop = _aabb(shape, sw, sh)
        if crop is not None:
            try:
                src = sprite.subsurface(pygame.Rect(*crop)).copy()
            except Exception:
                src = sprite
            else:
                ax, ay = crop[0], crop[1]
        cw, ch = src.get_size()
        scale = min((size - 2) / cw, (size - 2) / ch)
        if scale <= 0:
            return None
        dw, dh = max(1, int(cw * scale)), max(1, int(ch * scale))
        thumb = Surface((size, size), pygame.SRCALPHA)
        try:
            small = pygame.transform.smoothscale(src, (dw, dh))
        except Exception:
            small = pygame.transform.scale(src, (dw, dh))
        ox, oy = (size - dw) // 2, (size - dh) // 2
        thumb.blit(small, (ox, oy))

        def pt(x: float, y: float) -> tuple[float, float]:
            return (ox + (float(x) - ax) * scale, oy + (float(y) - ay) * scale)

        stype = shape.get("type", "rectangle")
        if stype == "rectangle":
            w, h = float(shape.get("width", 0)), float(shape.get("height", 0))
            if w <= 0 or h <= 0:
                return thumb
            x, y = pt(*_offset(shape))
            r = pygame.Rect(int(x), int(y), max(1, int(w * scale)), max(1, int(h * scale)))
            pygame.draw.rect(thumb, FILL, r)
            pygame.draw.rect(thumb, STROKE, r, 1)
        elif stype == "circle":
            r = float(shape.get("radius", 0))
            if r <= 0:
                return thumb
            cx, cy = pt(*_offset(shape))
            rr = max(1, int(r * scale))
            pygame.draw.circle(thumb, FILL, (int(cx), int(cy)), rr)
            pygame.draw.circle(thumb, STROKE, (int(cx), int(cy)), rr, 1)
        elif stype == "capsule":
            r = float(shape.get("radius", 0))
            h = float(shape.get("height", 0))
            if r <= 0:
                return thumb
            x1, y1 = pt(*_offset(shape))
            x2, y2 = x1, y1 + h * scale
            rr = max(1, int(r * scale))
            for cx, cy in ((int(x1), int(y1)), (int(x2), int(y2))):
                pygame.draw.circle(thumb, FILL, (cx, cy), rr)
                pygame.draw.circle(thumb, STROKE, (cx, cy), rr, 1)
            top = min(y1, y2)
            body = pygame.Rect(int(x1 - rr), int(top), rr * 2, int(abs(h * scale)))
            if body.w > 0 and body.h > 0:
                thumb.fill(FILL, body)
        elif stype == "polygon":
            verts = shape.get("vertices", [])
            off = _offset(shape)
            if len(verts) >= 3:
                pts = [pt(v[0] + off[0], v[1] + off[1]) for v in verts]
                pygame.draw.polygon(thumb, FILL, pts)
                pygame.draw.polygon(thumb, STROKE, pts, 1)
        return thumb
    except Exception:
        return None
