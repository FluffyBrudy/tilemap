# UI Base Architecture Reference

A reference implementation of reusable UI patterns - not everything needs this, adapt where it makes sense.

---

## Core Concept

The UI system uses a **box model** (similar to CSS) for consistent layout:
- **margin** - outer spacing
- **border** - border width
- **padding** - inner spacing from border
- **content** - actual content area

```
┌─────────────────────────────────────┐
│ margin                              │
│   ┌───────────────────────────────┐  │
│   │    border                  │  │
│   │   ┌─────────────────┐     │  │
│   │   │   padding     │     │  │
│   │   │  ┌─────────┐ │     │  │
│   │   │  │ content │ │     │  │
│   │   │  └─────────┘ │     │  │
│   │   │              │     │  │
│   │   └─────────────────┘     │  │
│   │                         │  │
│   └───────────────────────────┘  │
└─────────────────────────────────────┘
```

---

## Key Abstractions

### 1. UIOptions - Declarative Configuration

```python
from ttypes.index_type import UIOptions

# Example: progress bar options
options: UIOptions = {
    "width": 250,
    "height": 24,
    "border_width": 2,
    "border_radius": 6,
    "padding_x": 2,
    "padding_y": 2,
    "margin_x": 0,
    "margin_y": 0,
    "border_color": (40, 44, 52, 255),
    "background": (33, 37, 43, 255),
    "fill_color": (255, 255, 255, 255),
}
```

Benefits:
- All styling in one place
- Easy theming
- Clear defaults
- Type-checkable

### 2. Box Model - Layout Computation

The `generate_box_model()` function computes all layout values:

```python
from ttypes.index_type import BoxModel, BoxModelResult

def generate_box_model(model: BoxModel) -> BoxModelResult:
    # Returns computed values:
    # - left, top (content position relative to origin)
    # - offset_x, offset_y (for positioning on screen)
    # - full_width, full_height (total size)
    # - content_width, content_height (inner area)
```

### 3. UIBase - Base Class

Foundation class providing:
- `box_model` - computed layout
- `local_surface` - off-screen render surface
- `colors` - extracted from options
- `border` - border config
- `add_plugin()` - extend rendering
- `draw_base()` - render background/border
- `render()` - draw to screen

```python
from ui.base.uibase import UIBase

class MyWidget(UIBase):
    def __init__(self, options: UIOptions):
        super().__init__(options)
        self.add_plugin(self.draw_content)
    
    def draw_content(self, surface):
        # Custom rendering
        pass
```

---

## Usage Examples

### Simple: ProgressBar

```python
class ProgressBarUI(UIBase):
    def __init__(self, **overrides):
        options = {**PROGRESSBAR_DEFAULTS, **overrides}
        super().__init__(options)
        self.interpolation = SimpleInterpolation(speed=0.05)
    
    def render(self, screen, pos_offset=(0, 0)):
        self.draw_base()
        # Draw fill based on interpolated value
        fill_width = int(self.box_model["content_width"] * self.interpolation.current)
        pygame.draw.rect(self.local_surface, self.colors["fill"], ...)
        screen.blit(self.local_surface, pos_offset)
```

### Complex: CooldownOverlay

Uses plugins for extensibility:
- `add_plugin(self.generate_overlay_surf)` - cooldown arc
- `add_plugin(self.display_icon)` - skill icon

---

## Integration Notes

### When to Use This Pattern

- **Good for:** Complex widgets with multiple rendering layers
- **Good for:** Components needing consistent theming
- **Maybe skip for:** Simple one-off widgets
- **Maybe skip for:** Tight performance requirements

### How to Adapt to This Project

This project has existing patterns:
- `theme.py` with COLORS, SHAPE, FONTS
- `draw_utils.py` with draw_panel, draw_button
- Consistent pygame-ce usage

**Recommendation:** Consider integrating box_model concept into existing draw_utils rather than full UIBase class.

---

## File Structure

```
refactor/reference/uibase/
├── README.md           # This file
├── uibase_core.py       # Types (UIOptions, BoxModel) + generate_box_model()
├── uibase.py           # UIBase base class
└── examples.py        # ProgressBarUI, CooldownOverlay, Dropdown examples
```

---

## See Also

- `scan_results.md` - Analysis of existing UI components in project
- `refactor/context.md` - Why we're doing this refactor
- `src/widgets/ui/` - Actual project UI components