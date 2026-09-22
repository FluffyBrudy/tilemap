from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pygame import Rect


@dataclass
class ToolbarEntry:
    kind: str  # "widget" | "sep"
    group: str
    priority: int
    width: int = 0
    widget: object | None = None
    right: bool = False
    collapsible: bool = True
    label: str = ""
    on_activate: Callable[[], None] | None = None
    overflow_entries: list[tuple[str, Callable[[], None]]] | None = None


@dataclass
class OverflowRow:
    label: str
    on_activate: Callable[[], None]


class ToolbarLayout:
    def __init__(self, gap: int = 4, sep_w: int = 10, margin: int = 6):
        self.gap = gap
        self.sep_w = sep_w
        self.margin = margin
        self.entries: list[ToolbarEntry] = []
        self.separators: list[tuple[int, int]] = []
        self.hidden: list[ToolbarEntry] = []
        self.row = Rect(0, 0, 0, 0)

    def clear(self) -> None:
        self.entries.clear()
        self.separators.clear()
        self.hidden.clear()

    def add_widget(
        self,
        widget: object,
        width: int,
        *,
        group: str,
        priority: int,
        right: bool = False,
        collapsible: bool = True,
        label: str = "",
        on_activate: Callable[[], None] | None = None,
    ) -> ToolbarEntry:
        entry = ToolbarEntry(
            kind="widget",
            group=group,
            priority=priority,
            width=max(0, int(width)),
            widget=widget,
            right=right,
            collapsible=collapsible,
            label=label,
            on_activate=on_activate,
        )
        self.entries.append(entry)
        return entry

    def add_segmented(
        self,
        widget: object,
        width: int,
        *,
        group: str,
        priority: int,
        overflow_entries: list[tuple[str, Callable[[], None]]] | None = None,
        label: str = "",
    ) -> ToolbarEntry:
        entry = self.add_widget(
            widget,
            width,
            group=group,
            priority=priority,
            label=label or group,
        )
        entry.overflow_entries = list(overflow_entries or [])
        return entry

    def add_separator(self, *, group: str, priority: int) -> ToolbarEntry:
        entry = ToolbarEntry(kind="sep", group=group, priority=priority, width=self.sep_w)
        self.entries.append(entry)
        return entry

    def overflow_rows(self) -> list[OverflowRow]:
        rows: list[OverflowRow] = []
        for entry in self.hidden:
            if entry.kind != "widget":
                continue
            if entry.overflow_entries:
                rows.extend(OverflowRow(label, cb) for label, cb in entry.overflow_entries)
            elif entry.on_activate is not None:
                rows.append(OverflowRow(entry.label or entry.group, entry.on_activate))
        return rows

    def reflow(self, row: Rect, row_y: int, height: int) -> Rect | None:
        """Assign rects; returns the overflow-button rect, or None if clean.

        `row` is the full toolbar row (x/width matter); widgets are placed
        at `row_y` with `height`. Collapsed widgets get `visible = False`.
        """
        self.row = Rect(row)
        self.separators = []
        self.hidden = []

        left = [e for e in self.entries if not e.right]
        right = [e for e in self.entries if e.kind == "widget" and e.right]

        # right block first: left flow must never run underneath it
        right_total = sum(e.width for e in right) + self.gap * max(0, len(right) - 1)
        right_start = row.right - self.margin - right_total
        x = right_start
        for entry in right:
            self._place(entry, x, row_y, height)
            x += entry.width + self.gap

        limit = right_start - self.gap
        start = row.x + self.margin
        collapsed = self._collapse_groups(left, start, limit, overflow_slot=height + self.gap)
        self.hide(collapsed)
        collapsed_ids = {id(e) for e in collapsed}

        # placement: separators emit only between two visible widgets
        cursor = start
        pending_sep_x: int | None = None
        prev_widget = False
        for entry in left:
            if id(entry) in collapsed_ids:
                continue
            if entry.kind == "sep":
                if prev_widget:
                    pending_sep_x = cursor
                    cursor += self.sep_w
                continue
            if pending_sep_x is not None:
                self.separators.append((pending_sep_x + self.sep_w // 2, row_y + height // 2))
                pending_sep_x = None
            self._place(entry, cursor, row_y, height)
            cursor += entry.width + self.gap
            prev_widget = True
        if pending_sep_x is not None:
            cursor -= self.sep_w  # trailing separator draws nothing

        self.hidden = collapsed
        if not collapsed:
            return None
        return Rect(cursor, row_y, height, height)

    def _flow_width(self, entries: list[ToolbarEntry], hidden: set[int]) -> int:
        return sum(entry.width + self.gap for entry in entries if id(entry) not in hidden)

    def _collapse_groups(
        self, left: list[ToolbarEntry], start: int, limit: int, overflow_slot: int
    ) -> list[ToolbarEntry]:
        """Whole-group collapse, lowest priority first, until the flow fits.

        Once anything collapses, an overflow button slot is reserved too.
        """
        hidden: set[int] = set()
        groups: dict[str, list[ToolbarEntry]] = {}
        for entry in left:
            groups.setdefault(entry.group, []).append(entry)
        order = sorted(groups, key=lambda g: min(e.priority for e in groups[g]))

        def collapsible_groups() -> list[str]:
            return [g for g in order if any(id(e) not in hidden and e.collapsible for e in groups[g])]

        def fits() -> bool:
            need = self._flow_width(left, hidden)
            if hidden:
                need += overflow_slot
            return start + need <= limit + self.gap

        while not fits():
            remaining = collapsible_groups()
            if not remaining:
                break
            for entry in groups[remaining[0]]:
                hidden.add(id(entry))
        return [e for e in left if id(e) in hidden]

    @staticmethod
    def _place(entry: ToolbarEntry, x: int, row_y: int, height: int) -> None:
        widget = entry.widget
        if widget is not None:
            rect = getattr(widget, "rect", None)
            if rect is not None:
                rect.x = int(x)
                rect.y = int(row_y)
                rect.w = int(entry.width)
                rect.h = int(height)
            try:
                widget.visible = True  # type: ignore[attr-defined]
            except (AttributeError, TypeError):
                pass

    def hide(self, entries: list[ToolbarEntry]) -> None:
        for entry in entries:
            widget = entry.widget
            if widget is not None:
                try:
                    widget.visible = False  # type: ignore[attr-defined]
                except (AttributeError, TypeError):
                    pass
