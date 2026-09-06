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
