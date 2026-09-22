"""UI strings must stay plain ASCII: the bundled fonts only guarantee
ASCII, so any non-ASCII character in an owned source file is a latent
rendering bug. One file, one rule - never per-feature copies."""

from pathlib import Path

# Sources whose rendered strings this rule owns: the particle plugin,
# the widgets it renders through, and the particle tests themselves.
OWNED = [
    "src/plugins/particle_editor/*.py",
    "src/widgets/particle_system.py",
    "src/widgets/particle_presets.py",
    "src/widgets/ui/node_editor.py",
    "src/editor.py",
    "tests/test_particle_*.py",
    "tests/e2e/test_particle_*.py",
    "tests/e2e/*.py",
    "tests/test_unicode.py",
]


def _owned_paths():
    root = Path(__file__).parent.parent
    paths = []
    for pattern in OWNED:
        paths.extend(sorted(root.glob(pattern)))
    return paths


def test_owned_sources_are_pure_ascii():
    offenders = []
    for path in _owned_paths():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for ch in line:
                if ord(ch) > 127:
                    offenders.append(f"{path.name}:{lineno}: U+{ord(ch):04X}")
                    break
    assert offenders == []


def test_owned_list_covers_plugin_package():
    names = {p.name for p in _owned_paths()}
    assert "editor.py" in names
    assert "models.py" in names
    assert any(n.startswith("test_particle_") for n in names)
