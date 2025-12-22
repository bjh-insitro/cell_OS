"""
Acquisition Planner - Next Experiment Generation

Plans next experiment with sentinels + boundary-targeted experimental wells.
Includes utility functions for integration testing and batch frame construction.
"""

import numpy as np
from typing import List, Dict, Optional, Literal
import logging

from .types import WellRecord, SentinelSpec, BatchFrame, ConditionKey
from .anchor_budgeter import AnchorBudgeter
from .band_selector import BoundaryBandSelector
from .boundary_model import BoundaryModel

logger = logging.getLogger(__name__)


class AcquisitionPlanner:
    """
    Plan next experiment: sentinels + boundary-targeted experimental wells.
    """

    def __init__(
        self,
        anchor_budgeter: AnchorBudgeter,
        boundary_selector: BoundaryBandSelector
    ):
        self.anchor_budgeter = anchor_budgeter
        self.boundary_selector = boundary_selector

    def plan(
        self,
        candidate_conditions: List[ConditionKey],
        phase1_metrics: Dict,
        boundary_scores: Dict[ConditionKey, float],
        plate_format: int,
        batch_id: str,
        policy: Optional[Dict] = None
    ) -> Dict:
        """
        Generate experiment plan with sentinels + boundary-targeted wells.

        Args:
            candidate_conditions: Conditions to consider
            phase1_metrics: Covariance traces, SNR, death flags, etc.
            boundary_scores: Per-condition boundary scores
            plate_format: Number of wells (96, 384)
            batch_id: Batch identifier
            policy: Allocation policy (boundary vs trajectory fill)

        Returns:
            ExperimentPlan with sentinel_plan, experimental_plan, expected_rewards
        """
        policy = policy or {}
        boundary_frac = policy.get("boundary_frac", 0.6)
        trajectory_frac = policy.get("trajectory_frac", 0.4)
        sentinel_frac = policy.get("sentinel_frac", 0.31)

        # 1) Allocate sentinels
        sentinel_plan = self.anchor_budgeter.allocate(
            plate_format=plate_format,
            reserved_frac=sentinel_frac,
            batch_id=batch_id
        )

        n_experimental = sentinel_plan["n_experimental_wells"]

        # 2) Allocate experimental wells
        n_boundary_wells = int(n_experimental * boundary_frac)
        n_trajectory_wells = n_experimental - n_boundary_wells

        # Rank conditions by boundary score
        ranked_conditions = sorted(
            boundary_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        experimental_plan = []

        # Boundary tightening: add replicates to top boundary conditions
        wells_allocated = 0
        for cond, score in ranked_conditions:
            if wells_allocated >= n_boundary_wells:
                break

            # Allocate reps (e.g., 4-6 per condition)
            n_reps = min(6, n_boundary_wells - wells_allocated)

            experimental_plan.append({
                "condition": cond,
                "n_reps": n_reps,
                "rationale": f"boundary_tightening (score={score:.2f})",
                "expected_entropy_reduction": score * 0.3  # Rough estimate
            })

            wells_allocated += n_reps

        # Trajectory fill: sample intermediate doses for high-SNR trajectories
        trajectory_snr = phase1_metrics.get("trajectory_snr", {})
        ranked_trajectories = sorted(
            trajectory_snr.items(),
            key=lambda x: x[1],
            reverse=True
        )

        wells_allocated = 0
        for traj_key, snr in ranked_trajectories:
            if wells_allocated >= n_trajectory_wells:
                break

            # Parse trajectory key: compound_cell_timepoint
            parts = traj_key.rsplit('_', 2)
            if len(parts) != 3:
                continue

            compound, cell, timepoint = parts

            # Suggest 2 intermediate doses
            n_reps = min(4, n_trajectory_wells - wells_allocated)

            experimental_plan.append({
                "trajectory": traj_key,
                "n_wells": n_reps,
                "rationale": f"trajectory_fill (SNR={snr:.1f})",
                "expected_snr_improvement": 0.1  # Rough estimate
            })

            wells_allocated += n_reps

        return {
            "batch_id": batch_id,
            "sentinel_plan": sentinel_plan,
            "experimental_plan": experimental_plan,
            "expected_reward_terms": {
                "boundary_entropy_reduction": sum(
                    item.get("expected_entropy_reduction", 0)
                    for item in experimental_plan
                    if "boundary" in item.get("rationale", "")
                ),
                "trajectory_snr_improvement": sum(
                    item.get("expected_snr_improvement", 0)
                    for item in experimental_plan
                    if "trajectory" in item.get("rationale", "")
                ),
            },
            "total_wells": sentinel_plan["n_sentinel_wells"] + n_experimental,
        }


# ============================================================================
# Utility: Compute integration test metrics
# ============================================================================

def _to_native_type(val):
    """Convert numpy types to Python native types for JSON serialization."""
    if hasattr(val, 'item'):
        return val.item()
    elif isinstance(val, np.ndarray):
        return val.tolist()
    elif isinstance(val, (np.integer, np.floating)):
        return float(val)
    elif isinstance(val, np.bool_):
        return bool(val)
    elif isinstance(val, dict):
        return {k: _to_native_type(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_to_native_type(v) for v in val]
    return val


def compute_integration_test_metrics(
    batch_frames: Dict[str, BatchFrame],
    global_vehicle_mu: np.ndarray,
    global_sentinel_mus: Dict[str, np.ndarray],
    within_scatter: float
) -> Dict:
    """
    Compute decomposed nuisance metrics for integration test.

    Three critical metrics:
    A) Vehicle drift magnitude (before centering)
    B) Post-centering residual drift per sentinel
    C) Sentinel geometry preservation

    Returns pass/fail assessment and detailed diagnostics.
    """
    vehicle_drifts = []
    sentinel_residual_drifts = {}
    geometry_correlations = []

    for batch_id, frame in batch_frames.items():
        # A) Vehicle drift magnitude
        vehicle_drift = np.linalg.norm(frame.vehicle_mu - global_vehicle_mu)
        frame.vehicle_drift_magnitude = vehicle_drift
        vehicle_drifts.append(vehicle_drift)

        # B) Post-centering residual drift
        frame.sentinel_residual_drifts = {}
        for sentinel_name, sentinel_mu in frame.sentinel_mus.items():
            if sentinel_name not in global_sentinel_mus:
                continue

            # Center both batch and global by their respective vehicles
            sentinel_centered_batch = sentinel_mu - frame.vehicle_mu
            sentinel_centered_global = global_sentinel_mus[sentinel_name] - global_vehicle_mu

            residual_drift = np.linalg.norm(sentinel_centered_batch - sentinel_centered_global)
            frame.sentinel_residual_drifts[sentinel_name] = residual_drift

            if sentinel_name not in sentinel_residual_drifts:
                sentinel_residual_drifts[sentinel_name] = []
            sentinel_residual_drifts[sentinel_name].append(residual_drift)

            # Store centered sentinel means
            frame.sentinel_mus_centered[sentinel_name] = sentinel_centered_batch

        # C) Sentinel geometry preservation
        # Compute pairwise distances between sentinels (centered)
        sentinel_names = sorted(frame.sentinel_mus_centered.keys())
        if len(sentinel_names) >= 2:
            batch_distances = []
            global_distances = []

            for i in range(len(sentinel_names)):
                for j in range(i+1, len(sentinel_names)):
                    s1, s2 = sentinel_names[i], sentinel_names[j]

                    # Batch pairwise distance
                    d_batch = np.linalg.norm(
                        frame.sentinel_mus_centered[s1] - frame.sentinel_mus_centered[s2]
                    )
                    batch_distances.append(d_batch)

                    # Global pairwise distance
                    if s1 in global_sentinel_mus and s2 in global_sentinel_mus:
                        s1_global_centered = global_sentinel_mus[s1] - global_vehicle_mu
                        s2_global_centered = global_sentinel_mus[s2] - global_vehicle_mu
                        d_global = np.linalg.norm(s1_global_centered - s2_global_centered)
                        global_distances.append(d_global)

            if len(batch_distances) > 0 and len(global_distances) > 0:
                # Correlation of pairwise distances
                corr = np.corrcoef(batch_distances, global_distances)[0, 1]
                frame.geometry_preservation = corr
                geometry_correlations.append(corr)

    # Aggregate metrics
    median_vehicle_drift = np.median(vehicle_drifts) if vehicle_drifts else 0.0
    max_vehicle_drift = np.max(vehicle_drifts) if vehicle_drifts else 0.0

    sentinel_median_drifts = {}
    sentinel_max_drifts = {}
    for sentinel_name, drifts in sentinel_residual_drifts.items():
        sentinel_median_drifts[sentinel_name] = np.median(drifts)
        sentinel_max_drifts[sentinel_name] = np.max(drifts)

    overall_median_residual = np.median(list(sentinel_median_drifts.values())) if sentinel_median_drifts else 0.0
    overall_max_residual = np.max(list(sentinel_max_drifts.values())) if sentinel_max_drifts else 0.0

    median_geometry = np.median(geometry_correlations) if geometry_correlations else 0.0
    min_geometry = np.min(geometry_correlations) if geometry_correlations else 0.0

    # Pass/fail criteria
    # 1. Anchor between-plate shift < 0.5× within-scatter (using median vehicle drift)
    criterion_1_pass = median_vehicle_drift < (0.5 * within_scatter)

    # 2. Post-centering sentinel residual drift
    #    - median < 0.5× within-scatter
    #    - max < 0.8× within-scatter
    criterion_2_median_pass = overall_median_residual < (0.5 * within_scatter)
    criterion_2_max_pass = overall_max_residual < (0.8 * within_scatter)

    # 3. Sentinel geometry preservation > 0.9 for most batches
    criterion_3_pass = median_geometry > 0.9

    all_pass = (
        criterion_1_pass and
        criterion_2_median_pass and
        criterion_2_max_pass and
        criterion_3_pass
    )

    return _to_native_type({
        "pass": all_pass,
        "within_scatter": within_scatter,
        "vehicle_drift": {
            "median": median_vehicle_drift,
            "max": max_vehicle_drift,
            "normalized_median": median_vehicle_drift / within_scatter if within_scatter > 0 else 0.0,
            "criterion_pass": criterion_1_pass,
            "criterion_threshold": 0.5
        },
        "sentinel_residual_drift": {
            "per_sentinel_median": sentinel_median_drifts,
            "per_sentinel_max": sentinel_max_drifts,
            "overall_median": overall_median_residual,
            "overall_max": overall_max_residual,
            "normalized_median": overall_median_residual / within_scatter if within_scatter > 0 else 0.0,
            "normalized_max": overall_max_residual / within_scatter if within_scatter > 0 else 0.0,
            "criterion_median_pass": criterion_2_median_pass,
            "criterion_max_pass": criterion_2_max_pass,
            "criterion_threshold_median": 0.5,
            "criterion_threshold_max": 0.8
        },
        "geometry_preservation": {
            "median": median_geometry,
            "min": min_geometry,
            "per_batch": {batch_id: frame.geometry_preservation for batch_id, frame in batch_frames.items() if frame.geometry_preservation is not None},
            "criterion_pass": criterion_3_pass,
            "criterion_threshold": 0.9
        },
        "recommendation": (
            "✓ Boundaries are allowed to exist. Proceed to Phase 2." if all_pass
            else "⚠ Still doing plate anthropology. Fix anchors before trusting boundaries."
        )
    })


# ============================================================================
# Utility: Build BatchFrames from data
# ============================================================================

def build_batch_frames(
    wells: List[WellRecord],
    sentinel_specs: List[SentinelSpec]
) -> Dict[str, BatchFrame]:
    """
    Build BatchFrame for each batch using sentinel wells.

    Args:
        wells: All wells with embeddings
        sentinel_specs: Sentinel specifications

    Returns:
        Dict mapping batch_id -> BatchFrame
    """
    # Group wells by batch
    batches = {}
    for well in wells:
        if well.batch_id not in batches:
            batches[well.batch_id] = []
        batches[well.batch_id].append(well)

    # Build BatchFrame per batch
    batch_frames = {}

    for batch_id, batch_wells in batches.items():
        # Find vehicle wells (dose=0 or compound=DMSO)
        vehicle_wells = [
            w for w in batch_wells
            if w.dose_uM == 0.0 or w.compound == 'DMSO'
        ]

        if len(vehicle_wells) == 0:
            logger.warning(f"No vehicle wells in batch {batch_id}, cannot build BatchFrame")
            continue

        vehicle_embeddings = np.array([w.embedding for w in vehicle_wells])
        vehicle_mu = vehicle_embeddings.mean(axis=0)
        vehicle_sigma = vehicle_embeddings.std(axis=0)

        # Find sentinel wells for each archetype
        sentinel_mus = {}
        sentinel_counts = {}

        for spec in sentinel_specs:
            sentinel_wells = [w for w in batch_wells if spec.matches(w)]

            if len(sentinel_wells) > 0:
                sentinel_embeddings = np.array([w.embedding for w in sentinel_wells])
                sentinel_mus[spec.name] = sentinel_embeddings.mean(axis=0)
                sentinel_counts[spec.name] = len(sentinel_wells)

        # Compute quality metrics
        quality = {
            "n_total_wells": len(batch_wells),
            "n_vehicle_wells": len(vehicle_wells),
            "qc_pass_rate": sum(w.qc_pass for w in batch_wells) / len(batch_wells),
        }

        batch_frames[batch_id] = BatchFrame(
            batch_id=batch_id,
            vehicle_mu=vehicle_mu,
            vehicle_sigma=vehicle_sigma,
            sentinel_mus=sentinel_mus,
            n_vehicle_wells=len(vehicle_wells),
            n_sentinel_wells=sentinel_counts,
            quality=quality
        )

    return batch_frames


# ============================================================================
# High-level API: Analyze boundaries for a design
# ============================================================================

def analyze_boundaries(
    results: List[Dict],
    design_id: str,
    phase1_metrics: Dict,
    sentinel_specs: List[SentinelSpec],
    boundary_type: Literal["death", "stress"] = "death"
) -> Dict:
    """
    High-level API: Analyze boundaries for a design.

    Args:
        results: Raw results from database
        design_id: Design identifier
        phase1_metrics: Metrics from morphology variance analysis
        sentinel_specs: Sentinel specifications
        boundary_type: Type of boundary to detect

    Returns:
        {
            "boundary_model": trained model artifact,
            "batch_frames": normalization frames,
            "boundary_band_conditions": list of conditions near boundary,
            "acquisition_plan": recommended next experiment,
            "diagnostics": quality metrics
        }
    """
    logger.info(f"Starting boundary analysis for {design_id} (type={boundary_type})")

    # Convert results to WellRecords
    wells = []
    for r in results:
        # Extract morphology features
        morph = np.array([
            r.get('morph_er', 0.0),
            r.get('morph_mito', 0.0),
            r.get('morph_nucleus', 0.0),
            r.get('morph_actin', 0.0),
            r.get('morph_rna', 0.0),
        ])

        # Skip wells with missing morphology
        if np.any(np.isnan(morph)) or np.all(morph == 0):
            continue

        # Build batch_id from plate + operator + day + timepoint
        batch_id = f"{r.get('plate_id', 'unknown')}_{r.get('operator', 'unknown')}_{r.get('day', 1)}_{r.get('timepoint_h', 0)}h"

        well = WellRecord(
            well_id=r.get('well_id', ''),
            cell_line=r.get('cell_line', ''),
            compound=r.get('compound', ''),
            dose_uM=r.get('dose_uM', 0.0),
            timepoint=f"{int(r.get('timepoint_h', 0))}h",
            embedding=morph,  # Raw features for now; would use PCA embeddings in practice
            viability=r.get('viability_pct', 100.0) / 100.0 if r.get('viability_pct') else None,
            qc_pass=True,  # Placeholder
            plate_id=r.get('plate_id', ''),
            batch_id=batch_id,
            operator=r.get('operator'),
            day=str(r.get('day', 1)),
            is_sentinel=r.get('is_sentinel', False)
        )

        wells.append(well)

    logger.info(f"Converted {len(wells)} wells to WellRecords")

    # Build batch frames
    batch_frames = build_batch_frames(wells, sentinel_specs)
    logger.info(f"Built {len(batch_frames)} batch frames")

    # Compute global sentinel means (needed for integration test)
    global_vehicle_wells = [w for w in wells if w.dose_uM == 0.0 or w.compound == 'DMSO']
    global_vehicle_mu = np.mean([w.embedding for w in global_vehicle_wells], axis=0) if global_vehicle_wells else np.zeros(5)

    global_sentinel_mus = {}
    for spec in sentinel_specs:
        spec_wells = [w for w in wells if spec.matches(w)]
        if spec_wells:
            global_sentinel_mus[spec.name] = np.mean([w.embedding for w in spec_wells], axis=0)

    # Compute within-scatter (RMS of vehicle well stds)
    if global_vehicle_wells:
        vehicle_embeddings = np.array([w.embedding for w in global_vehicle_wells])
        within_scatter = np.sqrt(np.mean(np.var(vehicle_embeddings, axis=0)))
    else:
        within_scatter = 1.0  # Fallback

    # Compute integration test metrics
    integration_metrics = compute_integration_test_metrics(
        batch_frames=batch_frames,
        global_vehicle_mu=global_vehicle_mu,
        global_sentinel_mus=global_sentinel_mus,
        within_scatter=within_scatter
    )
    logger.info(f"Integration test: {integration_metrics['recommendation']}")

    # Train boundary model (placeholder - would need labels)
    if boundary_type == "death":
        classes = ["alive_stressed", "death"]
        # Death labels from viability + QC
        labels = np.array([
            1 if (w.viability is not None and w.viability < 0.25) else 0
            for w in wells
        ])
    else:
        classes = ["vehicle", "ER", "mito", "proteostasis", "oxidative"]
        # Would use sentinel labels here
        labels = np.zeros(len(wells))  # Placeholder

    boundary_model = BoundaryModel(
        name=f"{boundary_type}_boundary",
        classes=classes
    )

    # Only fit if we have labeled data
    if len(np.unique(labels)) > 1:
        boundary_model.fit(wells, labels, batch_frames)

        # Predict on all wells
        proba = boundary_model.predict_proba(wells, batch_frames)
        uncertainty = boundary_model.uncertainty(wells, batch_frames)
    else:
        logger.warning("Insufficient labeled data, skipping model fitting")
        proba = np.zeros((len(wells), len(classes)))
        uncertainty = np.zeros(len(wells))

    # Select boundary band
    selector = BoundaryBandSelector(mode="entropy")
    wells_in_band = selector.select_wells(wells, proba, uncertainty)

    logger.info(f"Found {len(wells_in_band)} wells in boundary band")

    # Extract boundary conditions
    boundary_conditions = list(set(w.condition for w in wells_in_band))

    return {
        "design_id": design_id,
        "boundary_type": boundary_type,
        "n_batches": len(batch_frames),
        "n_wells": len(wells),
        "n_boundary_wells": len(wells_in_band),
        "boundary_conditions": [
            {
                "cell_line": cond[0],
                "compound": cond[1],
                "dose_uM": cond[2],
                "timepoint": cond[3]
            }
            for cond in boundary_conditions
        ],
        "batch_diagnostics": [
            {
                "batch_id": batch_id,
                "n_vehicle_wells": frame.n_vehicle_wells,
                "n_sentinel_wells": sum(frame.n_sentinel_wells.values()) if frame.n_sentinel_wells else 0,
                "vehicle_drift_magnitude": frame.vehicle_drift_magnitude,
                "sentinel_residual_drifts": frame.sentinel_residual_drifts,
                "geometry_preservation": frame.geometry_preservation,
                "quality": frame.quality
            }
            for batch_id, frame in batch_frames.items()
        ],
        "integration_test": integration_metrics,
        "model_fitted": boundary_model.is_fitted,
    }
