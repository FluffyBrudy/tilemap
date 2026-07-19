import atexit
import sys
from datetime import datetime
from pathlib import Path

from constants import MAX_LOG_FILES


class StreamTee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data: str) -> int:
        written = 0
        for stream in self.streams:
            try:
                written = stream.write(data)
            except Exception:
                continue
        self.flush()
        return written

    def flush(self) -> None:
        for stream in self.streams:
            try:
                stream.flush()
            except Exception:
                continue

    @property
    def encoding(self):
        for stream in self.streams:
            if hasattr(stream, "encoding"):
                return stream.encoding
        return "utf-8"

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        for stream in self.streams:
            if hasattr(stream, "fileno"):
                try:
                    return stream.fileno()
                except Exception:
                    continue
        return -1


def _ensure_log_dir(base_path: Path) -> Path | None:
    candidates = [
        base_path / "data" / "logs",
        base_path / "logs",
        Path.home() / ".tilemap" / "logs",
    ]
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            test_path = path / ".write_test"
            with open(test_path, "w", encoding="utf-8"):
                pass
            test_path.unlink(missing_ok=True)
            return path
        except Exception:
            continue
    return None


def setup_console_log(base_path: Path, prefix: str = "tilemap") -> Path | None:
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    log_dir = _ensure_log_dir(base_path)
    if not log_dir:
        return None

    try:
        log_files = sorted(
            log_dir.glob(f"{prefix}_*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old_path in log_files[MAX_LOG_FILES:]:
            try:
                old_path.unlink(missing_ok=True)
            except Exception:
                continue
    except Exception:
        pass

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{prefix}_{timestamp}.log"
    try:
        log_file = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")
    except Exception:
        return None

    sys.stdout = StreamTee(original_stdout, log_file)
    sys.stderr = StreamTee(original_stderr, log_file)

    def _close_log():
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        try:
            log_file.close()
        except Exception:
            pass
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    atexit.register(_close_log)
    return log_path
