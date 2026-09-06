"""Tests for the marker palette CLI (subprocess-isolated)."""

import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).parent.parent / "src" / "standalone_marker_palette.py"
PY = sys.executable


def run(*args):
    return subprocess.run([PY, str(SRC), *args], capture_output=True, text=True,
                          timeout=120)


class TestGeneration:
    def test_default_4x4(self, tmp_path):
        proc = run("--output-dir", str(tmp_path))
        assert proc.returncode == 0, proc.stderr
        out = tmp_path / "markers_4x4_c32.png"
        assert out.is_file()

        import pygame

        pygame.init()
        try:
            surf = pygame.image.load(str(out))
            assert surf.get_size() == (128, 128)
            colors = {surf.get_at((c * 32 + 16, r * 32 + 16))[:3]
                      for r in range(4) for c in range(4)}
            assert len(colors) == 16
        finally:
            pygame.quit()

    def test_custom_size_and_name(self, tmp_path):
        proc = run("--rows", "2", "--cols", "5", "--cell", "16",
                   "--output-dir", str(tmp_path), "--name", "foes")
        assert proc.returncode == 0, proc.stderr
        out = tmp_path / "foes.png"
        assert out.is_file()

        import pygame

        pygame.init()
        try:
            assert pygame.image.load(str(out)).get_size() == (80, 32)
        finally:
            pygame.quit()

    def test_1x1_spawn_cell(self, tmp_path):
        out = tmp_path / "spawn.png"
        proc = run("--rows", "1", "--cols", "1", "--out", str(out))
        assert proc.returncode == 0, proc.stderr
        assert out.is_file()

    def test_prints_resolved_path(self, tmp_path):
        proc = run("--output-dir", str(tmp_path))
        assert proc.returncode == 0
        assert "markers_4x4_c32.png" in proc.stdout


class TestGuards:
    def test_rows_clamped(self, tmp_path):
        proc = run("--rows", "21", "--output-dir", str(tmp_path))
        assert proc.returncode == 2
        assert "--rows" in proc.stderr

    def test_cols_zero_rejected(self, tmp_path):
        proc = run("--cols", "0", "--output-dir", str(tmp_path))
        assert proc.returncode == 2

    def test_bad_cell_rejected(self, tmp_path):
        proc = run("--cell", "0", "--output-dir", str(tmp_path))
        assert proc.returncode == 2

    def test_bad_saturation_rejected(self, tmp_path):
        proc = run("--saturation", "1.5", "--output-dir", str(tmp_path))
        assert proc.returncode == 2


class TestSlopePolygon:
    def test_45_is_half_triangle(self):
        from standalone_marker_palette import slope_polygon

        poly = slope_polygon(32, 45)
        assert len(poly) == 3
        for x, y in poly:
            assert 0 <= x <= 32 and 0 <= y <= 32

    def test_steep_and_shallow_valid(self):
        from standalone_marker_palette import slope_polygon

        for angle in (10, 30, 60, 80, -10, -45, -80):
            poly = slope_polygon(32, angle)
            assert len(poly) >= 3
            for x, y in poly:
                assert -1e-6 <= x <= 33 and -1e-6 <= y <= 33

    def test_descending_mirrors_ascending(self):
        from standalone_marker_palette import slope_polygon

        up = slope_polygon(32, 40)
        down = slope_polygon(32, -40)

        def key(p):
            return (round(p[0], 6), round(p[1], 6))

        assert sorted(key((32 - x, y)) for x, y in up) == sorted(map(key, down))


class TestSlopeRow:
    def test_slope_appends_row(self, tmp_path):
        proc = run("--rows", "4", "--cols", "4", "--slope", "45",
                   "--output-dir", str(tmp_path))
        assert proc.returncode == 0, proc.stderr
        out = tmp_path / "markers_4x4_c32_s45.png"
        assert out.is_file()

        import pygame

        pygame.init()
        try:
            surf = pygame.image.load(str(out))
            assert surf.get_size() == (128, 160)
            oy = 4 * 32
            assert surf.get_at((30, oy + 2))[3] == 0
            assert surf.get_at((2, oy + 29))[3] == 255
        finally:
            pygame.quit()

    def test_slope_matches_column_color(self, tmp_path):
        proc = run("--rows", "2", "--cols", "2", "--slope", "45",
                   "--output-dir", str(tmp_path))
        assert proc.returncode == 0, proc.stderr

        import pygame

        pygame.init()
        try:
            surf = pygame.image.load(str(tmp_path / "markers_2x2_c32_s45.png"))
            assert surf.get_at((4, 2 * 32 + 28))[:3] == surf.get_at((16, 48))[:3]
        finally:
            pygame.quit()

    def test_bad_angles_rejected(self, tmp_path):
        for angle in ("0", "90", "-90", "120"):
            proc = run("--slope", angle, "--output-dir", str(tmp_path))
            assert proc.returncode == 2, angle
            assert "--slope" in proc.stderr


class TestEditorCliWiring:
    def _cli(self, *args):
        import os

        exe = Path(PY).parent / "tilemap-editor"
        return subprocess.run([str(exe), *args], capture_output=True, text=True,
                              timeout=120)

    def test_help_lists_markers(self):
        proc = self._cli("--help")
        assert proc.returncode == 0, proc.stderr
        assert "markers" in proc.stdout

    def test_markers_passthrough(self, tmp_path):
        proc = self._cli("markers", "--rows", "1", "--cols", "2",
                         "--cell", "16", "--output-dir", str(tmp_path))
        assert proc.returncode == 0, proc.stderr
        assert (tmp_path / "markers_2x1_c16.png").is_file()

    def test_markers_forwards_errors(self, tmp_path):
        proc = self._cli("markers", "--rows", "21",
                         "--output-dir", str(tmp_path))
        assert proc.returncode == 2
        assert "--rows" in proc.stderr
