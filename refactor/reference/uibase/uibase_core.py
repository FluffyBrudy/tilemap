"""
Core Types for UI Base Architecture

Based on patterns from refactor reference.
These types define the declarative UI configuration system.
"""
from typing import Any, Dict, Optional, Protocol, Tuple, TypedDict, Union
from pygame import Rect, Surface, Vector2
from pygame.typing import ColorLike, RectLike


# Position type - accepts multiple formats
TPosType = Union[Tuple[int, int], Tuple[float, float], Vector2]


# Box Model Input (before computation)
class BoxModel(TypedDict, total=False):
    """Input box model - all fields optional with defaults."""
    margin_x: int
    margin_y: int
    padding_x: int
    padding_y: int
    width: int
    height: int
    border_width: int


# Box Model Result (after computation)
class BoxModelResult(TypedDict, total=True):
    """Computed box model with all final values."""
    left: int          # Content position relative to origin
    top: int
    offset_x: int     # For positioning on screen
    offset_y: int
    full_width: int    # Total size including margin + border + padding
    full_height: int
    content_width: int  # Inner content area
    content_height: int


# Full UI Options (extends BoxModel with styling)
class UIOptions(BoxModel, total=False):
    """Declarative UI configuration."""
    border_radius: int
    border_color: ColorLike
    background: ColorLike
    fill_color: ColorLike
    # Add other optional styling as needed


def set_box_model_defaults(model: BoxModel) -> BoxModel:
    """Set defaults for any missing BoxModel fields."""
    return {
        "width": model.get("width", 0),
        "height": model.get("height", 0),
        "padding_x": model.get("padding_x", 0),
        "padding_y": model.get("padding_y", 0),
        "border_width": model.get("border_width", 0),
        "margin_x": model.get("margin_x", 0),
        "margin_y": model.get("margin_y", 0),
    }


def generate_box_model(model: BoxModel) -> BoxModelResult:
    """
    Compute complete box model from input.
    
    This is the core layout function - computes content area
    and positioning from margin/border/padding/spacing.
    
    Returns:
        BoxModelResult with all computed values
    """
    assert isinstance(model, dict)
    
    model = set_box_model_defaults(model)
    
    # Validate all values are non-negative integers
    for key, value in model.items():
        assert isinstance(value, int) and value >= 0, f"{key} must be non-negative int, got {value}"
    
    # Calculate inner content area
    inner_x = 2 * (model["padding_x"] + model["border_width"])
    inner_y = 2 * (model["padding_y"] + model["border_width"])
    
    return {
        "left": model["padding_x"] + model["border_width"],
        "top": model["padding_y"] + model["border_width"],
        "offset_x": model["margin_x"],
        "offset_y": model["margin_y"],
        "full_width": model["width"],
        "full_height": model["height"],
        "content_width": model["width"] - inner_x,
        "content_height": model["height"] - inner_y,
    }


# Protocols for type checking
class Rectable(Protocol):
    """Protocol for things that have a rect."""
    def rect(self) -> Rect: ...


class Renderable(Protocol):
    """Protocol for renderable UI elements."""
    def render(self, screen: Surface, pos_offset: TPosType) -> None: ...
    def update(self) -> None: ...


class VectorPos(Protocol):
    """Protocol for things with a Vector2 position."""
    pos: Vector2