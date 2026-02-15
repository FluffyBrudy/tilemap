import pygame
import os
import sys
import json
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from constants import INTELLISENSE_DEPTH, IGNORE_DIRS, BASE_PATH


COLORS = {
    "overlay": (0, 0, 0, 180),
    "bg": (30, 32, 36),
    "sidebar": (25, 27, 30),
    "header": (40, 42, 46),
    "border": (60, 62, 65),
    "text_main": (230, 230, 230),
    "text_dim": (140, 140, 140),
    "highlight": (50, 60, 80),
    "selected": (70, 90, 130),
    "accent": (80, 120, 200),
    "folder": (220, 180, 80),
    "file": (180, 180, 180),
    "image": (100, 180, 120),
}


class FileItem:
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.is_dir = path.is_dir()
        self.ext = path.suffix.lower()


class FileManager:
    def __init__(
        self,
        rect: pygame.Rect,
        initial_dir: Optional[Path] = None,
        allowed_exts: List[str] = [".png", ".jpg"],
        on_select: Callable[[Path], None] = lambda p: None,
        on_cancel: Callable[[], None] = lambda: None,
    ):
        self.rect = rect
        self.allowed_exts = allowed_exts
        self.on_select_callback = on_select
        self.on_cancel_callback = on_cancel

        self.current_path = initial_dir if initial_dir else Path.home()
        self.history: List[Path] = []
        self.items: List[FileItem] = []

        self.selected_index: int = -1
        self.scroll_y = 0
        self.scroll_speed = 30
        self.hover_index = -1
        self.double_click_timer = 0
        self.clicked_item_index = -1

        self.sidebar_width = 140
        self.header_height = 40
        self.footer_height = 50
        self.item_height = 30

        self.font_main = pygame.font.SysFont("Arial", 14)
        self.font_bold = pygame.font.SysFont("Arial", 14, bold=True)
        self.font_icon = pygame.font.SysFont("Consolas", 20)

        self.search_query = ""
        self.is_searching = False
        self.search_rect = pygame.Rect(
            self.rect.x + self.sidebar_width + 10,
            self.rect.y + self.header_height + 5,
            self.rect.width - self.sidebar_width - 20,
            25
        )
        self.search_header_height = 35
        self.is_search_focused = False
        
        self.recents_path = BASE_PATH / "data" / "recents.json"
        self.recents: List[Path] = self._load_recents()
        self.view_mode = "files"  # "files" or "recents"

        self.refresh_items()

    def refresh_items(self):
        self.items.clear()
        self.scroll_y = 0
        self.selected_index = -1

        if self.view_mode == "recents":
            for p in self.recents:
                if p.exists():
                    self.items.append(FileItem(p))
            return

        if self.search_query:
            self.is_searching = True
            # 1. Search files locally (current dir only)
            self._search_local_files(self.current_path, self.search_query)
            # 2. Search directories recursively
            self._recursive_search(self.current_path, self.search_query, INTELLISENSE_DEPTH)
            
            # Use a dict to avoid duplicates (same path might be found)
            unique_items = {str(item.path): item for item in self.items}
            self.items = sorted(unique_items.values(), key=lambda x: (not x.is_dir, x.name.lower()))
            return

        self.is_searching = False
        try:
            all_entries = list(self.current_path.iterdir())

            folders = sorted(
                [p for p in all_entries if p.is_dir()], key=lambda p: p.name.lower()
            )

            files = [
                p
                for p in all_entries
                if p.is_file() and p.suffix.lower() in self.allowed_exts
            ]
            files = sorted(files, key=lambda p: p.name.lower())

            for p in folders:
                self.items.append(FileItem(p))
            for p in files:
                self.items.append(FileItem(p))

        except PermissionError:
            print(f"Permission denied: {self.current_path}")
            self.go_up()

    def _search_local_files(self, path: Path, query: str):
        try:
            for p in path.iterdir():
                if p.name.startswith("."):
                    continue
                if p.is_file() and query.lower() in p.name.lower():
                    if p.suffix.lower() in self.allowed_exts:
                        self.items.append(FileItem(p))
                elif p.is_dir() and query.lower() in p.name.lower():
                    if p.name not in IGNORE_DIRS:
                        self.items.append(FileItem(p))
        except PermissionError:
            pass

    def _recursive_search(self, path: Path, query: str, depth: int):
        if depth < 0:
            return

        try:
            for p in path.iterdir():
                # Ignore hidden and system dirs
                if p.name.startswith("."):
                    continue
                
                if p.is_dir():
                    if p.name in IGNORE_DIRS:
                        continue
                        
                    # Add matching sub-directories (recursive discovery)
                    if query.lower() in p.name.lower():
                        self.items.append(FileItem(p))
                    
                    # Continue falling into subdirs
                    self._recursive_search(p, query, depth - 1)
        except (PermissionError, OSError, Exception):
            # Ignore /proc related errors and permission issues
            pass

    def _load_recents(self) -> List[Path]:
        if not self.recents_path.exists():
            return []
        try:
            with open(self.recents_path, "r") as f:
                data = json.load(f)
                return [Path(p) for p in data if Path(p).exists()]
        except:
            return []

    def _save_recents(self):
        try:
            if not self.recents_path.parent.exists():
                self.recents_path.parent.mkdir(parents=True)
            with open(self.recents_path, "w") as f:
                json.dump([str(p) for p in self.recents], f)
        except:
            pass

    def _add_to_recents(self, path: Path):
        if path in self.recents:
            self.recents.remove(path)
        self.recents.insert(0, path)
        self.recents = self.recents[:20]  # Keep last 20
        self._save_recents()

    def go_up(self):
        self.view_mode = "files"
        if self.current_path.parent != self.current_path:
            self.current_path = self.current_path.parent
            self.refresh_items()

    def navigate_to(self, path: Path, record_recent: bool = False):
        self.view_mode = "files"
        if path.is_dir():
            if record_recent:
                self._add_to_recents(path)
            self.current_path = path
            self.refresh_items()

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse_pos = pygame.mouse.get_pos()

        lx = mouse_pos[0] - self.rect.x
        ly = mouse_pos[1] - self.rect.y

        self.search_rect.x = self.rect.x + self.sidebar_width + 10
        self.search_rect.y = self.rect.y + self.header_height + 5

        content_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.y + self.header_height + self.search_header_height,
            self.rect.width - self.sidebar_width,
            self.rect.height - self.header_height - self.footer_height - self.search_header_height,
        )

        if event.type == pygame.MOUSEWHEEL:
            if content_rect.collidepoint(mouse_pos):
                max_scroll = max(
                    0, len(self.items) * self.item_height - content_rect.height
                )
                self.scroll_y = max(
                    0, min(self.scroll_y - (event.y * self.scroll_speed), max_scroll)
                )
                return True

        if event.type == pygame.MOUSEMOTION:
            if content_rect.collidepoint(mouse_pos):
                rel_y = ly - self.header_height - self.search_header_height + self.scroll_y
                idx = int(rel_y // self.item_height)
                if 0 <= idx < len(self.items):
                    self.hover_index = idx
                else:
                    self.hover_index = -1
            else:
                self.hover_index = -1

            return True

        if event.type == pygame.KEYDOWN and self.is_search_focused:
            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
            meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)
            if event.key == pygame.K_BACKSPACE:
                if ctrl_held or meta_held:
                    self.search_query = ""
                else:
                    self.search_query = self.search_query[:-1]
                self.refresh_items()
            elif event.key == pygame.K_ESCAPE:
                self.is_search_focused = False
            elif event.unicode and event.unicode.isprintable():
                self.search_query += event.unicode
                self.refresh_items()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if lx < self.sidebar_width:
                    self._handle_sidebar_click(ly)
                    return True

                if self.search_rect.collidepoint(mouse_pos):
                    self.is_search_focused = True
                    return True
                else:
                    self.is_search_focused = False

                if ly < self.header_height:
                    if lx < self.sidebar_width + 40:
                        self.go_up()
                    return True

                if ly > self.rect.height - self.footer_height:
                    self._handle_footer_click(lx)
                    return True

                if content_rect.collidepoint(mouse_pos) and self.hover_index != -1:
                    idx = self.hover_index
                    item = self.items[idx]

                    current_time = pygame.time.get_ticks()

                    if (
                        self.clicked_item_index == idx
                        and (current_time - self.double_click_timer) < 500
                    ):
                        if item.is_dir:
                            self.navigate_to(item.path, record_recent=True)
                        else:
                            self._add_to_recents(item.path)
                            self.on_select_callback(item.path)
                    else:
                        self.selected_index = idx
                        self.clicked_item_index = idx
                        self.double_click_timer = current_time

                    return True

        return True

    def _handle_sidebar_click(self, ly):
        shortcuts = [
            ("Home", Path.home()),
            ("Documents", Path.home() / "Documents"),
            ("Desktop", Path.home() / "Desktop"),
            ("Downloads", Path.home() / "Downloads"),
            ("Recents", None),
            ("Root", Path(os.path.abspath(os.sep))),
        ]

        start_y = 10
        gap = 40

        for i, (name, path) in enumerate(shortcuts):
            btn_y = start_y + (i * gap)
            if btn_y <= ly <= btn_y + 30:
                if name == "Recents":
                    self.view_mode = "recents"
                    self.refresh_items()
                elif path and path.exists():
                    self.navigate_to(path)
                return

    def _handle_footer_click(self, lx):
        btn_w = 80
        pad = 10
        cancel_x = self.rect.width - btn_w - pad
        open_x = cancel_x - btn_w - pad

        if cancel_x <= lx <= cancel_x + btn_w:
            self.on_cancel_callback()
        elif open_x <= lx <= open_x + btn_w:
            if self.selected_index != -1:
                item = self.items[self.selected_index]
                if not item.is_dir:
                    self._add_to_recents(item.path)
                    self.on_select_callback(item.path)

    def draw(self, screen: pygame.Surface):
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill(COLORS["overlay"])
        screen.blit(overlay, (0, 0))

        pygame.draw.rect(screen, COLORS["bg"], self.rect)
        pygame.draw.rect(screen, COLORS["border"], self.rect, 1)

        sidebar_rect = pygame.Rect(
            self.rect.x, self.rect.y, self.sidebar_width, self.rect.height
        )
        pygame.draw.rect(screen, COLORS["sidebar"], sidebar_rect)
        pygame.draw.line(
            screen,
            COLORS["border"],
            (sidebar_rect.right, sidebar_rect.top),
            (sidebar_rect.right, sidebar_rect.bottom),
        )

        self._draw_sidebar_items(screen, sidebar_rect)

        header_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.y,
            self.rect.width - self.sidebar_width,
            self.header_height,
        )
        pygame.draw.rect(screen, COLORS["header"], header_rect)
        pygame.draw.line(
            screen,
            COLORS["border"],
            (header_rect.left, header_rect.bottom),
            (header_rect.right, header_rect.bottom),
        )

        self._draw_header(screen, header_rect)

        # Draw Search Bar
        search_bg_rect = pygame.Rect(
            header_rect.left,
            header_rect.bottom,
            header_rect.width,
            self.search_header_height
        )
        pygame.draw.rect(screen, COLORS["bg"], search_bg_rect)
        
        self.search_rect.x = search_bg_rect.x + 10
        self.search_rect.y = search_bg_rect.y + 5
        self.search_rect.width = search_bg_rect.width - 20
        
        box_col = COLORS["selected"] if self.is_search_focused else COLORS["border"]
        pygame.draw.rect(screen, box_col, self.search_rect, border_radius=4)
        pygame.draw.rect(screen, COLORS["sidebar"], self.search_rect.inflate(-2, -2), border_radius=4)

        search_text = self.search_query
        if not search_text and not self.is_search_focused:
            search_text = "Search files..."
            search_col = COLORS["text_dim"]
        else:
            search_col = COLORS["text_main"]
            if self.is_search_focused and (pygame.time.get_ticks() // 500) % 2:
                search_text += "|"

        txt = self.font_main.render(search_text, True, search_col)
        screen.blit(txt, (self.search_rect.x + 8, self.search_rect.y + 4))

        content_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.y + self.header_height + self.search_header_height,
            self.rect.width - self.sidebar_width,
            self.rect.height - self.header_height - self.footer_height - self.search_header_height,
        )
        self._draw_file_list(screen, content_rect)

        footer_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.bottom - self.footer_height,
            content_rect.width,
            self.footer_height,
        )
        pygame.draw.rect(screen, COLORS["header"], footer_rect)
        pygame.draw.line(
            screen,
            COLORS["border"],
            (footer_rect.left, footer_rect.top),
            (footer_rect.right, footer_rect.top),
        )

        self._draw_footer(screen, footer_rect)

    def _draw_sidebar_items(self, screen, rect):
        shortcuts = ["Home", "Documents", "Desktop", "Downloads", "Recents", "Root"]
        start_y = rect.y + 10
        gap = 40

        for i, name in enumerate(shortcuts):
            y = start_y + (i * gap)

            mx, my = pygame.mouse.get_pos()
            btn_rect = pygame.Rect(rect.x + 5, y, rect.width - 10, 30)

            is_active = False
            if name == "Recents" and self.view_mode == "recents":
                is_active = True
            
            col = (
                COLORS["selected"] if is_active else
                COLORS["highlight"]
                if btn_rect.collidepoint(mx, my)
                else COLORS["sidebar"]
            )
            pygame.draw.rect(screen, col, btn_rect, border_radius=4)

            txt = self.font_bold.render(name, True, COLORS["text_main"])
            screen.blit(txt, (rect.x + 15, y + 7))

    def _draw_header(self, screen, rect):
        up_btn = pygame.Rect(rect.x + 5, rect.y + 5, 30, 30)
        self._draw_icon_arrow_up(
            screen, up_btn.centerx, up_btn.centery, COLORS["text_main"]
        )

        path_str = str(self.current_path)

        if len(path_str) > 50:
            path_str = "..." + path_str[-47:]

        txt = self.font_main.render(path_str, True, COLORS["text_dim"])
        screen.blit(txt, (rect.x + 45, rect.y + 12))

    def _draw_file_list(self, screen, rect):
        clip = screen.get_clip()
        screen.set_clip(rect)

        start_y = rect.y - self.scroll_y

        for i, item in enumerate(self.items):
            y = start_y + (i * self.item_height)

            if y + self.item_height < rect.y:
                continue
            if y > rect.bottom:
                break

            row_rect = pygame.Rect(rect.x, y, rect.width, self.item_height)

            if i == self.selected_index:
                pygame.draw.rect(screen, COLORS["selected"], row_rect)
            elif i == self.hover_index:
                pygame.draw.rect(screen, COLORS["highlight"], row_rect)

            icon_x = rect.x + 10
            icon_center_y = y + self.item_height // 2
            if item.is_dir:
                self._draw_icon_folder(screen, icon_x, icon_center_y - 8)
            elif item.ext in [".png", ".jpg", ".jpeg"]:
                self._draw_icon_image(screen, icon_x, icon_center_y - 8)
            else:
                self._draw_icon_file(screen, icon_x, icon_center_y - 8)

            col = (
                COLORS["text_main"] if i == self.selected_index else COLORS["text_main"]
            )
            txt = self.font_main.render(item.name, True, col)
            screen.blit(txt, (rect.x + 35, y + 7))

        screen.set_clip(clip)

        total_h = len(self.items) * self.item_height
        if total_h > rect.height:
            scroll_pct = self.scroll_y / (total_h - rect.height)
            bar_h = max(20, rect.height * (rect.height / total_h))
            bar_y = rect.y + scroll_pct * (rect.height - bar_h)

            bar_rect = pygame.Rect(rect.right - 6, bar_y, 4, bar_h)
            pygame.draw.rect(screen, COLORS["border"], bar_rect, border_radius=2)

    def _draw_footer(self, screen, rect):
        sel_txt = "No file selected"
        if self.selected_index != -1:
            sel_txt = self.items[self.selected_index].name

        txt_surf = self.font_main.render(sel_txt, True, COLORS["text_dim"])
        screen.blit(txt_surf, (rect.x + 10, rect.y + 17))

        btn_w, btn_h = 80, 30
        margin = 10

        def draw_btn(x, label, accent=False):
            r = pygame.Rect(x, rect.y + 10, btn_w, btn_h)
            bg = COLORS["accent"] if accent else COLORS["highlight"]

            mx, my = pygame.mouse.get_pos()
            if r.collidepoint(mx, my):
                bg = (min(bg[0] + 20, 255), min(bg[1] + 20, 255), min(bg[2] + 20, 255))

            pygame.draw.rect(screen, bg, r, border_radius=4)
            lbl = self.font_bold.render(label, True, COLORS["text_main"])
            lbl_r = lbl.get_rect(center=r.center)
            screen.blit(lbl, lbl_r)

        cancel_x = rect.right - btn_w - margin
        open_x = cancel_x - btn_w - margin

        draw_btn(cancel_x, "Cancel")
        draw_btn(open_x, "Open", accent=True)

    def _draw_icon_folder(self, surface, x, y):
        color = COLORS["folder"]

        pygame.draw.rect(surface, color, (x, y, 8, 4))

        pygame.draw.rect(surface, color, (x, y + 4, 18, 12))

    def _draw_icon_file(self, surface, x, y):
        color = COLORS["file"]

        pygame.draw.rect(surface, color, (x + 2, y, 14, 16))

        pygame.draw.polygon(
            surface, COLORS["bg"], [(x + 16, y), (x + 16, y + 5), (x + 11, y)]
        )

    def _draw_icon_image(self, surface, x, y):
        color = COLORS["image"]
        pygame.draw.rect(surface, color, (x + 1, y + 1, 16, 14))

        pygame.draw.polygon(
            surface, COLORS["bg"], [(x + 1, y + 15), (x + 6, y + 8), (x + 10, y + 15)]
        )
        pygame.draw.polygon(
            surface, COLORS["bg"], [(x + 8, y + 15), (x + 12, y + 6), (x + 17, y + 15)]
        )

    def _draw_icon_arrow_up(self, surface, cx, cy, color):
        points = [(cx, cy - 5), (cx - 5, cy + 2), (cx + 5, cy + 2)]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.rect(surface, color, (cx - 2, cy + 2, 4, 4))
