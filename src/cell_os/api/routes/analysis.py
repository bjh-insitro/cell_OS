"""
Analysis Routes

Endpoints for statistical and mechanistic analysis.
"""

import logging
from typing import Optional
from datetime import datetime
from collections import defaultdict
from fastapi import APIRouter, HTTPException
import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from cell_os.database.cell_thalamus_db import CellThalamusDB
from cell_os.cell_thalamus.variance_analysis import VarianceAnalyzer
from cell_os.cell_thalamus.boundary_detection import (
    analyze_boundaries,
    SentinelSpec,
    AnchorBudgeter,
    BoundaryBandSelector,
    AcquisitionPlanner
)
from cell_os.cell_thalamus.manifold_charts import (
    BoundaryType,
    ChartStatus,
    ManifoldChart,
    create_chart_from_integration_test,
    compute_dose_pair_separation,
    compute_archetype_fanout
)

logger = logging.getLogger(__name__)

router = APIRouter()

# These will be injected from main app
DB_PATH: str = ""


def init_globals(db_path):
    """Initialize global state from main app"""
    global DB_PATH
    DB_PATH = db_path


@router.get("/api/thalamus/designs/{design_id}/variance")
async def get_variance_analysis(design_id: str, metric: str = None):
    """Perform variance analysis"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        analyzer = VarianceAnalyzer(db)
        raw_analysis = analyzer.analyze_design(design_id)
        db.close()

        if "error" in raw_analysis:
            raise HTTPException(status_code=404, detail=raw_analysis["error"])

        # Helper function to convert numpy types to Python native types
        def to_native(val):
            if hasattr(val, 'item'):
                return val.item()
            return float(val) if isinstance(val, (int, float)) else val

        # If no metric specified, return all metrics for heatmap
        if metric is None:
            all_metrics = {}
            for metric_name, components_data in raw_analysis['variance_components'].items():
                metric_components = []
                for source, variance in components_data['components'].items():
                    total_var = components_data['total_variance']
                    fraction = variance / total_var if total_var > 0 else 0
                    metric_components.append({
                        'source': source,
                        'variance': to_native(variance),
                        'fraction': to_native(fraction)
                    })

                # Add residual
                metric_components.append({
                    'source': 'residual',
                    'variance': to_native(components_data['residual_variance']),
                    'fraction': to_native(components_data['residual_fraction'])
                })

                all_metrics[metric_name] = {
                    'components': metric_components,
                    'total_variance': to_native(components_data['total_variance'])
                }

            # Convert summary to native types
            summary = raw_analysis['summary']
            safe_summary = {
                'biological_fraction_mean': to_native(summary['biological_fraction_mean']),
                'technical_fraction_mean': to_native(summary['technical_fraction_mean']),
                'criteria': {
                    'biological_dominance': {
                        'pass': bool(summary['criteria']['biological_dominance']['pass'])
                    },
                    'technical_control': {
                        'pass': bool(summary['criteria']['technical_control']['pass'])
                    },
                    'sentinel_stability': {
                        'pass': bool(summary['criteria']['sentinel_stability']['pass'])
                    }
                }
            }

            return {
                'all_metrics': all_metrics,
                'summary': safe_summary
            }

        # Single metric request - existing logic
        atp_components = raw_analysis['variance_components'][metric]
        summary = raw_analysis['summary']
        spc = raw_analysis['spc_results']

        # Build components array
        components = []
        for source, variance in atp_components['components'].items():
            total_var = atp_components['total_variance']
            fraction = variance / total_var if total_var > 0 else 0
            components.append({
                'source': source,
                'variance': to_native(variance),
                'fraction': to_native(fraction)
            })

        # Add residual variance as a component
        components.append({
            'source': 'residual',
            'variance': to_native(atp_components['residual_variance']),
            'fraction': to_native(atp_components['residual_fraction'])
        })

        # Calculate sentinel pass rate
        if 'error' not in spc:
            total_sentinels = sum(v['n_points'] for v in spc.values())
            in_control_sentinels = sum(
                v['n_points'] - v['n_out_of_control']
                for v in spc.values()
            )
            pass_rate = in_control_sentinels / total_sentinels if total_sentinels > 0 else 0
        else:
            pass_rate = 0

        # Transform to frontend format
        analysis = {
            'metric': metric,
            'total_variance': to_native(atp_components['total_variance']),
            'biological_fraction': to_native(summary['biological_fraction_mean']),
            'technical_fraction': to_native(summary['technical_fraction_mean']),
            'pass_rate': to_native(pass_rate),
            'criteria': {
                'biological_dominance': bool(summary['criteria']['biological_dominance']['pass']),
                'technical_minimal': bool(summary['criteria']['technical_control']['pass']),
                'sentinel_stable': bool(summary['criteria']['sentinel_stability']['pass'])
            },
            'components': components
        }

        return analysis

    except Exception as e:
        logger.error(f"Error in variance analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/thalamus/designs/{design_id}/morphology-variance")
async def get_morphology_variance_analysis(design_id: str):
    """
    Analyze morphology variance for autonomous loop candidate ranking (Phase 1).

    This replaces entropy/CV-based ranking with morphology covariance analysis:
    - Per-condition scatter in PC space (tr(Σ_c))
    - Nuisance variance decomposition (plate/day/operator effects)
    - Priority scoring: high variance, non-death, low nuisance

    Returns ranked conditions and global diagnostics.
    """
    try:
        from cell_os.cell_thalamus.morphology_variance_analysis import rank_conditions_for_autonomous_loop

        # Get results for this design
        db = CellThalamusDB(db_path=DB_PATH)
        results = db.get_results(design_id)
        db.close()

        if not results:
            raise HTTPException(status_code=404, detail="No results found")

        # Run morphology variance analysis
        candidates, diagnostics = rank_conditions_for_autonomous_loop(
            results=results,
            design_id=design_id,
            top_k=15
        )

        return {
            'candidates': candidates,
            'diagnostics': diagnostics,
            'design_id': design_id,
            'analysis_type': 'morphology_covariance',
        }

    except Exception as e:
        logger.error(f"Error in morphology variance analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/thalamus/designs/{design_id}/boundaries")
async def get_boundary_analysis(
    design_id: str,
    boundary_type: str = "death",
    timepoint_h: Optional[float] = None,
    chart_id: Optional[str] = None
):
    """
    Phase 2: Boundary detection with manifold chart capability gating.

    This endpoint now enforces architectural constraints:
    - Mechanism-axis boundaries require geometry_preservation >= 0.90
    - Charts are first-class coordinate systems with explicit capabilities
    - Requests for disallowed boundary types return hard errors (not warnings)

    Args:
        design_id: Design to analyze
        boundary_type: "death" or "mechanism_axis"
        timepoint_h: Optional timepoint filter (creates chart per timepoint)
        chart_id: Optional chart ID (overrides timepoint_h if provided)

    Returns:
        {
            "charts": List of available charts with health + capabilities,
            "selected_chart": Chart used for this analysis (if boundary succeeded),
            "boundary_conditions": Conditions near decision boundary (if allowed),
            "error": Structured error if boundary type not allowed on chart
        }
    """
    try:
        # Get results
        db = CellThalamusDB(db_path=DB_PATH)
        results = db.get_results(design_id)
        db.close()

        if not results:
            raise HTTPException(status_code=404, detail="No results found")

        # Parse boundary type
        try:
            requested_boundary = BoundaryType(boundary_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid boundary_type: {boundary_type}. Must be one of: {[bt.value for bt in BoundaryType]}"
            )

        # Group results by timepoint
        timepoint_results = {}
        for r in results:
            tp = r.get('timepoint_h', 0.0)
            if tp not in timepoint_results:
                timepoint_results[tp] = []
            timepoint_results[tp].append(r)

        logger.info(f"Found {len(timepoint_results)} unique timepoints: {sorted(timepoint_results.keys())}")

        # Define standard sentinel specs
        sentinel_specs = [
            SentinelSpec(name="vehicle", cell_line="A549", compound="DMSO", dose_uM=0.0),
            SentinelSpec(name="ER", cell_line="A549", compound="thapsigargin", dose_uM=0.5),
            SentinelSpec(name="mito", cell_line="A549", compound="oligomycin", dose_uM=1.0),
            SentinelSpec(name="proteostasis", cell_line="A549", compound="MG132", dose_uM=1.0),
            SentinelSpec(name="oxidative", cell_line="A549", compound="tBHQ", dose_uM=30.0),
        ]

        # Analyze each timepoint separately and create charts
        charts = []
        for tp, tp_results in sorted(timepoint_results.items()):
            logger.info(f"Analyzing timepoint {tp}h ({len(tp_results)} wells)")

            # Run boundary analysis for this timepoint only
            analysis = analyze_boundaries(
                results=tp_results,
                design_id=f"{design_id}_T{int(tp):02d}h",
                phase1_metrics={"trajectory_snr": {}, "global_nuisance_fraction": 0.5},
                sentinel_specs=sentinel_specs,
                boundary_type=boundary_type
            )

            # Create chart from integration test
            chart = create_chart_from_integration_test(
                timepoint_h=tp,
                batch_diagnostics=analysis["batch_diagnostics"],
                integration_test=analysis["integration_test"],
                within_scatter=analysis["integration_test"]["within_scatter"]
            )

            charts.append({
                "chart": chart,
                "analysis": analysis
            })

        # Select chart based on user request
        selected_chart = None
        selected_analysis = None

        if chart_id:
            # Find by chart_id
            for c in charts:
                if c["chart"].chart_id == chart_id:
                    selected_chart = c["chart"]
                    selected_analysis = c["analysis"]
                    break
            if not selected_chart:
                raise HTTPException(
                    status_code=404,
                    detail=f"Chart {chart_id} not found. Available charts: {[c['chart'].chart_id for c in charts]}"
                )
        elif timepoint_h is not None:
            # Find by timepoint
            for c in charts:
                if c["chart"].timepoint_h == timepoint_h:
                    selected_chart = c["chart"]
                    selected_analysis = c["analysis"]
                    break
            if not selected_chart:
                raise HTTPException(
                    status_code=404,
                    detail=f"No chart found for timepoint {timepoint_h}h"
                )
        else:
            # Auto-select: prefer PASS charts, then earliest CONDITIONAL
            pass_charts = [c for c in charts if c["chart"].status == ChartStatus.PASS]
            if pass_charts:
                selected_chart = pass_charts[0]["chart"]
                selected_analysis = pass_charts[0]["analysis"]
            else:
                conditional_charts = [c for c in charts if c["chart"].status == ChartStatus.CONDITIONAL]
                if conditional_charts:
                    selected_chart = conditional_charts[0]["chart"]
                    selected_analysis = conditional_charts[0]["analysis"]
                else:
                    # All failed - return error with chart health
                    return {
                        "error": {
                            "code": "ALL_CHARTS_FAILED",
                            "message": "All timepoint charts failed integration tests",
                            "details": {
                                "charts": [{
                                    "chart_id": c["chart"].chart_id,
                                    "timepoint_h": c["chart"].timepoint_h,
                                    "status": c["chart"].status.value,
                                    "health": {
                                        "geometry_preservation": c["chart"].health.geometry_preservation_median,
                                        "vehicle_drift": c["chart"].health.vehicle_drift_median_normalized
                                    }
                                } for c in charts]
                            },
                            "recommendation": "Run anchor tightening cycle with increased sentinel replicates (8 vehicle + 5 per archetype)"
                        }
                    }

        # Check if requested boundary type is allowed on selected chart
        if not selected_chart.allows_boundary_type(requested_boundary):
            # HARD ERROR - capability violation
            refuse_response = selected_chart.refuse_message(requested_boundary)
            refuse_response["available_charts"] = [{
                "chart_id": c["chart"].chart_id,
                "timepoint_h": c["chart"].timepoint_h,
                "status": c["chart"].status.value,
                "allowed_boundaries": [bt.value for bt in c["chart"].allowed_boundary_types],
                "health": {
                    "geometry_preservation": c["chart"].health.geometry_preservation_median,
                    "sentinel_max_drift": c["chart"].health.sentinel_max_drift_normalized
                }
            } for c in charts]
            return refuse_response

        # Boundary type is allowed - return analysis
        # Get Phase 1 metrics for acquisition planning
        from cell_os.cell_thalamus.morphology_variance_analysis import rank_conditions_for_autonomous_loop
        try:
            _, phase1_diagnostics = rank_conditions_for_autonomous_loop(
                results=timepoint_results[selected_chart.timepoint_h],
                design_id=design_id,
                top_k=15
            )
        except Exception as e:
            logger.warning(f"Could not get Phase 1 metrics: {e}")
            phase1_diagnostics = {
                "trajectory_snr": {},
                "global_nuisance_fraction": 0.5
            }

        # Generate acquisition plan
        anchor_budgeter = AnchorBudgeter(sentinel_specs, reps_per_sentinel=5, vehicle_reps=8)
        boundary_selector = BoundaryBandSelector(mode="entropy")
        planner = AcquisitionPlanner(anchor_budgeter, boundary_selector)

        boundary_scores = {
            (cond["cell_line"], cond["compound"], cond["dose_uM"], cond["timepoint"]): 1.0
            for cond in selected_analysis["boundary_conditions"]
        }

        acquisition_plan = planner.plan(
            candidate_conditions=list(boundary_scores.keys()),
            phase1_metrics=phase1_diagnostics,
            boundary_scores=boundary_scores,
            plate_format=96,
            batch_id=f"anchor_tightening_{design_id[:8]}_T{int(selected_chart.timepoint_h):02d}h",
            policy={"boundary_frac": 0.6, "trajectory_frac": 0.4, "sentinel_frac": 0.31}
        )

        return {
            "design_id": design_id,
            "charts": [{
                "chart_id": c["chart"].chart_id,
                "timepoint_h": c["chart"].timepoint_h,
                "status": c["chart"].status.value,
                "chart_type": c["chart"].chart_type,
                "allowed_boundaries": [bt.value for bt in c["chart"].allowed_boundary_types],
                "health": {
                    "geometry_preservation_median": c["chart"].health.geometry_preservation_median,
                    "geometry_preservation_min": c["chart"].health.geometry_preservation_min,
                    "sentinel_max_drift": c["chart"].health.sentinel_max_drift_normalized,
                    "vehicle_drift_median": c["chart"].health.vehicle_drift_median_normalized,
                    "n_batches": c["chart"].health.n_batches
                },
                "notes": c["chart"].notes
            } for c in charts],
            "selected_chart": {
                "chart_id": selected_chart.chart_id,
                "timepoint_h": selected_chart.timepoint_h,
                "status": selected_chart.status.value,
                "chart_type": selected_chart.chart_type
            },
            "boundary_type": boundary_type,
            "boundary_conditions": selected_analysis["boundary_conditions"],
            "batch_diagnostics": selected_analysis["batch_diagnostics"],
            "integration_test": selected_analysis["integration_test"],
            "acquisition_plan": acquisition_plan,
            "model_fitted": selected_analysis["model_fitted"],
            "phase": "Phase2_BoundaryDetection",
            "model_version": "phase2_v2.0_chart_gating",
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in boundary analysis: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/thalamus/designs/{design_id}/sentinels")
async def get_sentinel_data(design_id: str):
    """Get sentinel SPC data"""
    try:
        db = CellThalamusDB(db_path=DB_PATH)
        sentinel_wells = db.get_sentinel_data(design_id)
        db.close()

        if not sentinel_wells:
            raise HTTPException(status_code=404, detail="No sentinel data found")

        # Group sentinels by compound and cell line
        grouped = defaultdict(list)
        for well in sentinel_wells:
            key = f"{well['compound']} ({well['cell_line']})"
            grouped[key].append(well)

        # Calculate SPC statistics for each sentinel type and metric
        spc_data = []
        metrics = ['atp_signal', 'morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna']

        for sentinel_type, wells in grouped.items():
            for metric in metrics:
                # Extract values for this metric
                values = [w[metric] for w in wells if w[metric] is not None]

                if len(values) < 2:
                    continue

                # Calculate statistics
                mean = float(np.mean(values))
                std = float(np.std(values, ddof=1))
                ucl = mean + 3 * std
                lcl = mean - 3 * std

                # Create points with outlier detection
                points = []
                for well in wells:
                    value = well[metric]
                    if value is not None:
                        is_outlier = value > ucl or value < lcl
                        points.append({
                            'plate_id': well['plate_id'],
                            'day': well['day'],
                            'operator': well['operator'],
                            'value': float(value),
                            'is_outlier': bool(is_outlier)
                        })

                spc_data.append({
                    'sentinel_type': sentinel_type,
                    'metric': metric,
                    'mean': mean,
                    'std': std,
                    'ucl': ucl,
                    'lcl': lcl,
                    'points': points
                })

        return spc_data

    except Exception as e:
        logger.error(f"Error getting sentinel data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/thalamus/designs/{design_id}/mechanism-recovery")
async def get_mechanism_recovery_stats(design_id: str):
    """
    Compute mechanism recovery statistics for a design.

    Returns separation ratios and centroid distances for:
    - All doses mixed (baseline collapse)
    - Mid-dose 12h only (optimal separation)
    - High-dose 48h only (death signature)
    """
    try:
        db = CellThalamusDB(DB_PATH)

        # EC50 map for dose stratification
        EC50_MAP = {
            'tBHQ': 30.0, 'H2O2': 100.0, 'tunicamycin': 1.0, 'thapsigargin': 0.5,
            'CCCP': 5.0, 'oligomycin': 1.0, 'etoposide': 10.0, 'MG132': 1.0,
            'nocodazole': 0.5, 'paclitaxel': 0.01,
        }

        STRESS_AXES = {
            'tBHQ': 'oxidative', 'H2O2': 'oxidative',
            'tunicamycin': 'er_stress', 'thapsigargin': 'er_stress',
            'CCCP': 'mitochondrial', 'oligomycin': 'mitochondrial',
            'etoposide': 'dna_damage', 'MG132': 'proteasome',
            'nocodazole': 'microtubule', 'paclitaxel': 'microtubule',
        }

        def load_and_filter(dose_filter='all', timepoint_filter=None):
            """Load morphology data with optional dose/timepoint filtering."""
            cursor = db.conn.cursor()
            cursor.execute("""
                SELECT compound, cell_line, timepoint_h, dose_uM,
                       morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna
                FROM thalamus_results
                WHERE design_id = ? AND is_sentinel = 0 AND compound != 'DMSO' AND dose_uM > 0
            """, (design_id,))

            rows = cursor.fetchall()
            data = []
            metadata = []

            for row in rows:
                compound, cell_line, timepoint, dose, er, mito, nucleus, actin, rna = row

                # Timepoint filter
                if timepoint_filter is not None and timepoint != timepoint_filter:
                    continue

                # Dose filter
                ec50 = EC50_MAP.get(compound)
                if ec50 is None:
                    continue

                dose_ratio = dose / ec50

                if dose_filter == 'mid' and not (0.5 <= dose_ratio <= 2.0):
                    continue
                elif dose_filter == 'high' and dose_ratio < 5.0:
                    continue

                stress_axis = STRESS_AXES.get(compound, 'unknown')
                morph_vector = np.array([er, mito, nucleus, actin, rna])

                data.append(morph_vector)
                metadata.append({'stress_axis': stress_axis})

            return np.array(data), metadata

        def compute_separation(X, metadata):
            """Compute PCA and separation ratio."""
            if len(X) < 10:
                return 0.0, 0.0, [], []

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            pca = PCA(n_components=2)
            X_pca = pca.fit_transform(X_scaled)

            # Compute separation ratio
            centroids = defaultdict(lambda: {'pc1': [], 'pc2': []})
            for i, meta in enumerate(metadata):
                stress_axis = meta['stress_axis']
                centroids[stress_axis]['pc1'].append(X_pca[i, 0])
                centroids[stress_axis]['pc2'].append(X_pca[i, 1])

            within_var = 0
            between_var = 0
            global_centroid = X_pca.mean(axis=0)

            for stress_axis, data in centroids.items():
                class_centroid = np.array([np.mean(data['pc1']), np.mean(data['pc2'])])
                between_var += len(data['pc1']) * np.sum((class_centroid - global_centroid)**2)

                for i, meta in enumerate(metadata):
                    if meta['stress_axis'] == stress_axis:
                        point = X_pca[i]
                        within_var += np.sum((point - class_centroid)**2)

            separation_ratio = between_var / (within_var + 1e-9)

            # Compute average pairwise centroid distance
            axes = list(centroids.keys())
            distances = []
            for i, ax1 in enumerate(axes):
                for ax2 in axes[i+1:]:
                    c1 = np.array([np.mean(centroids[ax1]['pc1']), np.mean(centroids[ax1]['pc2'])])
                    c2 = np.array([np.mean(centroids[ax2]['pc1']), np.mean(centroids[ax2]['pc2'])])
                    dist = np.linalg.norm(c1 - c2)
                    distances.append(dist)

            centroid_distance = np.mean(distances) if distances else 0.0

            # Return PCA coordinates for plotting
            pc_scores = X_pca.tolist()

            return separation_ratio, centroid_distance, pc_scores, metadata

        # Compute stats for each condition
        X_all, meta_all = load_and_filter(dose_filter='all')
        sep_all, dist_all, pc_all, pc_meta_all = compute_separation(X_all, meta_all)

        X_mid, meta_mid = load_and_filter(dose_filter='mid', timepoint_filter=12.0)
        sep_mid, dist_mid, pc_mid, pc_meta_mid = compute_separation(X_mid, meta_mid)

        X_high, meta_high = load_and_filter(dose_filter='high', timepoint_filter=48.0)
        sep_high, dist_high, pc_high, pc_meta_high = compute_separation(X_high, meta_high)

        improvement_factor = sep_mid / sep_all if sep_all > 0 else 0.0

        return {
            "all_doses": {
                "separation_ratio": float(sep_all),
                "centroid_distance": float(dist_all),
                "n_wells": len(X_all),
                "pc_scores": pc_all,
                "metadata": [{"stress_axis": m["stress_axis"]} for m in pc_meta_all]
            },
            "mid_dose": {
                "separation_ratio": float(sep_mid),
                "centroid_distance": float(dist_mid),
                "n_wells": len(X_mid),
                "pc_scores": pc_mid,
                "metadata": [{"stress_axis": m["stress_axis"]} for m in pc_meta_mid]
            },
            "high_dose": {
                "separation_ratio": float(sep_high),
                "centroid_distance": float(dist_high),
                "n_wells": len(X_high),
                "pc_scores": pc_high,
                "metadata": [{"stress_axis": m["stress_axis"]} for m in pc_meta_high]
            },
            "improvement_factor": float(improvement_factor)
        }

    except Exception as e:
        logger.error(f"Error computing mechanism recovery stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
