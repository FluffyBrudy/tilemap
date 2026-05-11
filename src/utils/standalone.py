"""Shared launcher for standalone widget subprocesses.

Provides a single function that works for both pip-installed and local dev
environments, eliminating the "works on PyPI but not locally" problem.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from utils.error_handler import error_handler

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
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BASE_PATH / "src") + (
        os.pathsep + env.get("PYTHONPATH", "")
    )
    # Strategy 1: module invocation (skip for standalone_* modules - they need PYTHONPATH)
    if not module_name.startswith("standalone_"):
        try:
            import importlib.util

            spec = importlib.util.find_spec(module_name)
            if spec is None:
                error_handler.capture_info(
                    f"Module not found: {module_name}", context="launch_standalone"
                )
                raise ModuleNotFoundError(f"Module not found: {module_name}")
            else:
                error_handler.capture_info(f"Module found: {module_name}", context="launch_standalone")
            cmd = [sys.executable, "-m", module_name] + args
            error_handler.capture_info(f"Command: {cmd}", context="launch_standalone")

            # For GUI tools, don't wait - just launch and return immediately
            # GUI apps don't produce stdout/stderr that we can read synchronously
            proc = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(cwd) if cwd else None,
            )

            # Don't call communicate() - GUI tools block on display, don't respond immediately
            # Just return the process - it's running independently
            return proc
        except ModuleNotFoundError as e:
            error_handler.capture_info(f"Module not found: {module_name} - {e}", context="launch_standalone")
        except ImportError as e:
            error_handler.capture_info(f"Import error for {module_name}: {e}", context="launch_standalone")
        except Exception as e:
            error_handler.capture(
                e, context=f"Error launching {module_name}: {type(e).__name__}", severity="info"
            )

    # Strategy 2: direct script path from src/ (only for non-standalone modules)
    # Skip this strategy for standalone_* modules as they need proper module resolution
    if not module_name.startswith("standalone_"):
        # Convert dotted name to file path: standalone_filemanager -> standalone_filemanager.py
        #                                       plugins.sprite_animation.standalone -> plugins/sprite_animation/standalone.py
        script_rel = module_name.replace(".", "/") + ".py"
        script_path = BASE_PATH / "src" / script_rel
        if script_path.exists():
            cmd = [sys.executable, str(script_path)] + args
            return subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=text,
                cwd=str(cwd) if cwd else None,
            )

    # Strategy 3: inject src/ into PYTHONPATH
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(BASE_PATH / "src") + (
        os.pathsep + existing if existing else ""
    )
    cmd = [sys.executable, "-m", module_name] + args
    # For standalone modules, don't override cwd to keep PYTHONPATH working
    effective_cwd = (
        None if module_name.startswith("standalone_") else (str(cwd) if cwd else None)
    )
    return subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        cwd=effective_cwd,
    )