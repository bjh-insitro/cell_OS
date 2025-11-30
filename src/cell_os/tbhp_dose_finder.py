"""
tBHP Dose Finder Module.

Autonomous agent for finding optimal tBHP oxidative stress doses for different cell lines.
Optimizes for:
1. High oxidative stress signal (CellROX)
2. Acceptable viability
3. Good segmentation quality
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import logging

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

logger = logging.getLogger(__name__)


@dataclass
class TBHPDoseResult:
    """Result of tBHP dose finding for one cell line."""
    cell_line: str
    optimal_dose_uM: float
    viability_at_optimal: float
    cellrox_signal_at_optimal: float
    segmentation_quality_at_optimal: float
    dose_response_curve: pd.DataFrame
    status: str  # "success", "failed", "suboptimal"
    notes: str = ""


@dataclass
class TBHPOptimizationCriteria:
    """Criteria for optimal tBHP dose."""
    min_viability: float = 0.70          # At least 70% viable
    target_cellrox_signal: float = 200.0 # Target signal (approx 2x baseline)
    min_segmentation_quality: float = 0.80 # 80% cells segmentable
    
    # Weights for scoring (if no perfect match found)
    weight_viability: float = 2.0
    weight_signal: float = 1.0
    weight_segmentation: float = 1.5


class TBHPDoseFinder:
    """Autonomous dose finding for tBHP oxidative stress."""
    
    def __init__(self, vm: BiologicalVirtualMachine, criteria: Optional[TBHPOptimizationCriteria] = None):
        self.vm = vm
        self.criteria = criteria or TBHPOptimizationCriteria()
        
    def run_dose_finding(self, cell_line: str, dose_range: Tuple[float, float] = (0.0, 500.0), 
                        n_doses: int = 12) -> TBHPDoseResult:
        """
        Run dose-response experiment and find optimal dose.
        
        Args:
            cell_line: Name of cell line (e.g., "U2OS")
            dose_range: (min_dose, max_dose) in µM
            n_doses: Number of dose points to test
            
        Returns:
            TBHPDoseResult with optimal dose and data
        """
        logger.info(f"Starting tBHP dose finding for {cell_line}")
        
        # 1. Generate dose grid (log-spaced + 0)
        doses = [0.0]
        log_min = np.log10(max(1.0, dose_range[0]))
        log_max = np.log10(dose_range[1])
        doses.extend(np.logspace(log_min, log_max, n_doses - 1))
        doses = sorted(list(set(doses)))
        
        results = []
        
        # 2. Run experiment for each dose
        # In a real lab, this would be a plate experiment.
        # Here we simulate parallel wells.
        
        for dose in doses:
            well_id = f"dose_finding_{cell_line}_{dose:.1f}"
            
            # Seed and grow
            self.vm.seed_vessel(well_id, cell_line, 10000)
            self.vm.incubate(24 * 3600, 37.0)  # Grow for 24h
            
            # Treat
            self.vm.treat_with_compound(well_id, "tbhp", dose)
            self.vm.incubate(24 * 3600, 37.0)  # Treat for 24h
            
            # Readouts
            state = self.vm.get_vessel_state(well_id)
            viability = state["viability"]
            cellrox = self.vm.simulate_cellrox_signal(well_id, "tbhp", dose)
            seg_quality = self.vm.simulate_segmentation_quality(well_id, "tbhp", dose)
            
            results.append({
                "dose_uM": dose,
                "viability": viability,
                "cellrox_signal": cellrox,
                "segmentation_quality": seg_quality
            })
            
            # Cleanup
            if well_id in self.vm.vessel_states:
                del self.vm.vessel_states[well_id]
                
        df = pd.DataFrame(results)
        
        # 3. Find optimal dose
        optimal_dose, status, metrics = self._select_optimal_dose(df)
        
        logger.info(f"Optimal tBHP dose for {cell_line}: {optimal_dose:.1f} µM ({status})")
        
        return TBHPDoseResult(
            cell_line=cell_line,
            optimal_dose_uM=optimal_dose,
            viability_at_optimal=metrics["viability"],
            cellrox_signal_at_optimal=metrics["cellrox_signal"],
            segmentation_quality_at_optimal=metrics["segmentation_quality"],
            dose_response_curve=df,
            status=status
        )
        
    def _select_optimal_dose(self, df: pd.DataFrame) -> Tuple[float, str, Dict[str, float]]:
        """Select the best dose based on criteria."""
        # Filter candidates meeting all hard constraints
        candidates = df[
            (df["viability"] >= self.criteria.min_viability) &
            (df["segmentation_quality"] >= self.criteria.min_segmentation_quality)
        ].copy()
        
        if not candidates.empty:
            # Among valid candidates, maximize CellROX signal
            # But prefer lower doses if signal is similar (parsimony)
            
            # Sort by signal descending
            candidates = candidates.sort_values("cellrox_signal", ascending=False)
            
            # Pick the one with highest signal
            best_row = candidates.iloc[0]
            
            # Check if signal target is met
            status = "success" if best_row["cellrox_signal"] >= self.criteria.target_cellrox_signal else "suboptimal_signal"
            
            return best_row["dose_uM"], status, best_row.to_dict()
            
        else:
            # No dose meets all criteria. Find best compromise.
            # Score = w_v * viability + w_s * signal_norm + w_q * quality
            
            # Normalize signal (cap at target)
            df["signal_norm"] = df["cellrox_signal"] / self.criteria.target_cellrox_signal
            df["signal_norm"] = df["signal_norm"].clip(upper=1.0)
            
            df["score"] = (
                self.criteria.weight_viability * df["viability"] +
                self.criteria.weight_signal * df["signal_norm"] +
                self.criteria.weight_segmentation * df["segmentation_quality"]
            )
            
            best_row = df.loc[df["score"].idxmax()]
            
            return best_row["dose_uM"], "failed_constraints", best_row.to_dict()
