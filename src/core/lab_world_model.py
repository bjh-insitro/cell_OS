"""
Lab world model facade for cell_OS.

This exposes the existing LabWorldModel class from src.lab_world_model
under a stable core namespace, without touching the older code that lives
in src.core.world_model (Artifact, UnitOp, etc).
"""

from __future__ import annotations

from src.lab_world_model import LabWorldModel, CampaignId, PathLike

__all__ = ["LabWorldModel", "CampaignId", "PathLike"]
