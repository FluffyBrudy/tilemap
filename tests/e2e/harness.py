"""Surface drivers for e2e flow tests: the POM equivalent.

Coordinates, rect lookups, and synthetic-event plumbing live here and
only here. Tests read as user journeys; nothing outside this module
computes a widget rect or patches the mouse.

Every action returns ``self`` so journeys chain; assertions stay in the
test bodies against the exposed state properties.
"""

from __future__ import annotations

import pygame
from pygame import Rect

from plugins.particle_editor.editor import ParticleEditor
from plugins.particle_editor.models import builtin_library, builtin_library_path
from plugins.particle_editor.presets import get_preset_config
from plugins.particle_editor.sim import FIXED_DT


class ParticleEditorDriver:
    def __init__(self, editor: ParticleEditor, monkeypatch):
        self.editor = editor
        self.screen = pygame.Surface((editor.rect.w, editor.rect.h))
        self._mp = monkeypatch

    @classmethod
    def blank(cls, tmp_path, monkeypatch, name="Campfire", w=1180, h=760):
        library, _ = builtin_library()
        editor = ParticleEditor(
            pygame.Rect(0, 0, w, h), library, builtin_library_path(), tmp_path
        )
        editor.load_entry(name, get_preset_config(name))
        return cls(editor, monkeypatch)

    # -- actions (all chain) -------------------------------------------------

    def _move(self, pos):
        self._mp.setattr(pygame.mouse, "get_pos", lambda: pos)
        return pos

    def _click_at(self, rect):
        pos = self._move((rect.centerx, rect.centery))
        self.editor.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)
        )
        self.editor.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos)
        )
        return self

    def load(self, name):
        self.editor.load_entry(name, get_preset_config(name))
        return self

    def set(self, key, value):
        self.editor.controls[key].set_value(value)
        self.editor._apply_change(key)
        self.editor._commit(key)
        return self

    def save(self):
        self.editor.save()
        return self

    def revert(self):
        self.editor.revert()
        return self

    def undo(self):
        self.editor.undo()
        return self

    def redo(self):
        self.editor.redo()
        return self

    def click_save(self):
        return self._click_at(self.editor._btn_save.rect)

    def click_revert(self):
        return self._click_at(self.editor._btn_revert.rect)

    def click_blank(self):
        return self._click_at(self.editor._btn_blank.rect)

    def click_preset(self, name):
        for thumb_name, trect in self.editor._thumb_rects:
            if thumb_name == name:
                return self._click_at(trect)
        raise AssertionError(f"preset thumb not visible: {name}")

    def click_overflow_row(self, label):
        rows = {r.label: r.on_activate for r in self.editor._toolbar.overflow_rows()}
        rows[label]()
        return self

    def open_overflow_popup(self):
        btn = self.editor._overflow_btn
        assert btn is not None, "no overflow button at this width"
        return self._click_at(btn.rect)

    def drag_strip_to_end(self):
        bar = self.editor._strip_bar
        thumb = bar._thumb_rect()
        self._move((thumb.centerx, thumb.centery))
        self.editor.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=thumb.center)
        )
        far = (thumb.centerx + bar.max_scroll, thumb.centery)
        self._move(far)
        self.editor.handle_event(
            pygame.event.Event(
                pygame.MOUSEMOTION,
                pos=far,
                rel=(int(bar.max_scroll), 0),
                buttons=(1, 0, 0),
            )
        )
        self.editor.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(0, 0))
        )
        return self

    def wheel_sidebar(self, ticks=-3):
        bar = self.editor._side_bar
        self._move((bar.rect.centerx, bar.rect.centery))
        bar.handle_event(
            pygame.event.Event(
                pygame.MOUSEMOTION,
                pos=bar.rect.center,
                rel=(0, 0),
                buttons=(0, 0, 0),
            )
        )
        self.editor.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=ticks))
        return self

    def open_library(self, label):
        self.editor._switch_library(label)
        return self

    def fill(self):
        self.editor._do_fill()
        return self

    def link_on(self):
        self.editor._link_toggle.value = True
        return self

    def resize(self, w, h):
        self.editor.set_rect(pygame.Rect(0, 0, w, h))
        self.screen = pygame.Surface((w, h))
        return self

    def update(self, steps=1):
        for _ in range(steps):
            self.editor.update(FIXED_DT)
        return self

    def draw(self):
        self.editor.draw(self.screen)
        return self

    # -- state -----------------------------------------------------------------

    @property
    def count(self):
        return self.editor.sim.count

    @property
    def dirty(self):
        return self.editor.is_dirty()

    @property
    def message(self):
        return self.editor.message

    @property
    def working(self):
        return self.editor.working

    @property
    def toasts(self):
        return self.editor.toasts._toasts

    @property
    def loaded_name(self):
        return self.editor.loaded_name

    @property
    def thumb_names(self):
        return [n for n, _ in self.editor._thumb_sims]

    @property
    def visible_keys(self):
        return [k for _, ks in self.editor._visible_sections() for k in ks]


class NodeViewerDriver:
    """Driver for the in-editor particle node panel (viewer)."""

    def __init__(self, viewer, fake_editor, monkeypatch):
        self.viewer = viewer
        self.fake = fake_editor
        self._mp = monkeypatch
        self.screen = pygame.Surface((1280, 800))

    @property
    def node(self):
        return self.fake.node_manager.get_active_node()

    def draw(self):
        self.viewer.draw(self.screen)
        return self

    def click_button(self, action):
        buttons = {a: r for r, a in self.viewer._buttons()}
        rect = buttons[action]
        pos = (rect.centerx, rect.centery)
        self._mp.setattr(pygame.mouse, "get_pos", lambda: pos)
        self.viewer.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)
        )
        return self

    def refresh(self):
        self.viewer._preset_owner = None
        return self

    def preset_selected(self):
        return self.viewer._preset_dd.selected if self.viewer._preset_dd else None
