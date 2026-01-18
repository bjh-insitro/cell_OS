"""
Cell Painting Result Schema and Summary View.

Defines the expected structure of Cell Painting assay results and provides
utilities for validation and visualization.

Phase 0 Context: The schema captures all fields needed for go/no-go analysis:
- Core morphology channels (ER, Mito, Nucleus, Actin, RNA)
- Morphology regime weights (stress vs death signature interpolation)
- Quality metrics (segmentation, debris, artifacts)
- Timepoint sensitivity (onset kinetics)
"""

from dataclasses import dataclass
from typing import Any, TypedDict

# ═══════════════════════════════════════════════════════════════════════════════
# RESULT SCHEMA (TypedDict for type checking)
# ═══════════════════════════════════════════════════════════════════════════════


class MorphologyChannels(TypedDict):
    """5-channel morphology feature values."""

    er: float
    mito: float
    nucleus: float
    actin: float
    rna: float


class MorphRegime(TypedDict):
    """Morphology regime weights (stress vs death signature interpolation)."""

    stress_weight: float  # [0,1] - high when viability > collapse threshold
    death_weight: float  # [0,1] - high when viability < collapse threshold (= 1 - stress_weight)
    onset_factor: float  # [0.2,1] - increases with time since treatment
    collapse_threshold: float  # Viability threshold for regime transition
    onset_tau_h: float  # Characteristic time for onset kinetics


class DetectorMetadata(TypedDict, total=False):
    """Detector physics metadata (saturation, quantization, SNR)."""

    is_saturated: dict[str, bool]  # Per-channel saturation flags
    is_quantized: dict[str, bool]  # Per-channel quantization flags
    quant_step: dict[str, float]  # Per-channel quantization step size
    snr_floor_proxy: dict[str, float | None]  # Per-channel SNR estimate
    exposure_multiplier: float  # Agent-controlled exposure setting
    edge_distance: float  # Distance from well edge [0,1]
    qc_flags: dict[str, Any]  # QC pathology flags


class CellPaintingResult(TypedDict, total=False):
    """
    Complete Cell Painting assay result schema.

    Required fields (always present):
    - status, action, vessel_id, cell_line
    - morphology (backward-compatible alias for morphology_measured)
    - morph_regime (stress/death weights, onset factor)

    Optional fields (conditionally present):
    - well_failure, qc_flag (only if failure detected)
    - segmentation_* fields (only if segmentation enabled)
    - imaging_artifacts (only if structured artifacts enabled)
    """

    # Core identification
    status: str  # "success" or error status
    action: str  # "cell_painting"
    vessel_id: str  # Well identifier
    cell_line: str  # Cell line name

    # Morphology outputs
    morphology: MorphologyChannels  # Measured morphology (backward compatible)
    morphology_struct: MorphologyChannels  # Structural morphology (pre-viability scaling)
    morphology_measured: MorphologyChannels  # Post-measurement-layer morphology

    # Signal and dysfunction scores
    signal_intensity: float  # [0,1] overall signal strength
    transport_dysfunction_score: float  # Inferred transport dysfunction

    # Temporal metadata
    timestamp: str  # ISO timestamp

    # Pipeline context
    run_context_id: str  # Run context identifier
    batch_id: str  # Batch identifier
    plate_id: str  # Plate identifier
    measurement_modifiers: dict[str, Any]  # Pipeline drift modifiers

    # Detector metadata
    detector_metadata: DetectorMetadata

    # Morphology regime (Phase 0.2: stress vs death signatures)
    morph_regime: MorphRegime

    # Quality metrics (from _compute_cp_quality_metrics)
    debris_load: float  # [0,1] debris as fraction of live cells
    handling_loss_fraction: float  # [0,1] cells lost to handling
    cp_quality: float  # [0,1] overall CP quality score
    segmentation_yield: float  # [0,1] fraction successfully segmented
    n_segmented: int  # Effective segmented cell count
    noise_mult: float  # Noise inflation multiplier
    artifact_level: int  # Step-like artifact indicator (0-3)

    # Optional: Failure modes
    well_failure: str  # Failure mode name (if failed)
    qc_flag: str  # QC flag (if failed)

    # Optional: Segmentation details
    cell_count_estimated: int  # Estimated cell count
    cell_count_observed: int  # Observed after segmentation
    segmentation_quality: float  # [0,1] segmentation quality
    segmentation_qc_passed: bool  # Whether QC passed
    segmentation_warnings: list  # List of warnings
    merge_count: int  # Cells lost to merging
    split_count: int  # Cells added by splitting
    size_bias: float  # Size selection bias

    # Optional: Imaging artifacts
    imaging_artifacts: dict[str, Any] | None


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

REQUIRED_FIELDS = frozenset(
    {
        "status",
        "action",
        "vessel_id",
        "cell_line",
        "morphology",
        "morph_regime",
    }
)

MORPHOLOGY_CHANNELS = frozenset({"er", "mito", "nucleus", "actin", "rna"})


def validate_result(result: dict[str, Any]) -> list[str]:
    """
    Validate a Cell Painting result against the schema.

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in result:
            errors.append(f"Missing required field: {field}")

    # Check morphology channels
    if "morphology" in result:
        morph = result["morphology"]
        if not isinstance(morph, dict):
            errors.append(f"morphology should be dict, got {type(morph)}")
        else:
            missing_channels = MORPHOLOGY_CHANNELS - set(morph.keys())
            if missing_channels:
                errors.append(f"Missing morphology channels: {missing_channels}")

            # Check for non-negative values
            for ch, val in morph.items():
                if ch in MORPHOLOGY_CHANNELS and val < 0:
                    errors.append(f"Negative morphology value: {ch}={val}")

    # Check morph_regime
    if "morph_regime" in result:
        regime = result["morph_regime"]
        if not isinstance(regime, dict):
            errors.append(f"morph_regime should be dict, got {type(regime)}")
        else:
            for field in ["stress_weight", "death_weight", "onset_factor"]:
                if field not in regime:
                    errors.append(f"Missing morph_regime field: {field}")
                elif regime[field] is not None:
                    val = regime[field]
                    if not (0 <= val <= 1):
                        errors.append(f"morph_regime.{field} out of bounds: {val}")

            # Check complementary weights
            sw = regime.get("stress_weight")
            dw = regime.get("death_weight")
            if sw is not None and dw is not None:
                if abs(sw + dw - 1.0) > 1e-5:
                    errors.append(f"Weights don't sum to 1: stress={sw}, death={dw}")

    return errors


# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS VIEW (Summary)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CellPaintingSummary:
    """Summary view of Cell Painting result for debugging/analysis."""

    vessel_id: str
    cell_line: str
    status: str

    # Morphology summary
    morph_mean: float
    morph_cv: float
    dominant_channel: str
    suppressed_channel: str

    # Regime state
    stress_weight: float
    death_weight: float
    onset_factor: float
    regime_label: str  # "stress", "death", or "transition"

    # Quality
    cp_quality: float
    segmentation_yield: float
    qc_passed: bool

    def __str__(self) -> str:
        """Pretty-print summary."""
        lines = [
            f"═══ Cell Painting Summary: {self.vessel_id} ═══",
            f"Cell line: {self.cell_line}",
            f"Status: {self.status}",
            "",
            "Morphology:",
            f"  Mean signal: {self.morph_mean:.2f}",
            f"  CV: {self.morph_cv:.1%}",
            f"  Dominant: {self.dominant_channel}",
            f"  Suppressed: {self.suppressed_channel}",
            "",
            f"Regime: {self.regime_label}",
            f"  Stress weight: {self.stress_weight:.3f}",
            f"  Death weight: {self.death_weight:.3f}",
            f"  Onset factor: {self.onset_factor:.3f}",
            "",
            "Quality:",
            f"  CP quality: {self.cp_quality:.1%}",
            f"  Segmentation yield: {self.segmentation_yield:.1%}",
            f"  QC passed: {'✓' if self.qc_passed else '✗'}",
        ]
        return "\n".join(lines)


def summarize_result(result: dict[str, Any]) -> CellPaintingSummary:
    """
    Create a summary view of a Cell Painting result.

    Args:
        result: Cell Painting assay result dict

    Returns:
        CellPaintingSummary with key metrics
    """
    import numpy as np

    morph = result.get("morphology", {})
    regime = result.get("morph_regime", {})

    # Compute morphology stats
    morph_values = [v for v in morph.values() if isinstance(v, int | float)]
    morph_mean = float(np.mean(morph_values)) if morph_values else 0.0
    morph_std = float(np.std(morph_values)) if morph_values else 0.0
    morph_cv = morph_std / morph_mean if morph_mean > 0 else 0.0

    # Find dominant/suppressed channels
    if morph:
        sorted_channels = sorted(morph.items(), key=lambda x: x[1], reverse=True)
        dominant = sorted_channels[0][0] if sorted_channels else "N/A"
        suppressed = sorted_channels[-1][0] if sorted_channels else "N/A"
    else:
        dominant = suppressed = "N/A"

    # Regime weights
    stress_weight = regime.get("stress_weight", 0.0) or 0.0
    death_weight = regime.get("death_weight", 0.0) or 0.0
    onset_factor = regime.get("onset_factor", 1.0) or 1.0

    # Determine regime label
    if stress_weight > 0.9:
        regime_label = "stress"
    elif death_weight > 0.9:
        regime_label = "death"
    else:
        regime_label = "transition"

    # Quality metrics
    cp_quality = result.get("cp_quality", 1.0)
    segmentation_yield = result.get("segmentation_yield", 1.0)
    qc_passed = result.get("segmentation_qc_passed", True) and result.get("qc_flag") != "FAIL"

    return CellPaintingSummary(
        vessel_id=result.get("vessel_id", "N/A"),
        cell_line=result.get("cell_line", "N/A"),
        status=result.get("status", "N/A"),
        morph_mean=morph_mean,
        morph_cv=morph_cv,
        dominant_channel=dominant,
        suppressed_channel=suppressed,
        stress_weight=stress_weight,
        death_weight=death_weight,
        onset_factor=onset_factor,
        regime_label=regime_label,
        cp_quality=cp_quality,
        segmentation_yield=segmentation_yield,
        qc_passed=qc_passed,
    )
