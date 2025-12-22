"""
Single-cell RNA-seq assay simulator.

Simulates scRNA-seq with realistic batch effects, dropout, and technical noise.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime

from .base import AssaySimulator

if TYPE_CHECKING:
    from ..biological_virtual import VesselState

logger = logging.getLogger(__name__)


class ScRNASeqAssay(AssaySimulator):
    """
    Single-cell RNA-seq assay simulator.

    Returns UMI count matrix with realistic technical artifacts:
    - Dropout (low-expression genes randomly undetected)
    - Library size variation (UMIs per cell)
    - Batch effects (multiplicative per-gene biases, stronger than imaging)
    - Ambient RNA contamination
    - Subpopulation heterogeneity

    IMPORTANT: scRNA-seq has STRONGER batch effects than imaging. Modalities
    can disagree, forcing robust belief systems.
    """

    def measure(
        self,
        vessel: "VesselState",
        n_cells: int = 1000,
        batch_id: Optional[str] = None,
        params_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Simulate single-cell RNA-seq for a vessel.

        MEASUREMENT TIMING: Reads at t_measure = vm.simulated_time (after advance_time).

        Args:
            vessel: Vessel state to measure
            n_cells: Number of cells to profile (default 1000)
            batch_id: Optional batch identifier for batch effects
            params_path: Optional path to scrna_seq_params.yaml
            **kwargs: Additional parameters

        Returns:
            Dict with counts, metadata, and run information
        """
        # Lazy load transcriptomics module
        from ..transcriptomics import simulate_scrna_counts

        # Lock measurement purity
        state_before = (vessel.cell_count, vessel.viability, vessel.confluence)

        vessel_id = vessel.vessel_id
        cell_line = vessel.cell_line

        # Default params path
        if params_path is None:
            params_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "scrna_seq_params.yaml"

        # Map vessel latent states to transcriptomics program names
        vessel_latents = {
            "er_stress": float(vessel.er_stress),
            "mito_dysfunction": float(vessel.mito_dysfunction),
            "transport_dysfunction": float(vessel.transport_dysfunction),
            # Placeholder latents (not tracked yet, but gene programs exist)
            "oxidative_stress": 0.0,
            "dna_damage": 0.0,
            # Contact pressure (measurement confounder)
            "contact_inhibition": float(getattr(vessel, "contact_pressure", 0.0)),
        }

        # Extract subpopulation fractions
        subpop_fractions = {
            name: float(subpop['fraction'])
            for name, subpop in vessel.subpopulations.items()
        }

        # Couple to RunContext for correlated batch drift
        run_context_latent = None
        if hasattr(self.vm, "run_context") and self.vm.run_context is not None:
            run_context_latent = float(hash(self.vm.run_context.context_id) % 1000) / 1000.0 - 0.5

        # Use assay RNG for observer independence
        result = simulate_scrna_counts(
            cell_line=cell_line,
            vessel_latents=vessel_latents,
            viability=float(vessel.viability),
            n_cells=n_cells,
            rng=self.vm.rng_assay,
            params_path=str(params_path),
            batch_id=batch_id if batch_id is not None else "default",
            subpop_fractions=subpop_fractions,
            run_context_latent=run_context_latent,
        )

        # Load cost model from params
        with open(params_path) as f:
            params = yaml.safe_load(f)

        costs = params.get("costs", {})
        time_cost_h = float(costs.get("time_cost_h", 4.0))
        reagent_cost_usd = float(costs.get("reagent_cost_usd", 200.0))
        min_cells = int(costs.get("min_cells", 500))
        soft_penalty = float(costs.get("soft_penalty_if_underpowered", 0.25))

        is_underpowered = (n_cells < min_cells)

        # Apply cost inflation from epistemic debt (if enabled)
        actual_cost_usd = reagent_cost_usd
        cost_multiplier = 1.0
        epistemic_debt = 0.0

        if self.vm.epistemic_controller is not None:
            actual_cost_usd = self.vm.epistemic_controller.get_inflated_cost(reagent_cost_usd)
            cost_multiplier = self.vm.epistemic_controller.get_cost_multiplier()
            epistemic_debt = self.vm.epistemic_controller.get_total_debt()

        # Apply time cost
        self.vm._simulate_delay(time_cost_h)

        # Assert measurement purity
        self._assert_measurement_purity(vessel, state_before)

        return {
            "status": "success",
            "action": "scrna_seq",
            "vessel_id": vessel_id,
            "cell_line": cell_line,
            "gene_names": result.gene_names,
            "cell_ids": result.cell_ids,
            "counts": result.counts,  # numpy array (n_cells, n_genes), int32
            "meta": result.meta,
            "n_cells": len(result.cell_ids),
            "n_genes": len(result.gene_names),
            "timestamp": datetime.now().isoformat(),
            # Batch metadata for epistemic control
            "batch_id": batch_id,
            "run_context_id": self.vm.run_context.context_id if hasattr(self.vm, "run_context") else None,
            # Cost model
            "time_cost_h": time_cost_h,
            "reagent_cost_usd": reagent_cost_usd,
            "actual_cost_usd": actual_cost_usd,
            "cost_multiplier": cost_multiplier,
            "epistemic_debt": epistemic_debt,
            "min_cells_required": min_cells,
            "is_underpowered": is_underpowered,
            "soft_penalty_if_underpowered": soft_penalty if is_underpowered else 0.0,
        }
