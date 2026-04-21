# ErrorHandler Specification

## Overview
Central singleton error capture system to replace scattered print statements and provide unified error visibility for debugging and LLM assistance.

## Requirements

### Core Functionality
- Singleton pattern for global access
- Capture exceptions with context information
- Write to log file + console output
- Thread-safe operation
- Minimal performance impact

### Interface Design
```python
# utils/error_handler.py
class ErrorHandler:
    def capture(self, error: Exception, context: str = "", severity: str = "error")
    def get_recent_errors(self, count: int = 10) -> List[dict]
    def clear_errors(self)
    def get_error_summary(self) -> dict

# Module-level convenience
error_handler = ErrorHandler()

# Context manager
@contextmanager
def error_context(operation: str)
```

## Implementation Details

### File Structure
```
src/utils/error_handler.py - Main ErrorHandler class
src/utils/__init__.py - Export error_handler for easy imports
data/logs/errors.log - Persistent error log
```

### Error Data Format
```python
{
    "timestamp": "2024-01-01T12:00:00Z",
    "error_type": "ValueError",
    "message": "Invalid tile coordinate",
    "context": "save_map",
    "severity": "error",
    "stack_trace": "...",
    "thread_id": "12345"
}
```

### Usage Patterns
```python
# Direct replacement:
# OLD: print(f"Error saving map: {e}")
# NEW: error_handler.capture(e, context="save_map")

# Context manager:
with error_context("load_tileset"):
    tileset = load_tileset(path)

# Manual capture:
try:
    dangerous_operation()
except Exception as e:
    error_handler.capture(e, context="ui_update", severity="warning")
```

## Minimal Testing Strategy

### Test Cases (Only if needed)
1. **Singleton Behavior** - Verify same instance returned
2. **File Logging** - Confirm errors written to file
3. **Thread Safety** - Multiple threads capturing simultaneously

### No Tests Needed For
- Basic exception capture (deterministic)
- File writing (standard library)
- JSON serialization (standard library)

## Integration Plan

### Phase 1: Core Implementation
- Create ErrorHandler singleton
- Basic file + console output
- Module-level convenience import

### Phase 2: Gradual Replacement
- Replace 5-10 most critical print statements first
- Focus on file operations and subprocess errors
- Add meaningful context strings

### Phase 3: Enhancement (Future)
- Error categorization
- Interactive console commands
- Error analytics

## Success Criteria
- All errors visible in single log file
- No more lost error messages
- Context information helps with debugging
- Zero performance impact on normal operation
- Easy import pattern: `from utils import error_handler`

## Constraints
- No external dependencies
- Must work with existing PyInstaller builds
- Backward compatible with current error handling
- Simple enough for quick implementation

## Context for Future Development

This ErrorHandler serves as the foundation for:
- Better debugging visibility during development
- LLM-assisted feature development with proper error context
- Future interactive debugging console
- Error analytics and pattern recognition
- Centralized logging for production debugging

The singleton pattern ensures minimal disruption to existing code while providing maximum visibility into error patterns throughout the application.
