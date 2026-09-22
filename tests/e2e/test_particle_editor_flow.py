"""E2E flow tests for the particle editor: whole user journeys.

Each test reads as something a user does start to finish. Coordinates,
rect lookups, and synthetic events live in harness.py - never here.
"""

import json

import pygame
import pytest

pytestmark = pytest.mark.e2e


def test_full_authoring_pass(driver, tmp_path):
    (driver.load("Blank").set("spawn_rate", 99).save())
    assert not driver.dirty
    target = tmp_path / "particles" / "custom.particles.json"
    assert target.is_file()

    driver.editor.export_node = tmp_path / "node_out.json"
    driver.set("spawn_rate", 40).save()
    payload = json.loads((tmp_path / "node_out.json").read_text())
    assert payload["name"] == "Blank"
    assert payload["config"]["spawn_rate"] == 40

    driver.set("spawn_rate", 7).revert()
    assert not driver.dirty
    assert driver.working["spawn_rate"] == 40

    driver.open_library("custom")
    assert driver.thumb_names == ["Blank"]
    driver.load("Blank")
    assert not driver.dirty


def test_preset_switch_lock_matrix(driver):
    driver.set("gravity_x", 50)
    assert driver.dirty
    before = dict(driver.working)

    driver.editor._load_named_blocking_dirty("Snow")
    assert driver.working == before
    assert driver.loaded_name == "Campfire"
    assert len(driver.toasts) == 1
    assert driver.toasts[0].variant == "warning"

    driver.editor._switch_library(driver.editor.lib_choice.value)
    assert len(driver.toasts) == 2

    driver.editor._load_named_blocking_dirty("Campfire")
    assert len(driver.toasts) == 2  # same name is always allowed

    driver.revert()
    driver.editor._load_named_blocking_dirty("Snow")
    assert driver.loaded_name == "Snow"
    assert not driver.dirty


def test_wheel_focus_gate(driver):
    """Wheel over a slider scrolls unless that slider was clicked (focused)."""
    ed = driver.editor

    def wheel_at(pos, ticks):
        driver._move(pos)
        ed.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=ticks))

    def track_center():
        return ed.controls["spawn_rate"]._track_rect.center

    v0 = driver.working["spawn_rate"]
    wheel_at(track_center(), -3)  # unfocused: scrolls, value kept
    assert driver.working["spawn_rate"] == v0
    assert ed.sidebar_scroll > 0

    driver._click_at(ed.controls["spawn_rate"]._track_rect)  # focus
    v0 = driver.working["spawn_rate"]  # click itself may move the slider
    s1 = ed.sidebar_scroll
    wheel_at(track_center(), 1)
    assert driver.working["spawn_rate"] != v0  # focused: value moves
    assert ed.sidebar_scroll == s1  # scroll blocked

    driver._click_at(ed.r_canvas)  # defocus
    v1 = driver.working["spawn_rate"]
    wheel_at(track_center(), -3)
    assert driver.working["spawn_rate"] == v1
    assert ed.sidebar_scroll > s1


def test_toolbar_overflow_journey(driver):
    rects = [driver.editor.lib_choice.rect, driver.editor.name_field.rect] + [
        b.rect for b in driver.editor._toolbar_buttons
    ]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert not rects[i].colliderect(rects[j])
    assert driver.editor.lib_choice._dd.rect.right <= driver.editor.name_field.rect.x

    driver.resize(640, 600)  # below the 800px production minimum: collapse contract
    hidden = {e.label for e in driver.editor._toolbar.hidden if e.kind == "widget"}
    assert {"Save", "Revert", "Blank"} <= hidden
    assert driver.editor._overflow_btn is not None
    driver.click_overflow_row("Revert")
    assert not driver.dirty

    driver.open_overflow_popup().draw()
    assert driver.editor._context_menu.is_open

    driver.resize(1180, 760)
    assert driver.editor._toolbar.hidden == []
    assert driver.editor._overflow_btn is None


def test_scroll_journeys(driver):
    bar = driver.editor._strip_bar
    assert bar.max_scroll > 0
    driver.drag_strip_to_end()
    assert driver.editor.strip_scroll == pytest.approx(bar.max_scroll)

    side = driver.editor._side_bar
    assert side.max_scroll > 0
    before = driver.editor.sidebar_scroll
    driver.wheel_sidebar()
    assert driver.editor.sidebar_scroll > before

    driver.draw()  # bars + thumbs paint without error


def test_small_library_hides_strip_bar(tmp_path, monkeypatch):
    from plugins.particle_editor.editor import ParticleEditor
    from plugins.particle_editor.models import ParticleLibrary, ParticleSystemEntry
    from plugins.particle_editor.presets import get_preset_config

    lib = ParticleLibrary(
        systems=[ParticleSystemEntry(name="Solo", config=get_preset_config("Blank"))]
    )
    editor = ParticleEditor(pygame.Rect(0, 0, 1180, 760), lib, None, tmp_path)
    assert editor._strip_bar.max_scroll == 0
    editor.draw(pygame.Surface((1180, 760)))


def test_mode_gating_and_contract(driver):
    assert "burst_count" not in driver.visible_keys
    assert "@fieldbox" not in driver.visible_keys

    driver.set("mode", "burst")
    assert "burst_count" in driver.visible_keys
    assert "timing.burst_interval" in driver.visible_keys
    assert "@fieldbox" not in driver.visible_keys

    driver.set("mode", "field")
    assert "burst_count" not in driver.visible_keys
    for key in ("@fieldbox", "coverage", "field_quality", "ground_bias"):
        assert key in driver.visible_keys
    assert driver.working["wrap"] is True
    assert driver.working["spawn_rate"] == 0
    assert driver.working["emission_shape"] == "rect"
    assert driver.working["alpha_fade"] == "none"

    driver.undo()
    assert driver.working["mode"] == "continuous"


def test_viewer_dispatch_journey(viewer_driver):
    vd = viewer_driver.draw()
    vd.click_button("toggle_visibility")
    assert vd.node.properties.get("_hidden") is True
    vd.click_button("toggle_visibility")
    assert "_hidden" not in vd.node.properties

    vd.click_button("open_editor").click_button("reload_editor")
    assert vd.fake.launched == [vd.node.node_id]
    assert vd.fake.reload_calls == [vd.node.node_id]

    vd.node.properties["spawn_rate"] = 31
    vd.refresh().draw()
    assert vd.preset_selected() == "Campfire (modified)"


def test_undo_redo_journey(driver):
    driver.set("gravity_x", 40)
    assert driver.working["gravity_x"] == 40
    driver.undo()
    assert driver.working["gravity_x"] == 0
    driver.redo()
    assert driver.working["gravity_x"] == 40

    driver.set("timing.start_delay", 2.0)
    assert driver.editor.sim.count == 0  # reset tier cleared + clock zeroed
    driver.undo()
    assert driver.working["timing"]["start_delay"] == 0.0


def test_field_fill_and_link_journey(driver):
    driver.load("Mist Bed")
    assert driver.count == 79
    driver.fill()
    assert driver.count == 79

    driver.working["wrap"] = False
    driver.fill()
    assert len(driver.toasts) == 1
    assert driver.toasts[0].variant == "warning"
    assert driver.count > 0  # soft: still fills

    driver.load("Campfire").link_on()
    driver.working["start_color_r"] = 10
    driver.working["start_color_g"] = 20
    driver.working["start_color_b"] = 30
    alpha_before = driver.working["end_color_a"]
    driver.editor.color_picker.sync_from_config(driver.working)
    driver.update()
    assert driver.working["end_color_r"] == 0
    assert driver.working["end_color_g"] == 10
    assert driver.working["end_color_b"] == 20
    assert driver.working["end_color_a"] == alpha_before


def test_strip_renders_every_preset(driver):
    from plugins.particle_editor.presets import PRESETS, get_preset_config

    assert len(PRESETS) == 19
    for preset in PRESETS:
        name = str(preset["name"])
        driver.load(name)
        driver.update(90)
        assert driver.count > 0, name
    assert all(s.count > 0 for _, s in driver.editor._thumb_sims)


def test_status_reports_clock(driver):
    driver.set("timing.start_delay", 1.0)
    assert driver.editor.sim.status_text().startswith("delay")
    driver.draw()


def test_draw_and_boot_smoke(driver, tmp_path):
    driver.update(10).draw()
    driver.resize(800, 600)
    assert driver.editor.r_canvas.width > driver.editor.r_sidebar.width
    driver.draw()

    from plugins.particle_editor.standalone import main

    main(
        [
            "--frames",
            "5",
            "--window-size",
            "800x600",
            "--data-root",
            str(tmp_path),
        ]
    )
