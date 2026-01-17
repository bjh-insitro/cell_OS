"""
Cytotoxicity assay simulators.

Models dead-cell biomarker release (proteases, LDH, etc.) into supernatant.
The underlying model tracks `cytotox_released_since_feed` - accumulated dead cell
biomass since last media change. This is agnostic to the specific measurement kit:
- CytoTox-Glo: Dead-cell protease activity (AAF-Glo substrate)
- LDH-Glo: Lactate dehydrogenase release
- Other cytotoxicity kits

Also returns orthogonal scalar readouts:
- ATP signal (metabolic state / mito dysfunction proxy)
- UPR marker (ER stress proxy)
- Trafficking marker (transport dysfunction proxy)
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict

import numpy as np

from ...contracts import LDH_VIABILITY_CONTRACT, enforce_measurement_contract
from .._impl import lognormal_multiplier, stable_u32
from ..constants import (
    ENABLE_INTERVENTION_COSTS,
    WASHOUT_INTENSITY_PENALTY,
    WASHOUT_INTENSITY_RECOVERY_H,
)
from .assay_params import DEFAULT_ASSAY_PARAMS
from .base import AssaySimulator

if TYPE_CHECKING:
    from ..biological_virtual import VesselState

logger = logging.getLogger(__name__)


class CytotoxAssay(AssaySimulator):
    """
    Cytotoxicity assay simulator (kit-agnostic).

    Models dead-cell biomarker release into supernatant. The underlying biology
    is membrane permeabilization releasing intracellular contents (proteases, LDH, etc.).

    The model tracks `cytotox_released_since_feed` - cumulative dead cell biomass
    since last media change. This is cleared when media is changed (aspirated out).

    Compatible with multiple measurement kits:
    - CytoTox-Glo: Dead-cell protease activity (AAF-Glo substrate, luminescence)
    - LDH-Glo: Lactate dehydrogenase release (luminescence)
    - CytoTox 96: LDH release (colorimetric)

    Also returns additional scalar markers:
    - ATP signal (metabolic state / mito dysfunction proxy)
    - UPR marker (ER stress proxy)
    - Trafficking marker (transport dysfunction proxy)

    Cytotox signal is INVERSELY proportional to viability:
    - High viability → Low cytotox signal (few dead cells)
    - Low viability → High cytotox signal (many dead cells releasing biomarkers)
    """

    @enforce_measurement_contract(LDH_VIABILITY_CONTRACT)
    def measure(self, vessel: "VesselState", **kwargs) -> dict[str, Any]:
        """
        Simulate cytotoxicity assay (supernatant-based, kit-agnostic).

        MEASUREMENT TIMING: Reads at t_measure = vm.simulated_time (after advance_time).

        Args:
            vessel: Vessel state to measure
            **kwargs: Additional parameters (plate_id, day, operator, well_position)

        Returns:
            Dict with cytotox_signal, atp_signal, upr_marker, trafficking_marker and metadata
        """
        # Lock measurement purity
        state_before = (vessel.viability, vessel.confluence)

        # Lazy load thalamus params
        if not hasattr(self.vm, "thalamus_params") or self.vm.thalamus_params is None:
            self.vm._load_cell_thalamus_params()

        vessel_id = vessel.vessel_id
        cell_line = vessel.cell_line

        # Get baseline cytotox signal for this cell line
        baseline_cytotox = self.vm.thalamus_params["baseline_atp"].get(cell_line, 50000.0)

        # Cytotoxicity signal scales with accumulated dead cell biomass since last media change
        # cytotox_released_since_feed tracks cumulative death fraction since last feed
        # Kit-agnostic: works for CytoTox-Glo (protease), LDH-Glo, or other cytotox kits
        # Media change clears this (old media with signal is aspirated out)
        cytotox_accumulated = getattr(vessel, "cytotox_released_since_feed", 0.0)

        # Fallback for vessels without the new field: use instantaneous death fraction
        if cytotox_accumulated <= 0.0:
            cytotox_accumulated = 1.0 - vessel.viability

        # Use death amplification factor (nonlinear scaling)
        # ASSUMPTION: Death amplification capped to prevent explosion. See assay_params.py
        death_amplification = cytotox_accumulated / max(0.1, 1.0 - cytotox_accumulated)
        death_amplification = min(
            death_amplification, DEFAULT_ASSAY_PARAMS.LDH_DEATH_AMPLIFICATION_CAP
        )

        cell_count_factor = vessel.cell_count / 1e6  # Normalize to 1M cells
        cytotox_signal = baseline_cytotox * cell_count_factor * death_amplification

        # Biological noise (dose-dependent)
        cytotox_signal = self._add_biological_noise(vessel, cytotox_signal)

        # Measurement layer
        t_measure = self.vm.simulated_time
        washout_multiplier = self._compute_washout_multiplier(vessel, t_measure)
        cytotox_signal *= washout_multiplier

        # Technical noise (use 'LDH' bias key for backward compatibility with run_context)
        cytotox_signal, failure_mode, qc_flag = self._add_technical_noise(
            vessel, cytotox_signal, "LDH", **kwargs
        )

        # UPR marker (ER stress proxy) - scales linearly with ER stress
        upr_marker = self._compute_upr_marker(vessel, washout_multiplier, **kwargs)

        # ATP signal (mito dysfunction proxy) - decreases with dysfunction
        atp_signal = self._compute_atp_signal(vessel, washout_multiplier, **kwargs)

        # Trafficking marker (transport dysfunction proxy) - increases with dysfunction
        trafficking_marker = self._compute_trafficking_marker(vessel, washout_multiplier, **kwargs)

        # Simulate delay
        self.vm._simulate_delay(0.5)

        # Assert measurement purity
        self._assert_measurement_purity(vessel, state_before)

        result = {
            "status": "success",
            "action": "cytotox_assay",
            "vessel_id": vessel_id,
            "cell_line": cell_line,
            "cytotox_signal": cytotox_signal,
            "ldh_signal": cytotox_signal,  # Backward compatibility alias
            "atp_signal": atp_signal,
            "upr_marker": upr_marker,
            "trafficking_marker": trafficking_marker,
            "timestamp": datetime.now().isoformat(),
        }

        # Ground truth only when debug enabled
        if getattr(self.vm.run_context, "debug_truth_enabled", False):
            result["_debug_truth"] = {
                "viability": float(vessel.viability),
                "cell_count": float(vessel.cell_count),
                "death_mode": getattr(vessel, "death_mode", None),
                "death_compound": getattr(vessel, "death_compound", None),
                "death_confluence": getattr(vessel, "death_confluence", None),
                "death_unknown": getattr(vessel, "death_unknown", None),
            }

        if failure_mode:
            result["well_failure"] = failure_mode
            result["qc_flag"] = qc_flag

        return result

    def _add_biological_noise(self, vessel: "VesselState", signal: float) -> float:
        """Add dose-dependent biological noise."""
        stress_level = 1.0 - vessel.viability
        bio_cfg = self.vm.thalamus_params.get("biological_noise", {})
        stress_multiplier = bio_cfg.get("stress_cv_multiplier", 1.0)
        base_cell_line_cv = bio_cfg.get("cell_line_cv", 0.04)
        effective_bio_cv = base_cell_line_cv * (1.0 + stress_level * (stress_multiplier - 1.0))

        if effective_bio_cv > 0:
            signal *= lognormal_multiplier(self.vm.rng_assay, effective_bio_cv)

        return signal

    def _compute_washout_multiplier(self, vessel: "VesselState", t_measure: float) -> float:
        """Compute washout artifact multiplier."""
        washout_multiplier = 1.0

        if ENABLE_INTERVENTION_COSTS and vessel.last_washout_time is not None:
            time_since_washout = t_measure - vessel.last_washout_time
            if time_since_washout < WASHOUT_INTENSITY_RECOVERY_H:
                recovery_fraction = time_since_washout / WASHOUT_INTENSITY_RECOVERY_H
                washout_penalty = WASHOUT_INTENSITY_PENALTY * (1.0 - recovery_fraction)
                washout_multiplier *= 1.0 - washout_penalty

        # Stochastic contamination artifact
        if vessel.washout_artifact_until_time and t_measure < vessel.washout_artifact_until_time:
            remaining_time = vessel.washout_artifact_until_time - t_measure
            decay_fraction = remaining_time / WASHOUT_INTENSITY_RECOVERY_H
            artifact_effect = vessel.washout_artifact_magnitude * decay_fraction
            washout_multiplier *= 1.0 - artifact_effect

        return washout_multiplier

    def _add_technical_noise(
        self, vessel: "VesselState", signal: float, assay_name: str, **kwargs
    ) -> tuple[float, str, str]:
        """Add technical noise and apply well failures."""
        tech_noise = self.vm.thalamus_params["technical_noise"]

        plate_id = kwargs.get("plate_id", "P1")
        batch_id = kwargs.get("batch_id", "batch_default")
        day = kwargs.get("day", 1)
        operator = kwargs.get("operator", "OP1")
        well_position = kwargs.get("well_position", "A1")

        # Deterministic batch effects
        plate_cv = tech_noise["plate_cv"]
        day_cv = tech_noise["day_cv"]
        operator_cv = tech_noise["operator_cv"]

        plate_factor = self._get_batch_factor("plate", plate_id, batch_id, plate_cv)
        day_factor = self._get_batch_factor("day", day, batch_id, day_cv)
        operator_factor = self._get_batch_factor("op", operator, batch_id, operator_cv)

        # Non-deterministic well factor
        well_cv = tech_noise["well_cv"]
        well_factor = lognormal_multiplier(self.vm.rng_assay, well_cv) if well_cv > 0 else 1.0

        # Edge effect
        edge_effect = tech_noise.get("edge_effect", 0.0)
        is_edge = self._is_edge_well(well_position)
        edge_factor = (1.0 - edge_effect) if is_edge else 1.0

        # Run context modifiers (reader gain + kit lot effects + temporal drift)
        # Pass t_measure and modality='reader' for time-dependent drift
        t_measure = self.vm.simulated_time
        meas_mods = self.vm.run_context.get_measurement_modifiers(t_measure, modality="reader")
        gain = meas_mods["gain"]  # Includes batch effect + temporal drift
        scalar_assay_biases = meas_mods["scalar_assay_biases"]

        # CANONICAL GAIN APPLICATION: gain applied exactly once here (includes batch + drift)
        total_tech_factor = (
            plate_factor * day_factor * operator_factor * well_factor * edge_factor * gain
        )
        signal *= total_tech_factor * scalar_assay_biases[assay_name]
        signal = max(0.0, signal)

        # Apply well failures
        failure_mode = None
        qc_flag = None
        failure_rate = tech_noise.get("well_failure_rate", 0.0)
        if failure_rate > 0:
            rng_failure = np.random.default_rng(
                stable_u32(
                    f"well_failure_{self.vm.run_context.seed}_{batch_id}_{plate_id}_{well_position}"
                )
            )
            if rng_failure.random() <= failure_rate:
                signal *= rng_failure.choice([0.01, 0.05, 0.1, 5.0, 10.0, 20.0])
                failure_mode = "assay_failure"
                qc_flag = "FAIL"

        return signal, failure_mode, qc_flag

    def _get_batch_factor(self, prefix: str, identifier: Any, batch_id: str, cv: float) -> float:
        """Get deterministic batch effect factor."""
        if cv <= 0:
            return 1.0
        rng = np.random.default_rng(
            stable_u32(f"{prefix}_{self.vm.run_context.seed}_{batch_id}_{identifier}")
        )
        return lognormal_multiplier(rng, cv)

    def _is_edge_well(self, well_position: str) -> bool:
        """Detect if well is on plate edge (384-well format)."""
        import re

        match = re.search(r"([A-P])(\d{1,2})$", well_position)
        if not match:
            return False
        row = match.group(1)
        col = int(match.group(2))
        return row in ["A", "P"] or col in [1, 24]

    def _compute_upr_marker(
        self, vessel: "VesselState", washout_multiplier: float, **kwargs
    ) -> float:
        """Compute UPR marker (ER stress proxy)."""
        baseline_upr = 100.0
        upr_marker = baseline_upr * (1.0 + 2.0 * vessel.er_stress)

        # Biological noise
        upr_marker = self._add_biological_noise(vessel, upr_marker)

        # Washout artifact
        upr_marker *= washout_multiplier

        # Technical noise
        upr_marker, _, _ = self._add_technical_noise(vessel, upr_marker, "UPR", **kwargs)

        return upr_marker

    def _compute_atp_signal(
        self, vessel: "VesselState", washout_multiplier: float, **kwargs
    ) -> float:
        """Compute ATP signal (mito dysfunction proxy)."""
        # ASSUMPTION: ATP floor from basal/non-mito sources. See assay_params.py
        baseline_atp = 100.0
        atp_signal = baseline_atp * max(
            DEFAULT_ASSAY_PARAMS.ATP_SIGNAL_FLOOR, 1.0 - 0.7 * vessel.mito_dysfunction
        )

        # Biological noise
        atp_signal = self._add_biological_noise(vessel, atp_signal)

        # Washout artifact
        atp_signal *= washout_multiplier

        # Technical noise
        atp_signal, _, _ = self._add_technical_noise(vessel, atp_signal, "ATP", **kwargs)

        return atp_signal

    def _compute_trafficking_marker(
        self, vessel: "VesselState", washout_multiplier: float, **kwargs
    ) -> float:
        """Compute trafficking marker (transport dysfunction proxy)."""
        baseline_trafficking = 100.0
        trafficking_marker = baseline_trafficking * (1.0 + 1.5 * vessel.transport_dysfunction)

        # Biological noise
        trafficking_marker = self._add_biological_noise(vessel, trafficking_marker)

        # Washout artifact
        trafficking_marker *= washout_multiplier

        # Technical noise
        trafficking_marker, _, _ = self._add_technical_noise(
            vessel, trafficking_marker, "TRAFFICKING", **kwargs
        )

        return trafficking_marker
