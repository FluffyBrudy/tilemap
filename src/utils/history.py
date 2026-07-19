import copy
from typing import Any


class HistoryState:
    def __init__(self, data: Any, description: str):
        self.data = data
        self.description = description


class HistoryManager:
    def __init__(self, max_states: int = 50):
        self.max_states = max_states
        self.undo_stack: list[HistoryState] = []
        self.redo_stack: list[HistoryState] = []

    def save_state(self, data: Any, description: str):

        state_copy = copy.deepcopy(data)
        self.undo_stack.append(HistoryState(state_copy, description))
        if len(self.undo_stack) > self.max_states:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self, current_data: Any) -> Any:
        if not self.undo_stack:
            return None

        self.redo_stack.append(HistoryState(copy.deepcopy(current_data), "Redo State"))
        state = self.undo_stack.pop()
        return state.data

    def redo(self, current_data: Any) -> Any:
        if not self.redo_stack:
            return None

        self.undo_stack.append(HistoryState(copy.deepcopy(current_data), "Undo State"))
        state = self.redo_stack.pop()
        return state.data

    @property
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0
