"""
Execution queue for managing workflow execution order.
"""
from collections import deque
from typing import Callable, List


class ExecutionQueue:
    """Simple in-memory execution queue with explicit start/stop controls."""
    
    def __init__(self):
        self._pending = deque()
        self._active = False
    
    def submit(self, execution_id: str):
        """Submit an execution to the queue."""
        self._pending.append(execution_id)
    
    def start(self, worker: Callable[[str], None]):
        """Process queued executions with the provided worker callback."""
        self._active = True
        while self._active and self._pending:
            execution_id = self._pending.popleft()
            worker(execution_id)
    
    def stop(self):
        """Stop processing the queue."""
        self._active = False
    
    def pending(self) -> List[str]:
        """Get list of pending execution IDs."""
        return list(self._pending)
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._pending) == 0
    
    def size(self) -> int:
        """Get number of pending executions."""
        return len(self._pending)
