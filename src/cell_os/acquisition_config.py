# -*- coding: utf-8 -*-
"""Acquisition configuration for imaging dose loops.

Defines scoring weights and operational stance (personality) of the acquisition function.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class AcquisitionConfig:
    """Configuration for multi-objective acquisition scoring.
    
    Defines the operational stance of the imaging loop by setting weights
    for stress maximization vs. constraint penalties.
    
    Four canonical personalities:
    
    1. **POSH Optimizer**: Maximize morphological information for single-dose screens
       - Use for: POSH pre-screen dose selection (expensive, non-repeatable assays)
       - w_stress=1.0, w_viab=1.5, w_qc=1.2
       - Philosophy: "Live at the boundary between order and collapse"
    
    2. **Ambitious Postdoc**: Stress-greedy, accepts QC/viability violations for signal
       - Use for: EC50 mapping, exploratory assay development
       - w_stress=1.0, w_viab=0.1, w_qc=0.15
    
    3. **Cautious Operator**: QC-first, avoids any violations
       - Use for: Production screens, long-term batch processes
       - w_stress=0.6, w_viab=1.0, w_qc=1.2
    
    4. **Wise PI**: Adaptive - starts ambitious, becomes cautious as confidence builds
       - Use for: Multi-cycle optimization, adaptive research
       - (Requires cycle-dependent weight adjustment - future work)
    
    Attributes
    ----------
    w_stress : float
        Weight for stress term (higher = prioritize stress signal).
    w_viab : float
        Weight for viability penalty (higher = avoid viability violations).
    w_qc : float
        Weight for QC penalty (higher = avoid segmentation issues).
    personality : str
        Human-readable name for this configuration.
    """
    
    w_stress: float = 1.0
    w_viab: float = 2.0
    w_qc: float = 1.5
    personality: str = "default"
    
    @classmethod
    def posh_optimizer(cls) -> "AcquisitionConfig":
        """Maximize morphological information for single-shot POSH screens.
        
        Optimizes for the edge where stress is high but segmentation remains intact.
        Designed for pre-screens that choose ONE dose for expensive, non-repeatable runs.
        
        Philosophy: "Maximize information density while keeping the assay operational."
        Pushes to the boundary between order and collapse because that's where
        the biology is loudest.
        """
        return cls(
            w_stress=1.0,
            w_viab=0.5,
            w_qc=0.8,
            personality="posh_optimizer"
        )
    
    @classmethod
    def ambitious_postdoc(cls) -> "AcquisitionConfig":
        """Stress-greedy configuration for exploratory work.
        
        Accepts viability/QC violations if stress signal is strong.
        Best for finding stress-response curves and EC50 values.
        """
        return cls(
            w_stress=1.0,
            w_viab=0.1,
            w_qc=0.15,
            personality="ambitious_postdoc"
        )
    
    @classmethod
    def cautious_operator(cls) -> "AcquisitionConfig":
        """QC-first configuration for production work.
        
        Prioritizes clean segmentation and reproducibility over stress signal.
        Best for large screens and comparison runs.
        """
        return cls(
            w_stress=0.6,
            w_viab=1.0,
            w_qc=1.2,
            personality="cautious_operator"
        )
    
    @classmethod
    def balanced(cls) -> "AcquisitionConfig":
        """Balanced configuration.
        
        Moderate tradeoffs between stress and constraints.
        """
        return cls(
            w_stress=1.0,
            w_viab=2.0,
            w_qc=1.5,
            personality="balanced"
        )
    
    @classmethod
    def posh_optimizer(cls) -> "AcquisitionConfig":
        """POSH-specific configuration: maximize morphological information.
        
        Optimized for single-dose POSH screens where the goal is to extract
        maximum phenotypic information from an expensive, non-repeatable assay.
        
        Philosophy: "Maximize morphological information while keeping assay operational"
        - Stress is primary signal (rich morphology, high phenotypic expression)
        - Viability is soft constraint (mild damage acceptable, catastrophic loss rejected)
        - QC penalties curve smoothly (no hard cliffs)
        - Lives at boundary between order and collapse
        
        Target: 0.35-0.55 µM TBHP range where:
        - Stress transcription is high
        - Morphology is rich (cytoplasm reorganizes, mitochondria pop)
        - Cell boundaries remain intact
        - Segmentation still works
        - Fields are dense enough for statistics
        """
        return cls(
            w_stress=1.0,
            w_viab=1.5,
            w_qc=1.2,
            personality="posh_optimizer"
        )
    
    def __str__(self) -> str:
        return (f"AcquisitionConfig(personality='{self.personality}', "
                f"w_stress={self.w_stress}, w_viab={self.w_viab}, w_qc={self.w_qc})")
