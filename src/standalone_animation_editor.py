#!/usr/bin/env python3
"""
Standalone Animation Editor
Independent tool for creating sprite animations from images/spritesheets.
Can be launched from tilemap editor or run standalone.
"""
import pygame
import sys
import json
from pathlib import Path
from typing import List, Optional, Tuple, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from widgets.filemanager import FileManager

pygame.init()

class AnimationEditor:
    def __init__(self, animation_file: Optional[Path] = None):
        self.screen = pygame.display.set_mode((1000, 700), pygame.RESIZABLE)
        pygame.display.set_caption("Animation Editor")
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Animation data
        self.animation_name = "untitled"
        self.frames: List[pygame.Surface] = []
        self.frame_durations: List[int] = []  # milliseconds per frame
        self.current_frame = 0
        self.preview_timer = 0
        self.is_playing = False
        self.loop = True
        
        # Source images
        self.source_images: List[Tuple[Path, pygame.Surface]] = []
        
        # UI state
        self.font = pygame.font.SysFont("Arial", 14)
        self.font_large = pygame.font.SysFont("Arial", 18, bold=True)
        self.default_duration = 200  # ms
        
        # File manager state
        self.file_manager: Optional[FileManager] = None
        
        # Spritesheet dialog state
        self.show_spritesheet_dialog = False
        self.pending_image_path: Optional[Path] = None
        self.pending_image_surface: Optional[pygame.Surface] = None
        self.spritesheet_width_input = ""
        self.spritesheet_height_input = ""
        self.spritesheet_input_active = "width"  # "width" or "height"
        
        # Animation file
        self.animation_file = animation_file
        if animation_file and animation_file.exists():
            self.load_animation(animation_file)
    
    def open_file_manager_load_animation(self):
        """Open file manager to load animation."""
        w, h = 600, 400
        screen_w, screen_h = self.screen.get_size()
        rect = pygame.Rect((screen_w - w) // 2, (screen_h - h) // 2, w, h)
        
        self.file_manager = FileManager(
            rect=rect,
            initial_dir=Path.cwd(),
            allowed_exts=[".json"],
            on_select=self.on_animation_file_selected,
            mode="open",
            on_cancel=self.close_file_manager
        )
    
    def open_file_manager_save_animation(self):
        """Open file manager to save animation."""
        w, h = 600, 400
        screen_w, screen_h = self.screen.get_size()
        rect = pygame.Rect((screen_w - w) // 2, (screen_h - h) // 2, w, h)
        
        default_name = f"{self.animation_name}.json" if self.animation_name else "animation.json"
        
        self.file_manager = FileManager(
            rect=rect,
            initial_dir=Path.cwd(),
            allowed_exts=[".json"],
            on_save=self.on_animation_save_selected,
            mode="save",
            default_name=default_name,
            on_cancel=self.close_file_manager
        )
    
    def open_file_manager_import_images(self):
        """Open file manager to import images."""
        w, h = 600, 400
        screen_w, screen_h = self.screen.get_size()
        rect = pygame.Rect((screen_w - w) // 2, (screen_h - h) // 2, w, h)
        
        self.file_manager = FileManager(
            rect=rect,
            initial_dir=Path.cwd(),
            allowed_exts=[".png", ".jpg", ".jpeg"],
            on_select=self.on_images_selected,
            mode="open",
            on_cancel=self.close_file_manager,
            multi_select=True
        )
    
    def close_file_manager(self):
        """Close file manager."""
        self.file_manager = None
    
    def on_animation_file_selected(self, path):
        """Callback when animation file is selected."""
        self.close_file_manager()
        self.load_animation(path)
    
    def on_animation_save_selected(self, path):
        """Callback when save location is selected."""
        self.close_file_manager()
        self.save_animation(path)
    
    def on_images_selected(self, paths):
        """Callback when images are selected."""
        self.close_file_manager()
        
        # Handle single or multiple paths
        if isinstance(paths, Path):
            paths = [paths]
        
        # If single image, ask if it's a spritesheet
        if len(paths) == 1:
            path = paths[0]
            try:
                surf = pygame.image.load(path).convert_alpha()
                self.pending_image_path = path
                self.pending_image_surface = surf
                self.show_spritesheet_dialog = True
                self.spritesheet_width_input = ""
                self.spritesheet_height_input = ""
                self.spritesheet_input_active = "width"
            except Exception as e:
                print(f"Error loading image: {e}")
        else:
            # Multiple images, add as individual frames
            for path in paths:
                self.add_image_as_frame(path)
    
    def add_image_as_frame(self, path: Path):
        """Add image as a single frame."""
        try:
            surf = pygame.image.load(path).convert_alpha()
            self.source_images.append((path, surf))
            self.frames.append(surf)
            self.frame_durations.append(self.default_duration)
            print(f"Added frame: {path.name} ({surf.get_width()}x{surf.get_height()})")
        except Exception as e:
            print(f"Error loading image: {e}")
    
    def add_spritesheet(self, path: Path, surf: pygame.Surface, tile_w: int, tile_h: int):
        """Split spritesheet into frames."""
        img_w, img_h = surf.get_size()
        cols = img_w // tile_w
        rows = img_h // tile_h
        
        count = 0
        for row in range(rows):
            for col in range(cols):
                x = col * tile_w
                y = row * tile_h
                
                rect = pygame.Rect(x, y, tile_w, tile_h)
                if surf.get_rect().contains(rect):
                    frame = surf.subsurface(rect).copy()
                    self.frames.append(frame)
                    self.frame_durations.append(self.default_duration)
                    count += 1
        
        self.source_images.append((path, surf))
        print(f"Added spritesheet: {path.name} ({count} frames, {tile_w}x{tile_h} each)")
    
    def handle_spritesheet_dialog(self, event):
        """Handle events for spritesheet dialog."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # Cancel - add as single frame
                self.add_image_as_frame(self.pending_image_path)
                self.show_spritesheet_dialog = False
                self.pending_image_path = None
                self.pending_image_surface = None
            
            elif event.key == pygame.K_RETURN:
                # Confirm
                if self.spritesheet_input_active == "width" and self.spritesheet_width_input:
                    # Move to height input
                    self.spritesheet_input_active = "height"
                elif self.spritesheet_input_active == "height" and self.spritesheet_height_input:
                    # Process spritesheet
                    try:
                        tile_w = int(self.spritesheet_width_input)
                        tile_h = int(self.spritesheet_height_input)
                        
                        if tile_w > 0 and tile_h > 0:
                            self.add_spritesheet(self.pending_image_path, self.pending_image_surface, tile_w, tile_h)
                        else:
                            print("Invalid dimensions")
                            self.add_image_as_frame(self.pending_image_path)
                    except ValueError:
                        print("Invalid number format")
                        self.add_image_as_frame(self.pending_image_path)
                    
                    self.show_spritesheet_dialog = False
                    self.pending_image_path = None
                    self.pending_image_surface = None
            
            elif event.key == pygame.K_TAB:
                # Switch between inputs
                if self.spritesheet_input_active == "width":
                    self.spritesheet_input_active = "height"
                else:
                    self.spritesheet_input_active = "width"
            
            elif event.key == pygame.K_BACKSPACE:
                # Delete character
                if self.spritesheet_input_active == "width":
                    self.spritesheet_width_input = self.spritesheet_width_input[:-1]
                else:
                    self.spritesheet_height_input = self.spritesheet_height_input[:-1]
            
            elif event.unicode.isdigit():
                # Add digit
                if self.spritesheet_input_active == "width":
                    self.spritesheet_width_input += event.unicode
                else:
                    self.spritesheet_height_input += event.unicode
    
    def load_animation(self, path: Path):
        """Load animation from JSON file."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            self.animation_name = data.get("name", "untitled")
            self.loop = data.get("loop", True)
            self.default_duration = data.get("default_duration", 200)
            
            # Load frames from image paths
            self.frames = []
            self.frame_durations = []
            
            for frame_data in data.get("frames", []):
                img_path = Path(frame_data["image"])
                if not img_path.is_absolute():
                    img_path = path.parent / img_path
                
                if img_path.exists():
                    surf = pygame.image.load(img_path).convert_alpha()
                    # If frame has crop data, crop it
                    if "crop" in frame_data:
                        crop = frame_data["crop"]
                        rect = pygame.Rect(crop["x"], crop["y"], crop["w"], crop["h"])
                        surf = surf.subsurface(rect).copy()
                    
                    self.frames.append(surf)
                    self.frame_durations.append(frame_data.get("duration_ms", self.default_duration))
            
            self.animation_file = path
            print(f"Loaded animation: {self.animation_name} ({len(self.frames)} frames)")
            
        except Exception as e:
            print(f"Error loading animation: {e}")
    
    def save_animation(self, path: Path):
        """Save animation to JSON file."""
        if not self.frames:
            print("No frames to save")
            return
        
        # Save frames as separate images or reference existing ones
        frames_data = []
        for i, (frame, duration) in enumerate(zip(self.frames, self.frame_durations)):
            # For now, save frame info (in real implementation, save images)
            frame_data = {
                "image": f"frame_{i}.png",  # Placeholder
                "duration_ms": duration
            }
            frames_data.append(frame_data)
        
        data = {
            "name": self.animation_name,
            "loop": self.loop,
            "default_duration": self.default_duration,
            "frames": frames_data
        }
        
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved animation: {path}")
            self.animation_file = path
        except Exception as e:
            print(f"Error saving animation: {e}")
    
    def add_image(self, path: Path):
        """Add image as single frame (legacy method, kept for compatibility)."""
        self.add_image_as_frame(path)
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            # Spritesheet dialog takes priority
            if self.show_spritesheet_dialog:
                self.handle_spritesheet_dialog(event)
                continue
            
            # File manager takes priority
            if self.file_manager:
                self.file_manager.handle_event(event)
                continue
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                
                elif event.key == pygame.K_SPACE:
                    self.is_playing = not self.is_playing
                    self.preview_timer = 0
                
                elif event.key == pygame.K_s and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
                    self.open_file_manager_save_animation()
                
                elif event.key == pygame.K_o and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
                    self.open_file_manager_load_animation()
                
                elif event.key == pygame.K_i and (event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
                    self.open_file_manager_import_images()
    
    def update(self):
        if self.is_playing and self.frames:
            self.preview_timer += self.clock.get_time()
            current_duration = self.frame_durations[self.current_frame] if self.current_frame < len(self.frame_durations) else self.default_duration
            
            if self.preview_timer >= current_duration:
                self.preview_timer = 0
                self.current_frame = (self.current_frame + 1) % len(self.frames)
    
    def draw(self):
        self.screen.fill((40, 40, 40))
        
        # Title
        title = self.font_large.render(f"Animation Editor - {self.animation_name}", True, (255, 255, 255))
        self.screen.blit(title, (20, 20))
        
        # Preview area
        if self.frames:
            frame = self.frames[self.current_frame]
            # Scale up for preview
            scale = min(4, min(400 // frame.get_width(), 400 // frame.get_height()))
            scaled = pygame.transform.scale(frame, (frame.get_width() * scale, frame.get_height() * scale))
            
            preview_x = self.screen.get_width() // 2 - scaled.get_width() // 2
            preview_y = 100
            self.screen.blit(scaled, (preview_x, preview_y))
            
            # Frame info
            info = self.font.render(f"Frame {self.current_frame + 1}/{len(self.frames)} - {self.frame_durations[self.current_frame] if self.current_frame < len(self.frame_durations) else self.default_duration}ms", True, (200, 200, 200))
            self.screen.blit(info, (preview_x, preview_y + scaled.get_height() + 10))
        
        # Instructions
        y = self.screen.get_height() - 200
        instructions = [
            "Controls:",
            "SPACE - Play/Pause",
            "Cmd+O - Open animation",
            "Cmd+S - Save animation",
            "Cmd+I - Import images",
            "ESC - Exit",
            "",
            f"Status: {'Playing' if self.is_playing else 'Paused'}",
            f"Frames: {len(self.frames)}"
        ]
        
        for line in instructions:
            text = self.font.render(line, True, (200, 200, 200))
            self.screen.blit(text, (20, y))
            y += 20
        
        # Draw spritesheet dialog if active
        if self.show_spritesheet_dialog:
            self.draw_spritesheet_dialog()
        
        # Draw file manager if open
        if self.file_manager:
            overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self.screen.blit(overlay, (0, 0))
            self.file_manager.draw(self.screen)
        
        pygame.display.flip()
    
    def draw_spritesheet_dialog(self):
        """Draw spritesheet configuration dialog."""
        # Overlay
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        
        # Dialog box
        dialog_w, dialog_h = 500, 350
        dialog_x = (self.screen.get_width() - dialog_w) // 2
        dialog_y = (self.screen.get_height() - dialog_h) // 2
        dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_w, dialog_h)
        
        pygame.draw.rect(self.screen, (50, 50, 50), dialog_rect)
        pygame.draw.rect(self.screen, (100, 100, 100), dialog_rect, 2)
        
        # Title
        title = self.font_large.render("Import Image", True, (255, 255, 255))
        self.screen.blit(title, (dialog_x + 20, dialog_y + 20))
        
        # Image info
        if self.pending_image_surface:
            w, h = self.pending_image_surface.get_size()
            info = self.font.render(f"Image size: {w}x{h} pixels", True, (200, 200, 200))
            self.screen.blit(info, (dialog_x + 20, dialog_y + 60))
        
        # Instructions
        y = dialog_y + 100
        instructions = [
            "Is this a spritesheet?",
            "",
            "Enter tile dimensions (width x height):",
            "Or press ESC to import as single frame"
        ]
        
        for line in instructions:
            text = self.font.render(line, True, (220, 220, 220))
            self.screen.blit(text, (dialog_x + 20, y))
            y += 25
        
        # Width input
        y = dialog_y + 220
        width_label = self.font.render("Tile Width:", True, (200, 200, 200))
        self.screen.blit(width_label, (dialog_x + 20, y))
        
        width_input_rect = pygame.Rect(dialog_x + 150, y - 5, 100, 30)
        color = (80, 120, 180) if self.spritesheet_input_active == "width" else (60, 60, 60)
        pygame.draw.rect(self.screen, color, width_input_rect)
        pygame.draw.rect(self.screen, (150, 150, 150), width_input_rect, 2)
        
        width_text = self.font.render(self.spritesheet_width_input, True, (255, 255, 255))
        self.screen.blit(width_text, (width_input_rect.x + 10, width_input_rect.y + 8))
        
        # Height input
        y += 40
        height_label = self.font.render("Tile Height:", True, (200, 200, 200))
        self.screen.blit(height_label, (dialog_x + 20, y))
        
        height_input_rect = pygame.Rect(dialog_x + 150, y - 5, 100, 30)
        color = (80, 120, 180) if self.spritesheet_input_active == "height" else (60, 60, 60)
        pygame.draw.rect(self.screen, color, height_input_rect)
        pygame.draw.rect(self.screen, (150, 150, 150), height_input_rect, 2)
        
        height_text = self.font.render(self.spritesheet_height_input, True, (255, 255, 255))
        self.screen.blit(height_text, (height_input_rect.x + 10, height_input_rect.y + 8))
        
        # Hints
        y += 50
        hints = [
            "TAB - Switch between inputs",
            "ENTER - Confirm (after entering both values)",
            "ESC - Import as single frame"
        ]
        
        for hint in hints:
            text = self.font.render(hint, True, (150, 150, 150))
            self.screen.blit(text, (dialog_x + 20, y))
            y += 20
    
    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()


if __name__ == "__main__":
    animation_file = None
    if len(sys.argv) > 1:
        animation_file = Path(sys.argv[1])
    
    editor = AnimationEditor(animation_file)
    editor.run()
