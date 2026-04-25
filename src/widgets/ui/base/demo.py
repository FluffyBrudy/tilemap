#!/usr/bin/env python3
"""
UI Base Components Interactive Demo

Run: cd src && python3 widgets/ui/base/demo.py
"""
import sys
import os

sys.path.insert(0, "/Users/upstem/Documents/fluffyrudy/project/tilemap-packages/tilemap/src")

import pygame
from pygame import Rect, Surface

from widgets.ui.base import (
    NumericInput,
    ButtonBase,
    ToggleButton,
    DropdownBase,
    DropdownItem,
    create_simple_options,
)
from widgets.ui.theme import COLORS, FONTS


class DemoApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((700, 500))
        pygame.display.set_caption("UI Base Components Demo")
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Create components at fixed positions
        self.btn_pos = (50, 50)
        self.toggle_pos = (200, 50)
        self.input_pos = (50, 120)
        self.dropdown_pos = (50, 180)
        
        self.btn = ButtonBase(
            create_simple_options(120, 35, bg_color=COLORS.accent, border_radius=6),
            label="Click Me",
            on_click=self._on_button_click,
        )
        
        self.num_input = NumericInput(
            create_simple_options(150, 32),
            placeholder="Enter number",
        )
        
        self.toggle = ToggleButton(
            create_simple_options(100, 35),
            label="Toggle",
        )
        
        self.dropdown = DropdownBase(
            create_simple_options(160, 32),
            items=[
                DropdownItem("Option 1", "opt1"),
                DropdownItem("Option 2", "opt2"),
                DropdownItem("Option 3", "opt3"),
            ],
        )
        
        self.last_click = "None"
    
    def _on_button_click(self):
        self.last_click = "Button CLICKED!"
    
    def run(self):
        while self.running:
            self._handle_events()
            self._render()
            self.clock.tick(60)
        pygame.quit()
    
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
            
            # Button event
            mouse_pos = pygame.mouse.get_pos()
            if event.type == pygame.MOUSEBUTTONDOWN:
                # Check button 
                btn_rect = Rect(self.btn_pos[0], self.btn_pos[1], 120, 35)
                if btn_rect.collidepoint(mouse_pos):
                    self.last_click = "Button CLICKED!"
                
                # Toggle
                toggle_rect = Rect(self.toggle_pos[0], self.toggle_pos[1], 100, 35)
                if toggle_rect.collidepoint(mouse_pos):
                    self.toggle.is_toggled = not self.toggle.is_toggled
                    self.last_click = f"Toggle {'ON' if self.toggle.is_toggled else 'OFF'}"
                
                # Dropdown
                dd_rect = Rect(self.dropdown_pos[0], self.dropdown_pos[1], 160, 32)
                if dd_rect.collidepoint(mouse_pos):
                    self.dropdown.is_open = not self.dropdown.is_open
                    self.last_click = f"Dropdown toggled"
            
            # Numeric input focus
            input_rect = Rect(self.input_pos[0], self.input_pos[1], 150, 32)
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.num_input.set_focus(input_rect.collidepoint(mouse_pos))
            
            # Pass keyboard to input
            if self.num_input.is_focused and event.type == pygame.KEYDOWN:
                self.num_input.handle_event(event)
                self.last_click = f"Input: {self.num_input.get_value()}"
    
    def _render(self):
        self.screen.fill(COLORS.bg)
        
        # Title
        font = FONTS.get_bold_font(24)
        title = font.render("UI Base Components Demo", True, COLORS.text)
        self.screen.blit(title, (20, 15))
        
        # Button
        self.btn.render(self.screen, self.btn_pos)
        font_sm = FONTS.get_font(14)
        self.screen.blit(font_sm.render("Button", True, COLORS.text_dim), (180, 58))
        
        # Toggle
        self.toggle.render(self.screen, self.toggle_pos)
        self.screen.blit(font_sm.render("Toggle", True, COLORS.text_dim), (310, 58))
        
        # Input
        self.num_input.rect = Rect(self.input_pos[0], self.input_pos[1], 150, 32)
        self.num_input.draw(self.screen)
        self.screen.blit(font_sm.render("Numeric Input", True, COLORS.text_dim), (210, 128))
        
        # Dropdown
        self.dropdown.rect = Rect(self.dropdown_pos[0], self.dropdown_pos[1], 160, 32)
        self.dropdown.draw(self.screen)
        self.screen.blit(font_sm.render("Dropdown", True, COLORS.text_dim), (220, 188))
        
        # Last action
        font_val = FONTS.get_mono_font(14)
        self.screen.blit(font_val.render(f"Action: {self.last_click}", True, COLORS.accent), (50, 280))
        
        # Instructions
        font_instr = FONTS.get_font(12)
        self.screen.blit(
            font_instr.render("ESC to quit | Click button/toggle | Type in input | Click dropdown", True, COLORS.text_muted),
            (20, 450)
        )
        
        # Border
        pygame.draw.rect(self.screen, COLORS.border, Rect(30, 40, 640, 380), 1)
        
        pygame.display.flip()


if __name__ == "__main__":
    DemoApp().run()