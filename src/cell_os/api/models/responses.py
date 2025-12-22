"""
Response models for Cell Thalamus API

Pydantic models for formatting API responses.
"""

from pydantic import BaseModel
from typing import List, Optional


class DesignResponse(BaseModel):
    """Response model for experimental designs"""
    design_id: str
    phase: int
    cell_lines: List[str]
    compounds: List[str]
    status: str
    created_at: Optional[str] = None
    well_count: Optional[int] = None


class ResultResponse(BaseModel):
    """Response model for experimental results"""
    result_id: int
    design_id: str
    well_id: str
    cell_line: str
    compound: str
    dose_uM: float
    timepoint_h: float
    plate_id: str
    day: int
    operator: str
    is_sentinel: bool
    morph_er: float
    morph_mito: float
    morph_nucleus: float
    morph_actin: float
    morph_rna: float
    atp_signal: float  # NOTE: Actually LDH cytotoxicity (kept name for backward compat). High = cell death, Low = viable
