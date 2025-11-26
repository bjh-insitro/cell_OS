"""Forwarding module to keep `cell_os.core.world_model` imports working.

This exposes the legacy unit-operation primitives from `src/core/world_model`
and maps the modern `cell_os.lab_world_model.LabWorldModel` to the name
`WorldModel` for backwards compatibility.
"""

from src.core.world_model import (
    Artifact,
    ExecutionRecord,
    UnitOp,
    PassageOp,
    FeedOp,
)
from cell_os.lab_world_model import LabWorldModel as WorldModel

__all__ = [
    "Artifact",
    "ExecutionRecord",
    "UnitOp",
    "PassageOp",
    "FeedOp",
    "WorldModel",
]
