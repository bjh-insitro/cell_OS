from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional


class Phase0ExitCriteriaFailed(RuntimeError):
    """Raised when a Phase 0 gate fails."""
    pass


@dataclass
class Phase0GateFailure(Phase0ExitCriteriaFailed):
    criterion: str
    measured: float
    threshold: float
    message: str
    details: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        super().__init__(self.message)
