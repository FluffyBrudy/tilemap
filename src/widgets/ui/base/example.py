"""
Example: UI Base Components Usage

Demonstrates how to use the UI base components from widgets/ui/base/
"""
import pygame
from pygame import Rect, Surface

# Initialize pygame
pygame.init()
screen = pygame.display.set_mode((600, 400))
pygame.display.set_caption("UI Base Components Demo")

# Import UI bases
from widgets.ui.base import (
    UIOptions,
    UIBase,
    InputBase,
    NumericInput,
    SuggestionInput,
    ButtonBase,
    IconButton,
    ToggleButton,
    DropdownBase,
    DropdownItem,
    RadioGroup,
    create_simple_options,
)
from widgets.ui.theme import COLORS


# ============================================================================
# Example 1: Simple Button
# ============================================================================
def demo_button():
    """Demo a simple button."""
    print("\n--- Button Demo ---")
    
    options = create_simple_options(
        width=120,
        height=35,
        bg_color=COLORS.accent,
        border_width=0,
        border_radius=4,
    )
    
    def on_click():
        print("Button clicked!")
    
    button = ButtonBase(options, label="Click Me", on_click=on_click)
    
    print(f"Button: {button}")
    print(f"  rect: {button.rect}")
    print(f"  fullsize: {button.fullsize}")
    print(f"  label: {button.label}")
    
    return button


# ============================================================================
# Example 2: Numeric Input
# ============================================================================
def demo_numeric_input():
    """Demo a numeric input field."""
    print("\n--- Numeric Input Demo ---")
    
    options = create_simple_options(
        width=150,
        height=30,
        bg_color=COLORS.panel,
        border_color=COLORS.border_soft,
        border_width=1,
        border_radius=4,
    )
    
    numeric_input = NumericInput(options, placeholder="Enter number")
    
    print(f"NumericInput: {numeric_input}")
    print(f"  placeholder: {numeric_input.placeholder}")
    print(f"  value: {numeric_input.get_value()}")
    
    # Simulate typing
    numeric_input._add_char("1")
    numeric_input._add_char("2")
    numeric_input._add_char("3")
    
    print(f"  after typing '123': {numeric_input.get_value()}")
    
    return numeric_input


# ============================================================================
# Example 3: Dropdown
# ============================================================================
def demo_dropdown():
    """Demo a dropdown."""
    print("\n--- Dropdown Demo ---")
    
    options = create_simple_options(
        width=180,
        height=30,
        bg_color=COLORS.panel,
        border_color=COLORS.border_soft,
        border_width=1,
        border_radius=4,
    )
    
    items = [
        DropdownItem("Option 1", "opt1"),
        DropdownItem("Option 2", "opt2"),
        DropdownItem("Option 3", "opt3"),
    ]
    
    dropdown = DropdownBase(options, items=items)
    
    print(f"Dropdown: {dropdown}")
    print(f"  items: {len(dropdown.items)}")
    print(f"  selected: {dropdown.get_selected()}")
    
    return dropdown


# ============================================================================
# Example 4: Custom Widget using UIBase
# ============================================================================
class ProgressBar(UIBase):
    """Simple progress bar using UIBase."""
    
    def __init__(self, options: UIOptions, value: float = 0.0):
        super().__init__(options)
        self.value = value
        self.colors["fill"] = COLORS.accent
    
    def set_value(self, value: float) -> None:
        self.value = max(0.0, min(1.0, value))
    
    def draw_content(self, surface: Surface) -> None:
        if self.value > 0:
            fill_width = int(self.box_model["content_width"] * self.value)
            
            pygame.draw.rect(
                surface,
                self.colors["fill"],
                (
                    self.box_model["left"],
                    self.box_model["top"],
                    fill_width,
                    self.box_model["content_height"],
                ),
            )


def demo_progress_bar():
    """Demo a progress bar."""
    print("\n--- Progress Bar Demo ---")
    
    options = create_simple_options(
        width=200,
        height=20,
        bg_color=COLORS.panel_alt,
        border_color=COLORS.border_soft,
        border_width=1,
        border_radius=4,
    )
    
    progress = ProgressBar(options, value=0.5)
    
    print(f"ProgressBar: {progress}")
    print(f"  value: {progress.value}")
    print(f"  fullsize: {progress.fullsize}")
    
    progress.set_value(0.75)
    print(f"  after set_value(0.75): {progress.value}")
    
    return progress


# ============================================================================
# Run all demos
# ============================================================================
def main():
    print("=" * 50)
    print("UI Base Components Demo")
    print("=" * 50)
    
    # Run all demos
    demo_button()
    demo_numeric_input()
    demo_dropdown()
    demo_progress_bar()
    
    print("\n" + "=" * 50)
    print("All demos completed!")
    print("=" * 50)
    
    # Quick rendering test
    print("\nRendering test...")
    
    # Create a test surface
    test_surface = Surface((600, 400))
    test_surface.fill(COLORS.bg)
    
    # Test button rendering
    button = demo_button()
    button.render(test_surface, (50, 50))
    
    # Test numeric input
    numeric = demo_numeric_input()
    numeric.set_focus(True)
    numeric.is_focused = True  # Force focus for demo
    numeric.draw(test_surface)
    
    # Test dropdown
    dropdown = demo_dropdown()
    dropdown.draw(test_surface)
    
    # Test progress bar
    progress = demo_progress_bar()
    progress.render(test_surface, (50, 250))
    
    print("Rendering test complete!")
    
    # Save screenshot (optional)
    # pygame.image.save(test_surface, "ui_demo.png")
    
    print("\nDone! Components work correctly.")


if __name__ == "__main__":
    main()