"""
Request models for Cell Thalamus API

Pydantic models for validating incoming requests.
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class RunSimulationRequest(BaseModel):
    """Request to run a standard simulation (demo/quick/full mode)"""
    cell_lines: List[str]
    compounds: Optional[List[str]] = None
    mode: str = "demo"  # demo, quick, full


class AutonomousLoopCandidate(BaseModel):
    """Individual candidate in autonomous loop portfolio"""
    compound: str
    cell_line: str
    timepoint_h: float
    wells: int  # Allocated well count
    priority: str  # "Primary", "Scout", "Probe"


class AutonomousLoopRequest(BaseModel):
    """Request for autonomous loop experiment - portfolio of top candidates"""
    candidates: List[AutonomousLoopCandidate]


class DesignGeneratorRequest(BaseModel):
    """Request model for design generation"""
    design_id: str
    description: str
    cell_lines: Optional[List[str]] = None
    compounds: Optional[List[str]] = None
    dose_multipliers: Optional[List[float]] = None
    replicates_per_dose: int = 3
    days: Optional[List[int]] = None
    operators: Optional[List[str]] = None
    timepoints_h: Optional[List[float]] = None
    sentinel_config: Optional[Dict[str, Dict[str, Any]]] = None
    plate_format: int = 96
    checkerboard: bool = False
    exclude_corners: bool = False
    exclude_edges: bool = False
