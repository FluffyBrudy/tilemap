"""Shared launcher for standalone widget subprocesses.

Provides a single function that works for both pip-installed and local dev
environments, eliminating the "works on PyPI but not locally" problem.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Import BASE_PATH from constants (works both installed and as script)
_current = Path(__file__).resolve()
_src = _current.parent.parent
if _src not in sys.path:
    sys.path.insert(0, str(_src))

from constants import BASE_PATH  # noqa: E402


def launch_standalone(
    module_name: str,
    args: list[str],
    cwd: Path | None = None,
    text: bool = False,
) -> subprocess.Popen:
    """Launch a standalone widget module in a subprocess.

    Tries three strategies in order:

    1. **Module invocation** (``python -m <name>``) — works after
       ``pip install`` (regular or ``-e``) when the module is in
       ``py-modules`` or a discovered package.
    2. **Direct script path** (``src/<name>.py``) — works in local dev
       even before the package is installed.
    3. **PYTHONPATH injection** — last resort for editable installs where
       the module lives under ``src/`` but isn't explicitly listed.

    Both stdout and stderr are captured as pipes so errors are always
    trackable (no more ``subprocess.DEVNULL`` hiding failures).

    Parameters
    ----------
    module_name : str
        Dotted module name, e.g. ``"standalone_filemanager"`` or
        ``"plugins.sprite_animation.standalone"``.
    args : list[str]
        CLI arguments to pass to the subprocess.
    cwd : Path, optional
        Working directory for the subprocess.
    text : bool, default ``False``
        If ``True``, open stdout/stderr in text mode (needed when you
        call ``.communicate()`` and expect ``str`` instead of ``bytes``).

    Returns
    -------
    subprocess.Popen
        The running subprocess.

    Raises
    ------
    RuntimeError
        If none of the three strategies can locate the module.
    """
    # Strategy 1: module invocation
    try:
        import importlib.util
        if importlib.util.find_spec(module_name) is not None:
            cmd = [sys.executable, "-m", module_name] + args
            return subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=text, cwd=str(cwd) if cwd else None,
            )
    except ModuleNotFoundError:
        pass
    except Exception:
        pass

    # Strategy 2: direct script path from src/
    # Convert dotted name to file path: standalone_filemanager -> standalone_filemanager.py
    #                                   plugins.sprite_animation.standalone -> plugins/sprite_animation/standalone.py
    script_rel = module_name.replace(".", "/") + ".py"
    script_path = BASE_PATH / "src" / script_rel
    if script_path.exists():
        cmd = [sys.executable, str(script_path)] + args
        return subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=text, cwd=str(cwd) if cwd else None,
        )

    # Strategy 3: inject src/ into PYTHONPATH
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(BASE_PATH / "src") + (os.pathsep + existing if existing else "")
    cmd = [sys.executable, "-m", module_name] + args
    return subprocess.Popen(
        cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=text, cwd=str(cwd) if cwd else None,
    )
