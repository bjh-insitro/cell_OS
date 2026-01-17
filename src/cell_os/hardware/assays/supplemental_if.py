"""
Supplemental IF (Immunofluorescence) Assay Simulator.

This assay simulates supplemental IF channels that complement core Cell Painting.
Unlike the standardized 5-channel Cell Painting assay, supplemental IF channels
are stress-specific biomarkers added when needed for particular experiments.

Example use cases:
- γ-H2AX for DNA damage detection (Phase 0 Thalamus)
- LC3 for autophagy monitoring
- Cleaved Caspase-3 for apoptosis

Design:
- Separate from CellPaintingAssay to maintain Cell Painting as standardized
- Uses same technical noise model for consistency
- Biomarker-specific signal models via the biomarkers registry
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import numpy as np

from .._impl import lognormal_multiplier, stable_u32
from ..biomarkers import BiomarkerRegistry, GammaH2AXModel
from .base import AssaySimulator

if TYPE_CHECKING:
    from ..biological_virtual import VesselState

logger = logging.getLogger(__name__)


class SupplementalIFAssay(AssaySimulator):
    """
    Supplemental IF assay simulator.

    Simulates antibody-based or probe-based IF channels that complement
    core Cell Painting. Each measurement specifies which biomarkers to include.

    Technical noise model matches Cell Painting for consistency:
    - Plate/day/operator effects
    - Well-to-well variation
    - Edge effects
    - Batch effects via run context

    Biomarker-specific signal models handle the biological response:
    - γ-H2AX: DNA damage → phosphorylated H2AX foci
    - LC3: ER/mito stress → autophagosome formation (future)
    """

    def __init__(self, vm):
        """
        Initialize Supplemental IF Assay.

        Args:
            vm: BiologicalVirtualMachine instance
        """
        super().__init__(vm)
        self.registry = BiomarkerRegistry()

    def measure(
        self, vessel: "VesselState", markers: list[str] | None = None, **kwargs
    ) -> dict[str, Any]:
        """
        Simulate supplemental IF measurement.

        Args:
            vessel: Vessel state to measure
            markers: List of biomarker IDs to measure (e.g., ["gamma_h2ax"])
                    If None, uses markers suggested by compound stress axes
            **kwargs: Additional parameters (plate_id, day, operator, well_position)

        Returns:
            Dict with:
                - status: "success" or "failure"
                - markers: Dict mapping marker_id to marker-specific results
                - timestamp: Measurement time
                - technical_factors: Applied technical noise factors
        """
        # Lock measurement purity
        state_before = (vessel.viability, vessel.confluence)

        # Lazy load thalamus params for technical noise
        if not hasattr(self.vm, "thalamus_params") or self.vm.thalamus_params is None:
            self.vm._load_cell_thalamus_params()

        vessel_id = vessel.vessel_id
        cell_line = vessel.cell_line

        # Determine which markers to measure
        if markers is None:
            # Auto-suggest based on compounds
            if vessel.compounds and self.vm.thalamus_params:
                compound_params = self.vm.thalamus_params.get("compounds", {})
                markers = self.registry.suggest_biomarkers_for_compounds(
                    list(vessel.compounds.keys()), compound_params
                )
            else:
                markers = []

        if not markers:
            # No markers requested or suggested
            return {
                "status": "success",
                "action": "supplemental_if",
                "vessel_id": vessel_id,
                "cell_line": cell_line,
                "markers": {},
                "message": "No markers requested",
                "timestamp": datetime.now().isoformat(),
            }

        # Compute technical noise factors (shared across markers)
        tech_factors = self._compute_technical_factors(**kwargs)

        # Create per-measurement RNG
        plate_id = kwargs.get("plate_id", "P1")
        well_position = kwargs.get("well_position", "A1")
        rng_seed = stable_u32(
            f"supplemental_if_{self.vm.run_context.seed}_{plate_id}_{well_position}"
        )
        rng = np.random.default_rng(rng_seed)

        # Measure each marker
        marker_results = {}
        for marker_id in markers:
            model = self.registry.get_model(marker_id)
            if model is None:
                logger.warning(f"Unknown biomarker: {marker_id}")
                marker_results[marker_id] = {
                    "status": "error",
                    "error": f"Unknown biomarker: {marker_id}",
                }
                continue

            # Get marker-specific result
            try:
                marker_data = model.compute_signal(
                    vessel=vessel, rng=rng, plate_id=plate_id, well_position=well_position, **kwargs
                )

                # Apply shared technical factors to intensity values
                if "mean_intensity" in marker_data:
                    marker_data["mean_intensity"] *= tech_factors["combined"]
                if "median_intensity" in marker_data:
                    marker_data["median_intensity"] *= tech_factors["combined"]
                if "p95_intensity" in marker_data:
                    marker_data["p95_intensity"] *= tech_factors["combined"]
                if "nuclear_intensities" in marker_data:
                    marker_data["nuclear_intensities"] = (
                        marker_data["nuclear_intensities"] * tech_factors["combined"]
                    )

                marker_data["status"] = "success"
                marker_results[marker_id] = marker_data

            except Exception as e:
                logger.error(f"Error measuring {marker_id}: {e}")
                marker_results[marker_id] = {"status": "error", "error": str(e)}

        # Simulate delay
        self.vm._simulate_delay(1.5)  # Faster than full Cell Painting

        # Assert measurement purity
        self._assert_measurement_purity(vessel, state_before)

        return {
            "status": "success",
            "action": "supplemental_if",
            "vessel_id": vessel_id,
            "cell_line": cell_line,
            "markers": marker_results,
            "markers_requested": markers,
            "technical_factors": {
                "plate_factor": tech_factors["plate"],
                "day_factor": tech_factors["day"],
                "operator_factor": tech_factors["operator"],
                "well_factor": tech_factors["well"],
                "edge_factor": tech_factors["edge"],
                "combined": tech_factors["combined"],
            },
            "timestamp": datetime.now().isoformat(),
            "run_context_id": self.vm.run_context.context_id,
        }

    def _compute_technical_factors(self, **kwargs) -> dict[str, float]:
        """
        Compute technical noise factors (matches Cell Painting model).

        Args:
            **kwargs: plate_id, batch_id, day, operator, well_position

        Returns:
            Dict with individual and combined factors
        """
        tech_noise = self.vm.thalamus_params.get("technical_noise", {})

        plate_id = kwargs.get("plate_id", "P1")
        batch_id = kwargs.get("batch_id", "batch_default")
        day = kwargs.get("day", 1)
        operator = kwargs.get("operator", "OP1")
        well_position = kwargs.get("well_position", "A1")

        # Deterministic batch effects
        plate_cv = tech_noise.get("plate_cv", 0.01)
        day_cv = tech_noise.get("day_cv", 0.015)
        operator_cv = tech_noise.get("operator_cv", 0.008)

        plate_factor = self._get_batch_factor("plate", plate_id, batch_id, plate_cv)
        day_factor = self._get_batch_factor("day", day, batch_id, day_cv)
        operator_factor = self._get_batch_factor("op", operator, batch_id, operator_cv)

        # Non-deterministic well factor
        well_cv = tech_noise.get("well_cv", 0.015)
        well_factor = lognormal_multiplier(self.vm.rng_assay, well_cv) if well_cv > 0 else 1.0

        # Edge effect
        edge_effect = tech_noise.get("edge_effect", 0.12)
        is_edge = self._is_edge_well(well_position)
        edge_factor = (1.0 - edge_effect) if is_edge else 1.0

        # Combined factor
        combined = plate_factor * day_factor * operator_factor * well_factor * edge_factor

        return {
            "plate": plate_factor,
            "day": day_factor,
            "operator": operator_factor,
            "well": well_factor,
            "edge": edge_factor,
            "combined": combined,
        }

    def _get_batch_factor(self, prefix: str, identifier: Any, batch_id: str, cv: float) -> float:
        """Get deterministic batch effect factor."""
        if cv <= 0:
            return 1.0
        rng = np.random.default_rng(
            stable_u32(f"{prefix}_{self.vm.run_context.seed}_{batch_id}_{identifier}")
        )
        return lognormal_multiplier(rng, cv)

    def _is_edge_well(self, well_position: str, plate_format: int = 384) -> bool:
        """Detect if well is on plate edge."""
        import re

        match = re.search(r"([A-P])(\d{1,2})$", well_position)
        if not match:
            return False

        row = match.group(1)
        col = int(match.group(2))

        if plate_format == 384:
            return row in ["A", "P"] or col in [1, 24]
        elif plate_format == 96:
            return row in ["A", "H"] or col in [1, 12]
        return False
