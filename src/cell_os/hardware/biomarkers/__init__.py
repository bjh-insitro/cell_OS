"""
Biomarker models for supplemental IF channels.

Biomarkers map latent stress states to observable IF readouts.
They are stress-specific markers that complement core Cell Painting.

Example biomarkers:
- γ-H2AX: DNA damage marker (phosphorylated histone H2AX at DSBs)
- LC3: Autophagy marker (future)
- Cleaved Caspase-3: Apoptosis marker (future)
"""

from .gamma_h2ax import GammaH2AXModel
from .registry import BiomarkerRegistry

__all__ = [
    "BiomarkerRegistry",
    "GammaH2AXModel",
]
