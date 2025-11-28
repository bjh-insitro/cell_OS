"""
Multi-Assay Simulation

Support for diverse assay readouts beyond viability:
- Flow cytometry (multi-parameter)
- High-content imaging (morphology)
- qPCR (gene expression)
- ELISA (secreted factors)
- Western blot (protein levels)
"""

import numpy as np
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class AssayType(Enum):
    """Supported assay types."""
    VIABILITY = "viability"
    FLOW_CYTOMETRY = "flow_cytometry"
    IMAGING = "imaging"
    QPCR = "qpcr"
    ELISA = "elisa"
    WESTERN_BLOT = "western_blot"


@dataclass
class FlowCytometryResult:
    """Flow cytometry multi-parameter readout."""
    live_cells_percent: float
    dead_cells_percent: float
    apoptotic_cells_percent: float
    mean_fsc: float  # Forward scatter (cell size)
    mean_ssc: float  # Side scatter (granularity)
    marker_positive_percent: Dict[str, float]  # e.g., {"CD4": 45.2, "CD8": 32.1}
    total_events: int


@dataclass
class ImagingResult:
    """High-content imaging readout."""
    cell_count: int
    mean_cell_area: float  # μm²
    mean_nuclear_area: float  # μm²
    nuclear_cytoplasmic_ratio: float
    morphology_score: float  # 0-1, health indicator
    organelle_features: Dict[str, float]  # e.g., {"mitochondria_intensity": 0.75}
    field_quality: float  # 0-1, image quality


@dataclass
class qPCRResult:
    """qPCR gene expression readout."""
    gene_name: str
    ct_value: float  # Cycle threshold
    fold_change: float  # Relative to control
    std_error: float
    p_value: float


@dataclass
class ELISAResult:
    """ELISA protein quantification."""
    analyte: str
    concentration_pg_ml: float
    od_450nm: float  # Optical density
    cv_percent: float
    within_range: bool  # Within standard curve


@dataclass
class WesternBlotResult:
    """Western blot protein levels."""
    protein: str
    band_intensity: float
    normalized_intensity: float  # Relative to loading control
    molecular_weight_kda: float


class MultiAssaySimulator:
    """
    Simulate diverse assay readouts with realistic noise and biology.
    """
    
    def __init__(self, random_seed: Optional[int] = None):
        self.rng = np.random.default_rng(random_seed)
        
    def simulate_flow_cytometry(self,
                                viability: float,
                                treatment_effect: float = 0.0,
                                markers: Optional[Dict[str, float]] = None) -> FlowCytometryResult:
        """
        Simulate flow cytometry readout.
        
        Args:
            viability: Base viability (0-1)
            treatment_effect: Effect of treatment on apoptosis (0-1)
            markers: Optional dict of marker expression levels
            
        Returns:
            FlowCytometryResult with multi-parameter data
        """
        # Calculate cell populations
        live_pct = viability * 100
        
        # Treatment induces apoptosis
        apoptotic_pct = treatment_effect * 30 * self.rng.normal(1.0, 0.15)
        apoptotic_pct = np.clip(apoptotic_pct, 0, live_pct)
        
        # Remaining are dead
        dead_pct = 100 - live_pct - apoptotic_pct
        dead_pct = max(0, dead_pct)
        
        # Normalize to 100%
        total = live_pct + apoptotic_pct + dead_pct
        live_pct = (live_pct / total) * 100
        apoptotic_pct = (apoptotic_pct / total) * 100
        dead_pct = (dead_pct / total) * 100
        
        # Scatter parameters (correlated with viability)
        base_fsc = 50000 * viability
        base_ssc = 30000 * viability
        
        mean_fsc = base_fsc * self.rng.normal(1.0, 0.10)
        mean_ssc = base_ssc * self.rng.normal(1.0, 0.12)
        
        # Marker expression
        marker_results = {}
        if markers:
            for marker, base_level in markers.items():
                # Add biological variation
                measured = base_level * self.rng.normal(1.0, 0.08)
                marker_results[marker] = np.clip(measured, 0, 100)
        
        # Total events (typical flow run)
        total_events = int(self.rng.normal(10000, 500))
        
        return FlowCytometryResult(
            live_cells_percent=live_pct,
            dead_cells_percent=dead_pct,
            apoptotic_cells_percent=apoptotic_pct,
            mean_fsc=mean_fsc,
            mean_ssc=mean_ssc,
            marker_positive_percent=marker_results,
            total_events=total_events
        )
    
    def simulate_imaging(self,
                        cell_count: int,
                        viability: float,
                        treatment_effect: float = 0.0) -> ImagingResult:
        """
        Simulate high-content imaging readout.
        
        Args:
            cell_count: Number of cells in field
            viability: Cell viability (0-1)
            treatment_effect: Treatment-induced morphology changes
            
        Returns:
            ImagingResult with morphology features
        """
        # Cell area (healthy cells are larger)
        base_area = 400  # μm²
        mean_area = base_area * viability * self.rng.normal(1.0, 0.15)
        
        # Nuclear area
        base_nuclear = 150  # μm²
        mean_nuclear = base_nuclear * self.rng.normal(1.0, 0.12)
        
        # N/C ratio (increases with stress)
        nc_ratio = mean_nuclear / mean_area
        nc_ratio *= (1.0 + treatment_effect * 0.3)  # Stress increases ratio
        
        # Morphology score (decreases with treatment)
        morphology = viability * (1.0 - treatment_effect * 0.5)
        morphology *= self.rng.normal(1.0, 0.10)
        morphology = np.clip(morphology, 0, 1)
        
        # Organelle features
        organelles = {
            "mitochondria_intensity": viability * self.rng.normal(1.0, 0.15),
            "lysosome_count": 20 * (1 + treatment_effect) * self.rng.normal(1.0, 0.20),
            "stress_granules": treatment_effect * 10 * self.rng.normal(1.0, 0.30)
        }
        
        # Field quality (random technical variation)
        field_quality = self.rng.normal(0.9, 0.05)
        field_quality = np.clip(field_quality, 0.5, 1.0)
        
        return ImagingResult(
            cell_count=int(cell_count * self.rng.normal(1.0, 0.10)),
            mean_cell_area=mean_area,
            mean_nuclear_area=mean_nuclear,
            nuclear_cytoplasmic_ratio=nc_ratio,
            morphology_score=morphology,
            organelle_features=organelles,
            field_quality=field_quality
        )
    
    def simulate_qpcr(self,
                     gene_name: str,
                     fold_change: float,
                     base_ct: float = 25.0) -> qPCRResult:
        """
        Simulate qPCR gene expression.
        
        Args:
            gene_name: Gene identifier
            fold_change: Expression change relative to control
            base_ct: Baseline Ct value for control
            
        Returns:
            qPCRResult with Ct values and statistics
        """
        # Convert fold change to Ct difference
        # Ct decreases by 1 for each doubling
        ct_diff = -np.log2(fold_change)
        
        # Add technical variation (qPCR is precise, ~0.2 Ct SD)
        ct_value = base_ct + ct_diff + self.rng.normal(0, 0.2)
        
        # Measured fold change (back-calculate with noise)
        measured_fc = 2 ** (-(ct_value - base_ct))
        
        # Standard error (typical for triplicates)
        std_error = measured_fc * self.rng.uniform(0.05, 0.15)
        
        # P-value (simplified - assumes t-test)
        # Larger fold changes = smaller p-values
        z_score = abs(np.log2(measured_fc)) / 0.3
        p_value = 2 * (1 - 0.5 * (1 + np.tanh(z_score / np.sqrt(2))))
        p_value = max(0.001, min(0.999, p_value))
        
        return qPCRResult(
            gene_name=gene_name,
            ct_value=ct_value,
            fold_change=measured_fc,
            std_error=std_error,
            p_value=p_value
        )
    
    def simulate_elisa(self,
                      analyte: str,
                      true_concentration: float) -> ELISAResult:
        """
        Simulate ELISA protein quantification.
        
        Args:
            analyte: Protein/cytokine name
            true_concentration: True concentration in pg/mL
            
        Returns:
            ELISAResult with OD and concentration
        """
        # ELISA has ~10-15% CV
        measured_conc = true_concentration * self.rng.normal(1.0, 0.12)
        measured_conc = max(0, measured_conc)
        
        # Optical density (sigmoidal standard curve)
        # OD = max_od / (1 + (EC50/conc)^hill)
        max_od = 2.5
        ec50 = 500  # pg/mL
        hill = 1.0
        
        od_450 = max_od / (1 + (ec50 / max(measured_conc, 1)) ** hill)
        od_450 += self.rng.normal(0, 0.02)  # Plate reader noise
        od_450 = np.clip(od_450, 0, max_od)
        
        # CV calculation
        cv_percent = (0.12 * 100) + self.rng.normal(0, 2)
        
        # Check if within standard curve range
        within_range = 10 < measured_conc < 5000
        
        return ELISAResult(
            analyte=analyte,
            concentration_pg_ml=measured_conc,
            od_450nm=od_450,
            cv_percent=cv_percent,
            within_range=within_range
        )
    
    def simulate_western_blot(self,
                             protein: str,
                             expression_level: float,
                             molecular_weight: float = 50.0) -> WesternBlotResult:
        """
        Simulate Western blot protein detection.
        
        Args:
            protein: Protein name
            expression_level: Relative expression (1.0 = control)
            molecular_weight: Expected MW in kDa
            
        Returns:
            WesternBlotResult with band intensity
        """
        # Western blots have high variability (~20-30% CV)
        band_intensity = expression_level * 1000 * self.rng.normal(1.0, 0.25)
        band_intensity = max(0, band_intensity)
        
        # Normalize to loading control (e.g., actin)
        loading_control = 1000 * self.rng.normal(1.0, 0.10)
        normalized = band_intensity / loading_control
        
        # MW can shift slightly
        measured_mw = molecular_weight * self.rng.normal(1.0, 0.02)
        
        return WesternBlotResult(
            protein=protein,
            band_intensity=band_intensity,
            normalized_intensity=normalized,
            molecular_weight_kda=measured_mw
        )
