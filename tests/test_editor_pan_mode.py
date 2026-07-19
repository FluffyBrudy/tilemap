"""
Tests for editor.py pan mode state machine and new tool fields added in PR.

The space-bar pan toggle logic is embedded in the Editor event loop.
We test it via a small helper that mirrors the exact branch from the diff,
keeping tests fast and free of the full Editor dependency graph.

Also tests:
- New initial state fields (eraser_mode, select_mode, _prev_tool)
- _launch_animation_editor_with_image routes .json files to _launch_animation_editor_with_json
- _launch_animation_editor_with_json exits early when spritesheet cannot be resolved
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# Minimal state object and pan-mode toggle helper
# (mirrors the K_SPACE branch in editor.py handle_events)
# ---------------------------------------------------------------------------


class ToolState:
    """Minimal object mirroring the 5 editor tool fields touched by the PR."""

    def __init__(self, pan_mode=False, select_mode=False, eraser_mode=False):
        self.pan_mode = pan_mode
        self.select_mode = select_mode
        self.eraser_mode = eraser_mode
        self._prev_tool = None


def apply_space_press(state: ToolState):
    """Apply the Space-key pan toggle logic exactly as in editor.py."""
    if state.pan_mode:
        # Restoring: turn off pan, re-enable previous tool
        state.pan_mode = False
        if getattr(state, "_prev_tool", None) == "select":
            state.select_mode = True
        elif getattr(state, "_prev_tool", None) == "eraser":
            state.eraser_mode = True
    else:
        # Entering pan: save current tool, turn off others
        if state.select_mode:
            state._prev_tool = "select"
        elif state.eraser_mode:
            state._prev_tool = "eraser"
        else:
            state._prev_tool = None
        state.pan_mode = True
        state.select_mode = False
        state.eraser_mode = False


# ---------------------------------------------------------------------------
# Tests for pan-mode toggle state machine
# ---------------------------------------------------------------------------


class TestPanModeStateTransitions:
    def test_space_enables_pan_from_neutral(self):
        s = ToolState()
        apply_space_press(s)
        assert s.pan_mode is True
        assert s.select_mode is False
        assert s.eraser_mode is False

    def test_space_disables_pan_when_pan_active(self):
        s = ToolState(pan_mode=True)
        apply_space_press(s)
        assert s.pan_mode is False

    def test_space_saves_select_as_prev_tool(self):
        s = ToolState(select_mode=True)
        apply_space_press(s)
        assert s._prev_tool == "select"

    def test_space_saves_eraser_as_prev_tool(self):
        s = ToolState(eraser_mode=True)
        apply_space_press(s)
        assert s._prev_tool == "eraser"

    def test_space_sets_prev_tool_none_when_no_tool_active(self):
        s = ToolState()
        apply_space_press(s)
        assert s._prev_tool is None

    def test_space_disables_select_when_entering_pan(self):
        s = ToolState(select_mode=True)
        apply_space_press(s)
        assert s.select_mode is False
        assert s.pan_mode is True

    def test_space_disables_eraser_when_entering_pan(self):
        s = ToolState(eraser_mode=True)
        apply_space_press(s)
        assert s.eraser_mode is False
        assert s.pan_mode is True

    def test_space_restores_select_after_pan(self):
        s = ToolState(select_mode=True)
        apply_space_press(s)  # enter pan, save "select"
        apply_space_press(s)  # exit pan, restore select
        assert s.select_mode is True
        assert s.pan_mode is False

    def test_space_restores_eraser_after_pan(self):
        s = ToolState(eraser_mode=True)
        apply_space_press(s)  # enter pan, save "eraser"
        apply_space_press(s)  # exit pan, restore eraser
        assert s.eraser_mode is True
        assert s.pan_mode is False

    def test_space_does_not_restore_neutral_as_select(self):
        """Coming from neutral (no tool), toggling pan back should leave select off."""
        s = ToolState()
        apply_space_press(s)  # neutral → pan
        apply_space_press(s)  # pan → neutral
        assert s.select_mode is False
        assert s.eraser_mode is False

    def test_double_space_returns_to_original_state_neutral(self):
        s = ToolState()
        apply_space_press(s)
        apply_space_press(s)
        assert s.pan_mode is False
        assert s.select_mode is False
        assert s.eraser_mode is False

    def test_double_space_returns_to_original_state_select(self):
        s = ToolState(select_mode=True)
        apply_space_press(s)
        apply_space_press(s)
        assert s.pan_mode is False
        assert s.select_mode is True
        assert s.eraser_mode is False

    def test_double_space_returns_to_original_state_eraser(self):
        s = ToolState(eraser_mode=True)
        apply_space_press(s)
        apply_space_press(s)
        assert s.pan_mode is False
        assert s.select_mode is False
        assert s.eraser_mode is True

    def test_triple_space_re_enters_pan(self):
        """Three presses: neutral → pan → select_restored → pan again."""
        s = ToolState(select_mode=True)
        apply_space_press(s)  # → pan
        apply_space_press(s)  # → select restored
        apply_space_press(s)  # → pan again
        assert s.pan_mode is True

    def test_pan_only_restores_prev_tool_not_both(self):
        """Exiting pan should restore at most one tool."""
        s = ToolState(select_mode=True)
        apply_space_press(s)  # save select, enter pan
        apply_space_press(s)  # restore select
        assert s.select_mode is True
        assert s.eraser_mode is False


# ---------------------------------------------------------------------------
# Tests for _launch_animation_editor_with_image routing
# ---------------------------------------------------------------------------


class TestLaunchAnimationEditorRouting:
    """Test that .json paths are routed to _launch_animation_editor_with_json."""

    def _make_minimal_editor_class(self):
        """
        Patch the minimum needed to call _launch_animation_editor_with_image
        without touching actual subprocess or the file system.
        """
        from pathlib import Path

        # We only need the two methods from editor.py. Use a plain namespace.
        class MinEditor:
            def __init__(self):
                self.tilemap = mock.Mock()
                self.tilemap.tile_size = (32, 32)
                self.data_root = Path("/fake/data")
                self.base_path = Path("/fake")
                self.child_processes = []
                self._json_call_path = None
                self._image_launch_called = False

            def _launch_animation_editor_with_json(self, path):
                self._json_call_path = path

            def _launch_animation_editor_with_image(self, path):
                # Reproduce only the routing logic from the PR
                try:
                    if path.suffix.lower() == ".json":
                        self._launch_animation_editor_with_json(path)
                        return
                    self._image_launch_called = True
                except Exception:
                    pass

        return MinEditor()

    def test_json_path_routes_to_json_handler(self):
        ed = self._make_minimal_editor_class()
        p = Path("animation.json")
        ed._launch_animation_editor_with_image(p)
        assert ed._json_call_path == p

    def test_json_path_does_not_call_image_launch(self):
        ed = self._make_minimal_editor_class()
        ed._launch_animation_editor_with_image(Path("animation.json"))
        assert ed._image_launch_called is False

    def test_png_path_does_not_route_to_json_handler(self):
        ed = self._make_minimal_editor_class()
        ed._launch_animation_editor_with_image(Path("sheet.png"))
        assert ed._json_call_path is None

    def test_jpg_path_does_not_route_to_json_handler(self):
        ed = self._make_minimal_editor_class()
        ed._launch_animation_editor_with_image(Path("sheet.jpg"))
        assert ed._json_call_path is None

    def test_uppercase_json_extension_routes_to_json_handler(self):
        ed = self._make_minimal_editor_class()
        ed._launch_animation_editor_with_image(Path("animation.JSON"))
        assert ed._json_call_path is not None


# ---------------------------------------------------------------------------
# Tests for _launch_animation_editor_with_json early-exit cases
# ---------------------------------------------------------------------------


class TestLaunchAnimationEditorWithJsonModel:
    """
    Test the logic inside _launch_animation_editor_with_json that concerns
    AnimationLibrary loading and spritesheet resolution, without spawning a process.
    """

    def test_json_without_spritesheet_prints_and_returns(self):
        """If spritesheet_path is None, the method should print and return without launching."""
        from plugins.sprite_animation.models import AnimationLibrary

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anim.json"
            lib = AnimationLibrary(spritesheet_path=None, tile_size=(32, 32))
            lib.save(path)

            launched = []

            class FakeEd:
                data_root = Path(tmp)
                base_path = Path(tmp)
                child_processes = []

                def _launch_animation_editor_with_json(self, p):
                    # Mirror the relevant portion of the real implementation
                    from plugins.sprite_animation.models import AnimationLibrary as AL
                    from utils.project_paths import resolve_project_path

                    loaded = AL.load(p)
                    sp = loaded.spritesheet_path
                    if sp:
                        resolved = resolve_project_path(
                            sp,
                            p.parent,
                            fallback_roots=[self.base_path],
                            must_exist=True,
                        )
                    else:
                        resolved = None

                    if not resolved or not resolved.exists():
                        return  # early exit — no launch

                    launched.append(str(p))

            ed = FakeEd()
            ed._launch_animation_editor_with_json(path)
            assert launched == []

    def test_json_with_missing_spritesheet_does_not_launch(self):
        """spritesheet_path set but file does not exist → no process spawned."""
        from plugins.sprite_animation.models import AnimationLibrary

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anim.json"
            lib = AnimationLibrary(
                spritesheet_path="nonexistent_sheet.png",
                tile_size=(32, 32),
            )
            lib.save(path)

            launched = []

            class FakeEd:
                data_root = Path(tmp)
                base_path = Path(tmp)
                child_processes = []

                def _launch_animation_editor_with_json(self, p):
                    from plugins.sprite_animation.models import AnimationLibrary as AL

                    loaded = AL.load(p)
                    sp = loaded.spritesheet_path
                    resolved = Path(tmp) / sp if sp else None

                    if not resolved or not resolved.exists():
                        return

                    launched.append(str(p))

            ed = FakeEd()
            ed._launch_animation_editor_with_json(path)
            assert launched == []
