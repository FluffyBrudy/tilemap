"""
Central error handling system for tilemap editor.

Provides singleton error capture with context information,
thread-safe operation, and unified logging.
"""

import threading
import json
import traceback
from datetime import datetime
from typing import List, Dict, Any
from contextlib import contextmanager

from constants import BASE_PATH
from .settings import settings


class ErrorHandler:
    """Singleton error handler for centralized error capture and logging."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Ensure singleton pattern with thread safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize error handler with log file setup."""
        if self._initialized:
            return

        self._lock = threading.Lock()
        self._recent_errors: List[Dict[str, Any]] = []
        self._max_recent_errors = settings.get("error_handler.max_recent_errors", 50)
        self._console = None  # Registered error console

        # Setup log directory and file from settings
        log_path = settings.get("error_handler.log_path", "data/logs/errors.log")
        self.log_file = BASE_PATH / log_path
        self.log_dir = self.log_file.parent
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._initialized = True

    def capture(
        self, error: Exception, context: str = "", severity: str = "error"
    ) -> None:
        """
        Capture an exception with context information.

        Args:
            error: The exception to capture
            context: Context string describing where error occurred
            severity: Error severity level (error, warning, info)
        """
        # Check if this severity level is enabled in settings
        allowed_levels = settings.get(
            "error_handler.severity_levels", ["error", "warning", "info"]
        )
        if severity not in allowed_levels:
            return
        error_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error_type": type(error).__name__,
            "message": str(error),
            "context": context,
            "severity": severity,
            "stack_trace": traceback.format_exc(),
            "thread_id": threading.current_thread().ident,
        }

        # Add to recent errors (thread-safe)
        with self._lock:
            self._recent_errors.append(error_data)
            if len(self._recent_errors) > self._max_recent_errors:
                self._recent_errors.pop(0)

        # Write to log file if enabled
        if settings.get("error_handler.file_logging", True):
            self._write_to_log(error_data)

        # Console output if enabled
        if settings.get("error_handler.console_output", True):
            self._console_output(error_data)

        # Notify error console if it's available
        self._notify_console(error_data)

    def _write_to_log(self, error_data: Dict[str, Any]) -> None:
        """Write error data to log file."""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(error_data) + "\n")
        except Exception as e:
            # Fallback to print if log file fails
            print(f"Failed to write to error log: {e}")
            print(f"Original error: {error_data}")

    def _console_output(self, error_data: Dict[str, Any]) -> None:
        """Output error to console with formatting."""
        severity_symbol = {"error": "ERROR", "warning": "WARN", "info": "INFO"}.get(
            error_data["severity"], "ERROR"
        )

        context_str = f" [{error_data['context']}]" if error_data["context"] else ""
        print(
            f"[{severity_symbol}]{context_str} {error_data['error_type']}: {error_data['message']}"
        )

    def get_recent_errors(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent errors from memory."""
        with self._lock:
            return (
                self._recent_errors[-count:]
                if count > 0
                else self._recent_errors.copy()
            )

    def clear_errors(self) -> None:
        """Clear recent errors from memory."""
        with self._lock:
            self._recent_errors.clear()

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of error statistics."""
        with self._lock:
            if not self._recent_errors:
                return {"total": 0, "by_type": {}, "by_context": {}, "by_severity": {}}

            by_type = {}
            by_context = {}
            by_severity = {}

            for error in self._recent_errors:
                # Count by error type
                error_type = error["error_type"]
                by_type[error_type] = by_type.get(error_type, 0) + 1

                # Count by context
                context = error["context"] or "unknown"
                by_context[context] = by_context.get(context, 0) + 1

                # Count by severity
                severity = error["severity"]
                by_severity[severity] = by_severity.get(severity, 0) + 1

            return {
                "total": len(self._recent_errors),
                "by_type": by_type,
                "by_context": by_context,
                "by_severity": by_severity,
                "latest": self._recent_errors[-1] if self._recent_errors else None,
            }

    def _notify_console(self, error_data: Dict[str, Any]) -> None:
        """Notify error console of new error (if available)."""
        with self._lock:
            if self._console:
                try:
                    self._console.add_error(error_data)
                except Exception:
                    # If console fails, unregister it to avoid repeated failures
                    self._console = None

    def register_console(self, console) -> None:
        """Register an error console for real-time updates."""
        with self._lock:
            self._console = console

    def unregister_console(self) -> None:
        """Unregister error console."""
        with self._lock:
            self._console = None


# Module-level singleton instance
error_handler = ErrorHandler()


@contextmanager
def error_context(operation: str, severity: str = "error"):
    """
    Context manager for automatic error capture.

    Args:
        operation: Description of the operation being performed
        severity: Error severity if exception occurs
    """
    try:
        yield
    except Exception as e:
        error_handler.capture(e, context=operation, severity=severity)
        raise  # Re-raise the exception for existing error handling patterns

