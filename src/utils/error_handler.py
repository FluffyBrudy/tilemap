"""
Central error handling system for tilemap editor.

Provides singleton error capture with context information,
thread-safe operation, and unified logging.

Initialized via dependency injection from Editor - no global config dependency.
"""

import json
import threading
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


class ErrorHandler:
    """Singleton error handler for centralized error capture and logging."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, log_root: Path = None, config: dict = None):
        """Ensure singleton pattern with thread safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
                    cls._instance._lock = None
                    cls._instance._recent_errors = []
                    cls._instance._config = {}
                    cls._instance._max_recent_errors = 50
                    cls._instance._console = None
                    cls._instance._file_logging = True
                    cls._instance._console_output_enabled = True
                    cls._instance._severity_levels = ["error", "warning", "info"]
                    cls._instance.log_file = None
                    cls._instance.log_dir = None
        return cls._instance

    def __init__(self, log_root: Path, config: dict):
        """Initialize error handler with log file setup.

        Args:
            log_root: Path to logs directory (e.g., base_path/data_path/logs)
            config: error_handler configuration dictionary from settings.json
        """
        if self._initialized:
            return

        self._lock = threading.Lock()
        self._recent_errors = []
        self._config = config

        self._max_recent_errors = config.get("max_recent_errors", 50)
        self._console = None

        log_path = config.get("log_path", "errors.log")
        self.log_file = log_root / log_path
        self.log_dir = self.log_file.parent
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._file_logging = config.get("file_logging", True)
        self._console_output_enabled = config.get("console_output", True)
        self._severity_levels = config.get(
            "severity_levels", ["error", "warning", "info"]
        )

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
        self._capture_impl(error, context, severity)

    def capture_info(self, message: str, context: str = "") -> None:
        """
        Capture an informational message (not an error).

        Args:
            message: The info message to log
            context: Context string describing where message originated
        """
        self._capture_impl(None, context, "info", message=message)

    def _capture_impl(
        self,
        error: Exception | None,
        context: str = "",
        severity: str = "error",
        message: str | None = None,
    ) -> None:
        """
        Internal implementation of error capture.
        """

        if severity not in self._severity_levels:
            return

        error_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error_type": type(error).__name__ if error else severity,
            "message": str(error) if error else (message or ""),
            "context": context,
            "severity": severity,
            "stack_trace": "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            if error
            else None,
            "thread_id": threading.current_thread().ident,
        }

        with self._lock:
            self._recent_errors.append(error_data)
            if len(self._recent_errors) > self._max_recent_errors:
                self._recent_errors.pop(0)

        if self._file_logging:
            self._write_to_log(error_data)

        if self._console_output_enabled:
            self._console_output(error_data)

        self._notify_console(error_data)

    def _write_to_log(self, error_data: dict[str, Any]) -> None:
        """Write error data to log file."""
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(error_data) + "\n")
        except Exception as e:
            print(f"Failed to write to error log: {e}")
            print(f"Original error: {error_data}")

    def _console_output(self, error_data: dict[str, Any]) -> None:
        """Output error to console with formatting."""
        severity_symbol = {"error": "ERROR", "warning": "WARN", "info": "INFO"}.get(
            error_data["severity"], "ERROR"
        )

        context_str = f" [{error_data['context']}]" if error_data["context"] else ""
        print(
            f"[{severity_symbol}]{context_str} {error_data['error_type']}: {error_data['message']}"
        )

    def get_recent_errors(self, count: int = 10) -> list[dict[str, Any]]:
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

    def get_error_summary(self) -> dict[str, Any]:
        """Get summary of error statistics."""
        with self._lock:
            if not self._recent_errors:
                return {"total": 0, "by_type": {}, "by_context": {}, "by_severity": {}}

            by_type = {}
            by_context = {}
            by_severity = {}

            for error in self._recent_errors:
                error_type = error["error_type"]
                by_type[error_type] = by_type.get(error_type, 0) + 1

                context = error["context"] or "unknown"
                by_context[context] = by_context.get(context, 0) + 1

                severity = error["severity"]
                by_severity[severity] = by_severity.get(severity, 0) + 1

            return {
                "total": len(self._recent_errors),
                "by_type": by_type,
                "by_context": by_context,
                "by_severity": by_severity,
                "latest": self._recent_errors[-1] if self._recent_errors else None,
            }

    def _notify_console(self, error_data: dict[str, Any]) -> None:
        """Notify error console of new error (if available)."""
        with self._lock:
            if self._console:
                try:
                    self._console.add_error(error_data)
                except Exception:
                    self._console = None

    def register_console(self, console) -> None:
        """Register an error console for real-time updates."""
        with self._lock:
            self._console = console

    def unregister_console(self) -> None:
        """Unregister error console."""
        with self._lock:
            self._console = None


_error_handler_instance: ErrorHandler = None


def init_error_handler(log_root: Path, config: dict) -> ErrorHandler:
    """Initialize the error handler singleton with proper configuration.

    Must be called by Editor after loading settings.json.

    Args:
        log_root: Path to logs directory (e.g., base_path/data_path/logs)
        config: error_handler configuration from settings.json
    """
    global _error_handler_instance
    _error_handler_instance = ErrorHandler(log_root=log_root, config=config)
    return _error_handler_instance


def get_error_handler() -> ErrorHandler:
    """Get the error handler singleton instance.

    Raises RuntimeError if not initialized.
    """
    global _error_handler_instance
    if _error_handler_instance is None:
        raise RuntimeError(
            "ErrorHandler not initialized. Editor must call init_error_handler() first."
        )
    return _error_handler_instance


class _ErrorHandlerProxy:
    """Proxy class to provide backwards-compatible error_handler access."""

    def __getattr__(self, name):
        global _error_handler_instance
        if _error_handler_instance is None:
            return lambda *args, **kwargs: None
        return getattr(get_error_handler(), name)


error_handler = _ErrorHandlerProxy()


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
        raise
