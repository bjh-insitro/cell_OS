# src/cell_os/calibration/bead_plate_calibration.py
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ----------------------------
# Report schema and utilities
# ----------------------------

SCHEMA_VERSION = "bead_plate_calibration_report_v1"

DEFAULT_CHANNEL_ORDER = ["er", "mito", "nucleus", "actin", "rna"]


def _now_iso_utc() -> str:
    # Timezone-aware UTC timestamp
    import datetime as _dt

    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def _load_design(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    with path.open("r") as f:
        return json.load(f)


def _design_hash(design: Optional[Dict[str, Any]]) -> Optional[str]:
    if design is None:
        return None
    import hashlib

    b = json.dumps(design, sort_keys=True).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def _config_hash(cfg: Optional[Dict[str, Any]]) -> Optional[str]:
    if cfg is None:
        return None
    import hashlib

    b = json.dumps(cfg, sort_keys=True).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def _get_material_assignment(rec: Dict[str, Any]) -> str:
    # Prefer explicit fields; fall back to compound if you overloaded it.
    return (
        rec.get("material_assignment")
        or rec.get("material")
        or rec.get("compound")
        or "UNKNOWN"
    )


def _get_detector_metadata(rec: Dict[str, Any]) -> Dict[str, Any]:
    md = rec.get("detector_metadata")
    return md if isinstance(md, dict) else {}


def _get_morph(rec: Dict[str, Any]) -> Dict[str, float]:
    morph = rec.get("morphology") or {}
    if not isinstance(morph, dict):
        return {}
    out: Dict[str, float] = {}
    for k, v in morph.items():
        fv = _safe_float(v)
        if fv is not None:
            out[str(k)] = fv
    return out


def _obs_meta_minimal(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Minimal metadata that helps debug provenance without depending on the run machinery.
    seeds = sorted({r.get("well_seed") for r in records if r.get("well_seed") is not None})
    run_ids = sorted({r.get("run_context_id") for r in records if r.get("run_context_id")})
    assays = sorted({r.get("assay") for r in records if r.get("assay")})
    modes = sorted({r.get("mode") for r in records if r.get("mode")})

    return {
        "n_records": len(records),
        "distinct_run_context_ids": run_ids,
        "distinct_assays": assays,
        "distinct_modes": modes,
        "distinct_well_seeds_count": len(seeds),
    }


# ----------------------------
# Report schema specification
# ----------------------------

def build_empty_report(
    *,
    obs_path: str,
    design_path: Optional[str],
    channel_order: List[str],
    design: Optional[Dict[str, Any]] = None,
    detector_config_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Report schema (bead_plate_calibration_report_v1)

    Required top-level keys:
      - schema_version: str
      - created_utc: str (ISO)
      - inputs: dict
      - channels: list[str]
      - floor: dict (observable flag always present)
      - vignette: dict (observable flag always present)
      - saturation: dict (observable flag always present)
      - quantization: dict (observable flag always present)
      - exposure_recommendations: dict (observable flag always present)
      - notes: list[str]

    Observable blocks follow a pattern:
      {
        "observable": bool,
        "reason": str | null,   # if observable is false
        "recommendation": str | null,  # if observable is false
        ... estimator outputs ...
      }
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "created_utc": _now_iso_utc(),
        "inputs": {
            "observations_jsonl": obs_path,
            "design_json": design_path,
            "design_sha256": _design_hash(design),
            "detector_config_sha256": _config_hash(detector_config_snapshot),
            "detector_config_snapshot": detector_config_snapshot,  # optional, may be None
        },
        "channels": channel_order,
        "floor": {
            "observable": False,
            "reason": "Not computed yet",
            "recommendation": None,
            "dark_well_stats": None,
            "per_channel": None,
        },
        "vignette": {
            "observable": False,
            "reason": "Not computed yet",
            "recommendation": None,
            "model": None,
            "fit_quality": None,
            "edge_multiplier": None,  # per channel
            "center_multiplier": None,  # per channel
        },
        "saturation": {
            "observable": False,
            "reason": "Not computed yet",
            "recommendation": None,
            "per_channel": None,  # saturation fraction, thresholds if available
        },
        "quantization": {
            "observable": False,
            "reason": "Not computed yet",
            "recommendation": None,
            "per_channel": None,  # step estimates, detected flags
        },
        "exposure_recommendations": {
            "observable": False,
            "reason": "Not computed yet",
            "recommendation": None,
            "policy": {
                "target_fraction_of_saturation": 0.80,
                "floor_margin_sigma": None,  # None when floor not observable
            },
            "per_channel": None,  # suggested exposure multipliers, warnings
            "global": None,       # optional plate-wide suggestions
        },
        "run_summary": None,  # filled with minimal info about the observation set
        "notes": [],
    }


# ----------------------------
# Plate geometry helpers
# ----------------------------

def _well_to_rowcol(well_id: str) -> Tuple[int, int]:
    """Convert well_id like 'A1' to (row_idx, col_idx) zero-indexed."""
    import re
    m = re.match(r"^([A-P])(\d{1,2})$", well_id.strip())
    if not m:
        raise ValueError(f"Invalid 384-well ID: {well_id}")
    r = ord(m.group(1)) - ord("A")
    c = int(m.group(2)) - 1
    return r, c


def _normalized_radius(row_idx: int, col_idx: int, n_rows: int = 16, n_cols: int = 24) -> float:
    """
    Compute normalized radial distance from plate center.

    Returns r in [0, 1] where:
      - 0 = center
      - 1 = corner (max distance)
    """
    # Plate center (0-indexed)
    center_r = (n_rows - 1) / 2.0
    center_c = (n_cols - 1) / 2.0

    # Distance from center
    dr = row_idx - center_r
    dc = col_idx - center_c
    dist = math.sqrt(dr**2 + dc**2)

    # Max possible distance (corner to center)
    max_dist = math.sqrt(center_r**2 + center_c**2)

    return dist / max_dist if max_dist > 0 else 0.0


# ----------------------------
# Estimator implementations
# ----------------------------

def estimate_floor(
    records: List[Dict[str, Any]],
    channel_order: List[str],
    *,
    dark_token: str = "DARK",
) -> Dict[str, Any]:
    """
    Stub: Use DARK wells to estimate detector floor.

    Must return a dict matching report["floor"] structure, with:
      - observable: bool
      - reason: str when not observable
      - recommendation: str when not observable
      - dark_well_stats: dict
      - per_channel: dict
    """
    # TODO: implement real estimator.
    # For now, mark unobservable if all dark morph values are exactly 0.0 for all channels.
    dark = [r for r in records if _get_material_assignment(r) == dark_token]
    if not dark:
        return {
            "observable": False,
            "reason": f"No DARK wells found (token={dark_token})",
            "recommendation": "Ensure bead plate design includes DARK wells and material_assignment is present.",
            "dark_well_stats": {"n_wells": 0},
            "per_channel": None,
        }

    unique_vals_by_ch: Dict[str, List[float]] = {}
    per_ch: Dict[str, Any] = {}
    all_zero_all_ch = True

    for ch in channel_order:
        vals = []
        for r in dark:
            morph = _get_morph(r)
            v = morph.get(ch)
            if v is not None:
                vals.append(v)
        uniq = sorted(set(vals))
        unique_vals_by_ch[ch] = uniq
        if any(v != 0.0 for v in uniq):
            all_zero_all_ch = False

        # placeholder stats
        per_ch[ch] = {
            "mean": float(sum(vals) / len(vals)) if vals else None,
            "std": 0.0,
            "unique_values": uniq[:20],  # cap
        }

    if all_zero_all_ch:
        return {
            "observable": False,
            "reason": "DARK wells return literal 0.0 with zero variance across channels, floor is clamped or bypassed.",
            "recommendation": "Add detector bias offset, remove negative clamp, or allow post-noise clamping only.",
            "dark_well_stats": {
                "n_wells": len(dark),
                "per_channel_unique_values": {ch: unique_vals_by_ch[ch][:20] for ch in channel_order},
            },
            "per_channel": per_ch,
        }

    # If observable, still return structure, but this is stub.
    return {
        "observable": True,
        "reason": None,
        "recommendation": None,
        "dark_well_stats": {"n_wells": len(dark)},
        "per_channel": per_ch,
    }


def fit_vignette(
    records: List[Dict[str, Any]],
    channel_order: List[str],
    *,
    dye_token: str = "FLATFIELD_DYE_LOW",
    model: str = "radial_quadratic",
) -> Dict[str, Any]:
    """
    Fit vignette from flatfield dye wells using radial quadratic model.

    Model: I(r) = c0 + c1 * r^2
    where r is normalized radius from plate center [0, 1].

    Returns edge_multiplier = (c0 + c1) / c0 for each channel.
    """
    import numpy as np

    dye = [r for r in records if _get_material_assignment(r) == dye_token]
    if len(dye) < 10:
        return {
            "observable": False,
            "reason": f"Insufficient dye wells for vignette fit (found {len(dye)}, need >= 10)",
            "recommendation": "Ensure plate includes flatfield dye wells and material_assignment is present.",
            "model": model,
            "fit_quality": None,
            "edge_multiplier": None,
            "center_multiplier": None,
        }

    # Extract geometry and intensities
    radii = []
    intensities = {ch: [] for ch in channel_order}

    for rec in dye:
        well_id = rec.get("well_id")
        if not well_id:
            continue
        try:
            r_idx, c_idx = _well_to_rowcol(well_id)
            r_norm = _normalized_radius(r_idx, c_idx)
            radii.append(r_norm)

            morph = _get_morph(rec)
            for ch in channel_order:
                intensities[ch].append(morph.get(ch, np.nan))
        except Exception:
            continue

    if len(radii) < 10:
        return {
            "observable": False,
            "reason": "Failed to extract geometry from dye wells",
            "recommendation": "Check well_id format and morphology fields.",
            "model": model,
            "fit_quality": None,
            "edge_multiplier": None,
            "center_multiplier": None,
        }

    # Extract row/col indices for extended model testing
    row_indices = []
    col_indices = []
    for rec in dye:
        well_id = rec.get("well_id")
        if not well_id:
            continue
        try:
            r_idx, c_idx = _well_to_rowcol(well_id)
            row_indices.append(r_idx)
            col_indices.append(c_idx)
        except Exception:
            continue

    # Fit per channel: I = c0 + c1 * r^2
    # Also test extended model: I = c0 + c1 * r^2 + c2 * row + c3 * col
    edge_mult = {}
    center_mult = {}
    fit_quality = {
        "r_squared": {},
        "r_squared_extended": {},
        "rmse": {},
        "unmodeled_structure_detected": {}
    }

    channels_fitted = 0
    for ch in channel_order:
        y = np.array(intensities[ch])
        r_arr = np.array(radii)
        row_arr = np.array(row_indices)
        col_arr = np.array(col_indices)

        # Remove NaNs
        mask = ~np.isnan(y)
        if mask.sum() < 10:
            edge_mult[ch] = None
            center_mult[ch] = None
            fit_quality["r_squared"][ch] = None
            fit_quality["r_squared_extended"][ch] = None
            fit_quality["rmse"][ch] = None
            fit_quality["unmodeled_structure_detected"][ch] = None
            continue

        y_clean = y[mask]
        r_clean = r_arr[mask]
        row_clean = row_arr[mask]
        col_clean = col_arr[mask]

        # Fit 1: Radial only (I = c0 + c1 * r^2)
        X_radial = np.column_stack([np.ones_like(r_clean), r_clean**2])

        try:
            coeffs_radial, _, _, _ = np.linalg.lstsq(X_radial, y_clean, rcond=None)
            c0, c1 = coeffs_radial

            # Predict and compute R^2 (radial only)
            y_pred_radial = c0 + c1 * r_clean**2
            ss_res_radial = np.sum((y_clean - y_pred_radial)**2)
            ss_tot = np.sum((y_clean - np.mean(y_clean))**2)
            r_squared_radial = 1 - (ss_res_radial / ss_tot) if ss_tot > 0 else 0.0
            rmse = np.sqrt(np.mean((y_clean - y_pred_radial)**2))

            # Fit 2: Extended model (I = c0 + c1*r^2 + c2*row + c3*col)
            # Normalize row/col to [0, 1] for comparable coefficients
            row_norm = (row_clean - np.min(row_clean)) / (np.max(row_clean) - np.min(row_clean) + 1e-9)
            col_norm = (col_clean - np.min(col_clean)) / (np.max(col_clean) - np.min(col_clean) + 1e-9)
            X_extended = np.column_stack([np.ones_like(r_clean), r_clean**2, row_norm, col_norm])

            coeffs_extended, _, _, _ = np.linalg.lstsq(X_extended, y_clean, rcond=None)
            y_pred_extended = X_extended @ coeffs_extended
            ss_res_extended = np.sum((y_clean - y_pred_extended)**2)
            r_squared_extended = 1 - (ss_res_extended / ss_tot) if ss_tot > 0 else 0.0

            # Detect unmodeled structure: if R² improves significantly with row/col
            delta_rsq = r_squared_extended - r_squared_radial
            unmodeled_structure = delta_rsq > 0.1  # Threshold: 10% improvement

            # Edge multiplier = intensity at r=1 / intensity at r=0
            center_intensity = c0
            edge_intensity = c0 + c1
            edge_multiplier = edge_intensity / center_intensity if center_intensity > 0 else None

            edge_mult[ch] = float(edge_multiplier) if edge_multiplier is not None else None
            center_mult[ch] = 1.0  # By definition (normalized to center)
            fit_quality["r_squared"][ch] = float(r_squared_radial)
            fit_quality["r_squared_extended"][ch] = float(r_squared_extended)
            fit_quality["rmse"][ch] = float(rmse)
            fit_quality["unmodeled_structure_detected"][ch] = bool(unmodeled_structure)

            if edge_multiplier is not None:
                channels_fitted += 1

        except np.linalg.LinAlgError:
            edge_mult[ch] = None
            center_mult[ch] = None
            fit_quality["r_squared"][ch] = None
            fit_quality["r_squared_extended"][ch] = None
            fit_quality["rmse"][ch] = None
            fit_quality["unmodeled_structure_detected"][ch] = None

    # Require at least 3 channels fitted to mark observable
    if channels_fitted < 3:
        return {
            "observable": False,
            "reason": f"Vignette fit failed for too many channels (only {channels_fitted}/5 succeeded)",
            "recommendation": "Check dye well intensities and plate geometry.",
            "model": model,
            "fit_quality": fit_quality,
            "edge_multiplier": edge_mult,
            "center_multiplier": center_mult,
        }

    return {
        "observable": True,
        "reason": None,
        "recommendation": None,
        "model": model,
        "fit_quality": fit_quality,
        "edge_multiplier": edge_mult,
        "center_multiplier": center_mult,
    }


def estimate_saturation(
    records: List[Dict[str, Any]],
    channel_order: List[str],
) -> Dict[str, Any]:
    """
    Estimate saturation thresholds and fractions using metadata + distribution analysis.

    Uses both:
      - detector_metadata.is_saturated flags (if present)
      - intensity distribution pile-up detection (p99, max, top_bin_fraction)
    """
    import numpy as np

    # Extract per-channel saturation flags and intensities
    per_ch_flags = {ch: [] for ch in channel_order}
    per_ch_intensities = {ch: [] for ch in channel_order}

    for rec in records:
        md = _get_detector_metadata(rec)
        sat = md.get("is_saturated") or {}
        morph = _get_morph(rec)

        for ch in channel_order:
            # Saturation flag
            if isinstance(sat, dict) and ch in sat:
                per_ch_flags[ch].append(bool(sat[ch]))

            # Intensity
            val = morph.get(ch)
            if val is not None:
                per_ch_intensities[ch].append(float(val))

    # Build per-channel report
    per_ch_report = {}
    channels_observable = 0

    for ch in channel_order:
        flags = per_ch_flags[ch]
        intensities = per_ch_intensities[ch]

        if not intensities:
            per_ch_report[ch] = {
                "saturation_fraction": None,
                "threshold_estimate": None,
                "p99": None,
                "max": None,
                "top_bin_fraction": None,
            }
            continue

        intensities_arr = np.array(intensities)
        p99 = float(np.percentile(intensities_arr, 99))
        p999 = float(np.percentile(intensities_arr, 99.9))
        max_val = float(np.max(intensities_arr))

        # Top bin fraction: fraction of values within 0.1% of max
        epsilon = max(0.001 * max_val, 1e-6)
        top_bin_mask = intensities_arr >= (max_val - epsilon)
        top_bin_fraction = float(np.mean(top_bin_mask))

        # Saturation fraction from flags
        if flags:
            sat_frac = float(np.mean([1.0 if f else 0.0 for f in flags]))
        else:
            # Fallback: use top_bin_fraction as proxy
            sat_frac = top_bin_fraction if top_bin_fraction > 0.01 else 0.0

        # Threshold estimate: use p999 if we see pile-up, else None
        threshold_est = p999 if top_bin_fraction > 0.05 else None

        # Confidence assessment: did we actually observe clipping?
        cap_inferred = top_bin_fraction > 0.05  # Pile-up indicates we hit cap
        confidence = "high" if cap_inferred else ("medium" if sat_frac == 0 else "low")

        per_ch_report[ch] = {
            "saturation_fraction": sat_frac,
            "threshold_estimate": threshold_est,
            "p99": p99,
            "p999": p999,
            "max_observed": max_val,
            "top_bin_fraction": top_bin_fraction,
            "cap_inferred": cap_inferred,
            "confidence": confidence,
        }

        if sat_frac is not None or threshold_est is not None:
            channels_observable += 1

    if channels_observable == 0:
        return {
            "observable": False,
            "reason": "No saturation data (flags or distribution) for any channel.",
            "recommendation": "Ensure detector_metadata includes is_saturated flags or add high-intensity samples.",
            "per_channel": per_ch_report,
        }

    # Global confidence summary
    all_confidences = [ch_data.get("confidence") for ch_data in per_ch_report.values() if ch_data.get("confidence")]
    any_high_conf = any(c == "high" for c in all_confidences)
    overall_confidence = "high" if any_high_conf else ("medium" if all_confidences else "low")

    return {
        "observable": True,
        "reason": None,
        "recommendation": None,
        "per_channel": per_ch_report,
        "overall_confidence": overall_confidence,
        "interpretation": (
            "No clipping observed; saturation cap is above observed max values. "
            "Threshold estimates are extrapolations, not direct observations."
        ) if not any_high_conf else "Clipping detected; threshold estimates based on pile-up analysis.",
    }


def estimate_quantization(
    records: List[Dict[str, Any]],
    channel_order: List[str],
    *,
    dye_token: str = "FLATFIELD_DYE_LOW",
) -> Dict[str, Any]:
    """
    Estimate quantization step using delta histogram analysis on dye wells.

    Method:
      1. Extract intensities from dye wells (low variance, stable)
      2. Compute adjacent differences after sorting
      3. Histogram the non-zero diffs to find modal step size
      4. Cross-check with detector_metadata.quant_step if present
    """
    import numpy as np
    from collections import Counter

    # First try detector_metadata
    quant_steps_meta: Dict[str, List[float]] = {ch: [] for ch in channel_order}
    for r in records:
        md = _get_detector_metadata(r)
        qs = md.get("quant_step") or md.get("quantization_step") or {}
        if isinstance(qs, dict):
            for ch in channel_order:
                v = _safe_float(qs.get(ch))
                if v is not None and v > 0:
                    quant_steps_meta[ch].append(v)

    # Also do delta-based estimation from dye wells
    dye = [r for r in records if _get_material_assignment(r) == dye_token]

    per_ch = {}
    channels_with_estimate = 0

    for ch in channel_order:
        # Try metadata first
        meta_vals = quant_steps_meta.get(ch, [])
        if meta_vals:
            step_meta = float(np.mean(meta_vals))
        else:
            step_meta = None

        # Try delta-based estimation
        if len(dye) >= 20:
            intensities = []
            for rec in dye:
                morph = _get_morph(rec)
                val = morph.get(ch)
                if val is not None and val > 0:
                    intensities.append(val)

            if len(intensities) >= 20:
                intensities_sorted = np.sort(intensities)
                diffs = np.diff(intensities_sorted)

                # Filter: keep diffs > 0.01 and < 10 (reasonable LSB range)
                diffs_filtered = diffs[(diffs > 0.01) & (diffs < 10)]

                if len(diffs_filtered) >= 10:
                    # Bin diffs into 0.01 width bins and find mode
                    hist, bin_edges = np.histogram(diffs_filtered, bins=100)
                    mode_idx = np.argmax(hist)
                    step_delta = (bin_edges[mode_idx] + bin_edges[mode_idx + 1]) / 2.0

                    # Use mode if it's significant (>5% of diffs in that bin)
                    if hist[mode_idx] > len(diffs_filtered) * 0.05:
                        step_estimate = float(step_delta)
                    else:
                        step_estimate = None
                else:
                    step_estimate = None
            else:
                step_estimate = None
        else:
            step_estimate = None

        # Prefer metadata, fallback to delta-based
        final_step = step_meta if step_meta is not None else step_estimate
        quantization_detected = final_step is not None

        per_ch[ch] = {
            "quant_step_estimate": final_step,
            "quant_step_from_metadata": step_meta,
            "quant_step_from_delta": step_estimate,
            "quantization_detected": quantization_detected,
        }

        if quantization_detected:
            channels_with_estimate += 1

    if channels_with_estimate == 0:
        return {
            "observable": False,
            "reason": "No quantization detected (metadata reports 0.0, delta estimation found no modal step).",
            "recommendation": "Enable quantization in detector simulation or use higher bit-depth samples.",
            "per_channel": per_ch,
            "cross_channel_consistency": None,
        }

    # Cross-channel consistency check
    detected_steps = [v["quant_step_estimate"] for v in per_ch.values() if v["quant_step_estimate"] is not None]

    if len(detected_steps) >= 2:
        mean_step = float(np.mean(detected_steps))
        std_step = float(np.std(detected_steps))
        cv_step = std_step / mean_step if mean_step > 0 else None

        # Consistent if CV < 20%
        consistent = cv_step is not None and cv_step < 0.20

        cross_channel_consistency = {
            "mean_step": mean_step,
            "std_step": std_step,
            "cv": cv_step,
            "is_consistent": consistent,
            "interpretation": (
                "Quantization step consistent across channels (CV < 20%)."
                if consistent
                else "WARNING: Quantization step varies across channels (CV >= 20%). May indicate smoothing or per-channel scaling."
            ),
        }
    else:
        cross_channel_consistency = None

    return {
        "observable": True,
        "reason": None,
        "recommendation": None,
        "per_channel": per_ch,
        "cross_channel_consistency": cross_channel_consistency,
    }


def recommend_exposure(
    report: Dict[str, Any],
    channel_order: List[str],
) -> Dict[str, Any]:
    """
    Provide exposure recommendations using saturation thresholds.

    Policy:
      - Target: keep peak signals < 80% of saturation threshold (target_fraction_of_saturation)
      - If floor observable: also ensure signal > 10*floor_sigma (floor_margin_sigma)
      - If floor not observable: warn but proceed with saturation-only guidance

    Recommendations:
      - dim: for bright samples (avoid saturation)
      - normal: current exposure OK
      - bright: for dim samples (pull off floor if observable)
    """
    import numpy as np

    floor = report.get("floor", {})
    sat = report.get("saturation", {})

    floor_observable = bool(floor.get("observable"))
    sat_observable = bool(sat.get("observable"))

    warnings = []
    if not floor_observable:
        warnings.append("Floor unobservable: cannot guarantee signal above floor by k*sigma.")

    if not sat_observable:
        return {
            "observable": False,
            "reason": "Saturation not observable: cannot make safe exposure recommendations.",
            "recommendation": "Ensure saturation metadata exists or add high-intensity samples.",
            "policy": {
                "target_fraction_of_saturation": 0.80,
                "floor_margin_sigma": None,
            },
            "per_channel": None,
            "global": {"warnings": warnings},
        }

    # Extract saturation thresholds (p99 or threshold_estimate)
    sat_per_ch = sat.get("per_channel", {})

    per_ch = {}
    for ch in channel_order:
        ch_sat = sat_per_ch.get(ch, {})
        threshold = ch_sat.get("threshold_estimate") or ch_sat.get("p999") or ch_sat.get("p99")
        max_val = ch_sat.get("max")

        if threshold is None and max_val is None:
            per_ch[ch] = {
                "recommended_exposure_multiplier": None,
                "safe_max": None,
                "warnings": warnings + [f"No saturation threshold for {ch}"],
            }
            continue

        # Safe max: 80% of threshold (or max if no pile-up)
        safe_max = threshold * 0.80 if threshold is not None else max_val * 0.80

        # Current exposure is 1.0 (from bead plate data)
        # If max_val is near safe_max, recommend lower exposure
        # If max_val is far below safe_max, can increase exposure
        if max_val is not None and safe_max is not None:
            headroom = safe_max / max_val if max_val > 0 else 1.0

            if headroom < 1.2:
                # Close to saturation - recommend dimming
                rec_mult = 0.7
                ch_warnings = warnings + [f"{ch}: near saturation (max={max_val:.1f}, safe={safe_max:.1f})"]
            elif headroom > 3.0:
                # Lots of headroom - can increase exposure
                rec_mult = min(headroom * 0.5, 2.0)  # Cap at 2x
                ch_warnings = warnings
            else:
                # Good range - current exposure OK
                rec_mult = 1.0
                ch_warnings = warnings
        else:
            rec_mult = 1.0
            ch_warnings = warnings

        per_ch[ch] = {
            "recommended_exposure_multiplier": rec_mult,
            "safe_max": safe_max,
            "current_max": max_val,
            "headroom_ratio": headroom if (max_val is not None and safe_max is not None) else None,
            "warnings": ch_warnings,
        }

    return {
        "observable": True,
        "reason": None,
        "recommendation": None,
        "policy": {
            "target_fraction_of_saturation": 0.80,
            "floor_margin_sigma": 10.0 if floor_observable else None,
        },
        "per_channel": per_ch,
        "global": {"warnings": warnings},
    }


# ----------------------------
# Main calibration entrypoint
# ----------------------------

def calibrate_from_observations(
    observations_jsonl: str,
    design_json: Optional[str] = None,
    outdir: Optional[str] = None,
    channel_order: Optional[List[str]] = None,
    detector_config_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main entrypoint. Reads observations, optionally reads design, produces a JSON-serializable report.

    Behavior:
      - Always returns a report with all top-level keys present.
      - Each estimator block includes observable flag plus reason/recommendation when false.
      - Partial calibration is allowed and expected.

    Caller can write outputs or use returned dict.
    """
    chs = channel_order or list(DEFAULT_CHANNEL_ORDER)
    obs_path = Path(observations_jsonl)
    design_path = Path(design_json) if design_json else None

    records = _read_jsonl(obs_path)
    design = _load_design(design_path) if design_path else None

    report = build_empty_report(
        obs_path=str(obs_path),
        design_path=str(design_path) if design_path else None,
        channel_order=chs,
        design=design,
        detector_config_snapshot=detector_config_snapshot,
    )
    report["run_summary"] = _obs_meta_minimal(records)

    # Estimators
    report["floor"] = estimate_floor(records, chs)
    report["vignette"] = fit_vignette(records, chs)
    report["saturation"] = estimate_saturation(records, chs)
    report["quantization"] = estimate_quantization(records, chs)
    report["exposure_recommendations"] = recommend_exposure(report, chs)

    # Notes: enforce your chosen framing
    if not report["floor"]["observable"]:
        report["notes"].append("Partial calibration: floor not observable; vignette/saturation/quantization may still be actionable.")

    # Write outputs if outdir provided
    if outdir:
        od = Path(outdir)
        od.mkdir(parents=True, exist_ok=True)
        _write_json(od / "calibration_report.json", report)

    return report


# ----------------------------
# CLI
# ----------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Calibrate detector from bead/dye plate observations (partial allowed).")
    p.add_argument("--obs", required=True, help="Path to observations.jsonl")
    p.add_argument("--design", required=False, default=None, help="Path to bead plate design JSON (optional)")
    p.add_argument("--outdir", required=True, help="Output directory for calibration_report.json")
    p.add_argument(
        "--channels",
        required=False,
        default=",".join(DEFAULT_CHANNEL_ORDER),
        help="Comma-separated channel order (default: er,mito,nucleus,actin,rna)",
    )
    return p


def main() -> None:
    ap = _build_argparser()
    args = ap.parse_args()
    channel_order = [c.strip() for c in args.channels.split(",") if c.strip()]

    calibrate_from_observations(
        observations_jsonl=args.obs,
        design_json=args.design,
        outdir=args.outdir,
        channel_order=channel_order,
    )


if __name__ == "__main__":
    main()
