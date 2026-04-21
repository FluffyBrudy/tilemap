#!/usr/bin/env python3
"""
Standalone Image Viewer with Grid/Spritesheet Support
Opens images in a scrollable window with optional grid overlay for spritesheets.
"""

import pygame
import sys
from pathlib import Path
from typing import Tuple


class ImageViewer:
    """Standalone image viewer with scrolling and grid support."""
    
    def __init__(self, image_path: Path, window_size: Tuple[int, int] = (1000, 700)):
        """Initialize the image viewer.
        
        Args:
            image_path: Path to the image file
            window_size: Window dimensions (width, height)
        """
        pygame.init()
        
        self.image_path = image_path
        self.window_size = window_size
        self.screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
        pygame.display.set_caption(f"Image Viewer - {image_path.name}")
        
        # Load image
        try:
            self.original_image = pygame.image.load(str(image_path))
            self.image_size = self.original_image.get_size()
        except pygame.error as e:
            print(f"Error loading image: {e}")
            sys.exit(1)
        
        # Zoom and scroll state
        self.zoom_level = 1.0
        self.scroll_x = 0
        self.scroll_y = 0
        self.scroll_speed = 30
        
        # Grid state
        self.grid_enabled = False
        self.grid_rows = 1
        self.grid_cols = 1
        self.show_grid_overlay = False
        
        # UI state
        self.rows_input_text = "1"
        self.cols_input_text = "1"
        self.rows_input_focused = False
        self.cols_input_focused = False
        self.show_controls = True
        
        # Fonts
        self.font_main = pygame.font.SysFont("Arial", 14)
        self.font_bold = pygame.font.SysFont("Arial", 14, bold=True)
        self.font_small = pygame.font.SysFont("Arial", 11)
        
        # Colors
        self.colors = {
            "bg": (30, 32, 36),
            "panel": (40, 42, 46),
            "border": (60, 62, 65),
            "text": (230, 230, 230),
            "text_dim": (140, 140, 140),
            "accent": (80, 120, 200),
            "grid": (255, 0, 0),
            "input_bg": (50, 52, 56),
            "button": (60, 80, 120),
            "button_hover": (80, 100, 140),
        }
        
        self.running = True
        self.clock = pygame.time.Clock()
        
        # Calculate initial display
        self.update_display_image()
    
    def update_display_image(self):
        """Update the displayed image based on zoom level."""
        if self.zoom_level != 1.0:
            new_size = (
                int(self.image_size[0] * self.zoom_level),
                int(self.image_size[1] * self.zoom_level)
            )
            self.display_image = pygame.transform.smoothscale(self.original_image, new_size)
        else:
            self.display_image = self.original_image
    
    def handle_events(self):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.VIDEORESIZE:
                self.window_size = (event.w, event.h)
                self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
            
            elif event.type == pygame.KEYDOWN:
                # Handle input focus
                if self.rows_input_focused or self.cols_input_focused:
                    self.handle_input_keydown(event)
                else:
                    self.handle_general_keydown(event)
            
            elif event.type == pygame.MOUSEWHEEL:
                # Scroll with mouse wheel
                keys = pygame.key.get_pressed()
                if keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
                    # Zoom with Ctrl + wheel
                    old_zoom = self.zoom_level
                    self.zoom_level *= 1.1 if event.y > 0 else 0.9
                    self.zoom_level = max(0.1, min(self.zoom_level, 10.0))
                    if old_zoom != self.zoom_level:
                        self.update_display_image()
                else:
                    # Scroll vertically
                    self.scroll_y -= event.y * self.scroll_speed
                    self.clamp_scroll()
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.handle_mouse_click(event.pos)
    
    def handle_general_keydown(self, event):
        """Handle keyboard input when not in text input mode."""
        if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
            self.running = False
        elif event.key == pygame.K_h:
            self.show_controls = not self.show_controls
        elif event.key == pygame.K_g:
            self.show_grid_overlay = not self.show_grid_overlay
        elif event.key == pygame.K_r:
            # Reset zoom and scroll
            self.zoom_level = 1.0
            self.scroll_x = 0
            self.scroll_y = 0
            self.update_display_image()
        elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
            self.zoom_level *= 1.2
            self.zoom_level = min(self.zoom_level, 10.0)
            self.update_display_image()
        elif event.key == pygame.K_MINUS:
            self.zoom_level *= 0.8
            self.zoom_level = max(self.zoom_level, 0.1)
            self.update_display_image()
    
    def handle_input_keydown(self, event):
        """Handle keyboard input for text fields."""
        if event.key == pygame.K_ESCAPE:
            self.rows_input_focused = False
            self.cols_input_focused = False
        elif event.key == pygame.K_RETURN:
            self.apply_grid()
            self.rows_input_focused = False
            self.cols_input_focused = False
        elif event.key == pygame.K_TAB:
            if self.rows_input_focused:
                self.rows_input_focused = False
                self.cols_input_focused = True
            else:
                self.cols_input_focused = False
                self.rows_input_focused = True
        elif event.key == pygame.K_BACKSPACE:
            if self.rows_input_focused:
                self.rows_input_text = self.rows_input_text[:-1]
            elif self.cols_input_focused:
                self.cols_input_text = self.cols_input_text[:-1]
        elif event.unicode and event.unicode.isdigit():
            if self.rows_input_focused and len(self.rows_input_text) < 4:
                self.rows_input_text += event.unicode
            elif self.cols_input_focused and len(self.cols_input_text) < 4:
                self.cols_input_text += event.unicode
    
    def apply_grid(self):
        """Apply grid settings from input fields."""
        try:
            rows = int(self.rows_input_text) if self.rows_input_text else 1
            cols = int(self.cols_input_text) if self.cols_input_text else 1
            self.grid_rows = max(1, min(rows, 100))
            self.grid_cols = max(1, min(cols, 100))
            self.rows_input_text = str(self.grid_rows)
            self.cols_input_text = str(self.grid_cols)
            self.show_grid_overlay = True
        except ValueError:
            self.rows_input_text = str(self.grid_rows)
            self.cols_input_text = str(self.grid_cols)
    
    def handle_mouse_click(self, pos):
        """Handle mouse clicks."""
        # Check if clicking on input fields
        if hasattr(self, 'rows_input_rect') and self.rows_input_rect.collidepoint(pos):
            self.rows_input_focused = True
            self.cols_input_focused = False
        elif hasattr(self, 'cols_input_rect') and self.cols_input_rect.collidepoint(pos):
            self.cols_input_focused = True
            self.rows_input_focused = False
        elif hasattr(self, 'apply_button_rect') and self.apply_button_rect.collidepoint(pos):
            self.apply_grid()
        elif hasattr(self, 'toggle_grid_button_rect') and self.toggle_grid_button_rect.collidepoint(pos):
            self.show_grid_overlay = not self.show_grid_overlay
        else:
            self.rows_input_focused = False
            self.cols_input_focused = False
    
    def clamp_scroll(self):
        """Clamp scroll values to valid range."""
        display_size = self.display_image.get_size()
        max_scroll_x = max(0, display_size[0] - self.window_size[0])
        max_scroll_y = max(0, display_size[1] - self.window_size[1] + 100)  # +100 for controls
        
        self.scroll_x = max(0, min(self.scroll_x, max_scroll_x))
        self.scroll_y = max(0, min(self.scroll_y, max_scroll_y))
    
    def draw(self):
        """Draw the viewer."""
        self.screen.fill(self.colors["bg"])
        
        # Draw image
        image_rect = self.display_image.get_rect()
        image_rect.topleft = (-self.scroll_x, -self.scroll_y)
        self.screen.blit(self.display_image, image_rect)
        
        # Draw grid overlay if enabled
        if self.show_grid_overlay and (self.grid_rows > 1 or self.grid_cols > 1):
            self.draw_grid_overlay(image_rect)
        
        # Draw controls panel
        if self.show_controls:
            self.draw_controls()
        
        pygame.display.flip()
    
    def draw_grid_overlay(self, image_rect):
        """Draw grid lines over the image."""
        cell_width = self.display_image.get_width() / self.grid_cols
        cell_height = self.display_image.get_height() / self.grid_rows
        
        # Draw vertical lines
        for i in range(1, self.grid_cols):
            x = image_rect.left + int(i * cell_width)
            if 0 <= x < self.window_size[0]:
                pygame.draw.line(
                    self.screen,
                    self.colors["grid"],
                    (x, max(0, image_rect.top)),
                    (x, min(self.window_size[1], image_rect.bottom)),
                    2
                )
        
        # Draw horizontal lines
        for i in range(1, self.grid_rows):
            y = image_rect.top + int(i * cell_height)
            if 0 <= y < self.window_size[1]:
                pygame.draw.line(
                    self.screen,
                    self.colors["grid"],
                    (max(0, image_rect.left), y),
                    (min(self.window_size[0], image_rect.right), y),
                    2
                )
    
    def draw_controls(self):
        """Draw control panel at the bottom."""
        panel_height = 90
        panel_rect = pygame.Rect(0, self.window_size[1] - panel_height, self.window_size[0], panel_height)
        
        # Draw semi-transparent background
        panel_surface = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        panel_surface.fill((*self.colors["panel"], 230))
        self.screen.blit(panel_surface, panel_rect)
        
        # Draw border
        pygame.draw.line(self.screen, self.colors["border"], 
                        (0, panel_rect.top), (self.window_size[0], panel_rect.top), 2)
        
        y_pos = panel_rect.top + 10
        x_pos = 10
        
        # Image info
        info_text = f"{self.image_path.name} | {self.image_size[0]}×{self.image_size[1]} px | Zoom: {self.zoom_level:.1f}x"
        info_surf = self.font_main.render(info_text, True, self.colors["text"])
        self.screen.blit(info_surf, (x_pos, y_pos))
        
        y_pos += 25
        
        # Grid controls
        label = self.font_main.render("Grid:", True, self.colors["text"])
        self.screen.blit(label, (x_pos, y_pos + 4))
        x_pos += 50
        
        # Rows input
        self.rows_input_rect = pygame.Rect(x_pos, y_pos, 60, 24)
        border_color = self.colors["accent"] if self.rows_input_focused else self.colors["border"]
        pygame.draw.rect(self.screen, border_color, self.rows_input_rect, border_radius=4)
        pygame.draw.rect(self.screen, self.colors["input_bg"], self.rows_input_rect.inflate(-2, -2), border_radius=4)
        
        rows_text = self.rows_input_text
        if self.rows_input_focused and (pygame.time.get_ticks() // 500) % 2:
            rows_text += "|"
        rows_surf = self.font_main.render(rows_text, True, self.colors["text"])
        self.screen.blit(rows_surf, (self.rows_input_rect.x + 6, self.rows_input_rect.y + 4))
        
        x_pos += 70
        label = self.font_main.render("×", True, self.colors["text"])
        self.screen.blit(label, (x_pos, y_pos + 4))
        x_pos += 20
        
        # Cols input
        self.cols_input_rect = pygame.Rect(x_pos, y_pos, 60, 24)
        border_color = self.colors["accent"] if self.cols_input_focused else self.colors["border"]
        pygame.draw.rect(self.screen, border_color, self.cols_input_rect, border_radius=4)
        pygame.draw.rect(self.screen, self.colors["input_bg"], self.cols_input_rect.inflate(-2, -2), border_radius=4)
        
        cols_text = self.cols_input_text
        if self.cols_input_focused and (pygame.time.get_ticks() // 500) % 2:
            cols_text += "|"
        cols_surf = self.font_main.render(cols_text, True, self.colors["text"])
        self.screen.blit(cols_surf, (self.cols_input_rect.x + 6, self.cols_input_rect.y + 4))
        
        x_pos += 70
        
        # Apply button
        self.apply_button_rect = pygame.Rect(x_pos, y_pos, 60, 24)
        mouse_pos = pygame.mouse.get_pos()
        button_color = self.colors["button_hover"] if self.apply_button_rect.collidepoint(mouse_pos) else self.colors["button"]
        pygame.draw.rect(self.screen, button_color, self.apply_button_rect, border_radius=4)
        apply_text = self.font_main.render("Apply", True, self.colors["text"])
        text_rect = apply_text.get_rect(center=self.apply_button_rect.center)
        self.screen.blit(apply_text, text_rect)
        
        x_pos += 70
        
        # Toggle grid button
        self.toggle_grid_button_rect = pygame.Rect(x_pos, y_pos, 100, 24)
        button_color = self.colors["button_hover"] if self.toggle_grid_button_rect.collidepoint(mouse_pos) else self.colors["button"]
        pygame.draw.rect(self.screen, button_color, self.toggle_grid_button_rect, border_radius=4)
        toggle_text = self.font_main.render("Grid: ON" if self.show_grid_overlay else "Grid: OFF", True, self.colors["text"])
        text_rect = toggle_text.get_rect(center=self.toggle_grid_button_rect.center)
        self.screen.blit(toggle_text, text_rect)
        
        # Help text
        y_pos += 30
        help_text = "Controls: Arrow keys/Mouse wheel=Scroll | Ctrl+Wheel=Zoom | R=Reset | G=Toggle Grid | H=Hide Controls | Q/ESC=Quit"
        help_surf = self.font_small.render(help_text, True, self.colors["text_dim"])
        self.screen.blit(help_surf, (10, y_pos))
    
    def run(self):
        """Main loop."""
        while self.running:
            self.handle_events()
            
            # Handle arrow key scrolling
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]:
                self.scroll_x -= self.scroll_speed
            if keys[pygame.K_RIGHT]:
                self.scroll_x += self.scroll_speed
            if keys[pygame.K_UP]:
                self.scroll_y -= self.scroll_speed
            if keys[pygame.K_DOWN]:
                self.scroll_y += self.scroll_speed
            
            self.clamp_scroll()
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()


def main():
    """Entry point for standalone image viewer."""
    if len(sys.argv) < 2:
        print("Usage: python standalone_image_viewer.py <image_path>")
        sys.exit(1)
    
    image_path = Path(sys.argv[1])
    
    if not image_path.exists():
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)
    
    viewer = ImageViewer(image_path)
    viewer.run()


if __name__ == "__main__":
    main()
