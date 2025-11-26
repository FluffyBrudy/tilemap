import pygame
import os
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple


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

        self.refresh_items()

    def refresh_items(self):
        self.items.clear()
        self.scroll_y = 0
        self.selected_index = -1

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

    def go_up(self):
        if self.current_path.parent != self.current_path:
            self.current_path = self.current_path.parent
            self.refresh_items()

    def navigate_to(self, path: Path):
        if path.is_dir():
            self.current_path = path
            self.refresh_items()

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse_pos = pygame.mouse.get_pos()

        lx = mouse_pos[0] - self.rect.x
        ly = mouse_pos[1] - self.rect.y

        content_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.y + self.header_height,
            self.rect.width - self.sidebar_width,
            self.rect.height - self.header_height - self.footer_height,
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
                rel_y = ly - self.header_height + self.scroll_y
                idx = int(rel_y // self.item_height)
                if 0 <= idx < len(self.items):
                    self.hover_index = idx
                else:
                    self.hover_index = -1
            else:
                self.hover_index = -1

            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if lx < self.sidebar_width:
                    self._handle_sidebar_click(ly)
                    return True

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
                            self.navigate_to(item.path)
                        else:
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
            ("Desktop", Path.home() / "Desktop"),
            ("Downloads", Path.home() / "Downloads"),
            ("Root", Path(os.path.abspath(os.sep))),
        ]

        start_y = 10
        gap = 40

        for i, (name, path) in enumerate(shortcuts):
            btn_y = start_y + (i * gap)
            if btn_y <= ly <= btn_y + 30:
                if path.exists():
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

        content_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.y + self.header_height,
            self.rect.width - self.sidebar_width,
            self.rect.height - self.header_height - self.footer_height,
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
        shortcuts = ["Home", "Desktop", "Downloads", "Root"]
        start_y = rect.y + 10
        gap = 40

        for i, name in enumerate(shortcuts):
            y = start_y + (i * gap)

            mx, my = pygame.mouse.get_pos()
            btn_rect = pygame.Rect(rect.x + 5, y, rect.width - 10, 30)

            col = (
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
