"""
Shape Learning Design Generator

This generator creates a design optimized for learning the shape of the system
by separating instrument truth from biological truth.

Key improvements over phase0_v2:
1. Instrument sentinel class (non-biological control wells)
2. Diagnostic sentinel geometry (edge vs center placement)
3. Bridge controls across day/operator (extra redundancy)
4. Absolute dose ladder for select compounds (not just IC50-scaled)
5. Timepoint perturbation for one compound (exposes temporal aliasing)
6. Explicit metadata about design goals

Usage:
    python design_generator_shape_learning.py
"""

from __future__ import annotations

from typing import Dict, List
from datetime import datetime
import json
import sys
import os
import random
import hashlib

# Import fixed sentinel scaffold
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase0_sentinel_scaffold import (
    get_sentinel_tokens,
    SCAFFOLD_ID,
    SCAFFOLD_HASH,
)


def make_rng(design_seed: int | None, salt: str) -> random.Random:
    """Create deterministic RNG seeded per design + salt."""
    base = str(design_seed if design_seed is not None else 0) + "|" + salt
    h = hashlib.sha256(base.encode("utf-8")).hexdigest()
    seed_int = int(h[:16], 16)
    return random.Random(seed_int)


def create_shape_learning_design(
    design_id: str = "phase0_shape_learning_v1",
    description: str = "Design optimized for learning system shape by separating instrument from biological truth",
    design_seed: int = 42,
) -> Dict:
    """
    Generate shape learning design with enhanced diagnostics.

    IMPORTANT ACCOUNTING MODEL
    - 96-well plate physically exists.
    - We keep the original phase0 "budgeted" footprint of 88 wells (96 minus 8 excluded).
    - We ALSO add 2 instrument sentinels placed in excluded wells (A01, A12).
    - Therefore, each plate contains:
        - 60 experimental wells (in the 88-well budget)
        - 28 biological sentinels (in the 88-well budget)
        - 2 instrument sentinels (outside the 88-well budget, but included in wells list)
      => 90 total wells in the design JSON per plate.
    """

    # Configuration
    cell_lines = ["A549", "HepG2"]
    compounds_group1 = ["tBHQ", "H2O2", "tunicamycin", "thapsigargin", "CCCP"]
    compounds_group2 = ["oligomycin", "etoposide", "MG132", "nocodazole", "paclitaxel"]

    compound_ic50 = {
        "tBHQ": 30.0,
        "H2O2": 100.0,
        "tunicamycin": 1.0,
        "thapsigargin": 0.5,
        "CCCP": 5.0,
        "oligomycin": 1.0,
        "etoposide": 10.0,
        "MG132": 1.0,
        "nocodazole": 0.5,
        "paclitaxel": 0.01,
    }

    # Dose configuration
    dose_multipliers = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0]
    reduced_dose_compounds = ["CCCP", "paclitaxel"]  # Skip 30× for these
    replicates_per_dose = 2

    # Absolute dose anchors (no replicates)
    absolute_doses_uM = [0.3, 3.0]
    absolute_dose_compounds = ["tBHQ", "oligomycin"]

    # Batch structure
    days = [1, 2]
    operators = ["Operator_A", "Operator_B"]
    timepoints_h = [12.0, 24.0, 48.0]

    # Timepoint perturbation for one compound
    perturbed_compound = "thapsigargin"
    perturbed_timepoints = {
        1: {"Operator_A": [6.0, 24.0, 48.0], "Operator_B": [12.0, 24.0, 48.0]},
        2: {"Operator_A": [12.0, 24.0, 48.0], "Operator_B": [12.0, 24.0, 48.0]},
    }

    plate_format = 96

    # Exclusions (phase0_v2 pattern)
    excluded_wells = {"A01", "A06", "A07", "A12", "H01", "H06", "H07", "H12"}

    # Plate grid
    rows = ["A", "B", "C", "D", "E", "F", "G", "H"]
    cols = list(range(1, 13))
    all_well_positions = [f"{r}{c:02d}" for r in rows for c in cols]
    budgeted_positions = [p for p in all_well_positions if p not in excluded_wells]  # 88 wells

    # Sentinel schema (for metadata only; actual positions come from scaffold + fixed instrument)
    sentinel_config_per_plate = {
        "instrument": {"compound": None, "dose_uM": 0.0, "n": 2, "is_bridge": False},
        "vehicle": {"compound": "DMSO", "dose_uM": 0.0, "n": 6, "is_bridge": False},
        "vehicle_bridge": {"compound": "DMSO", "dose_uM": 0.0, "n": 2, "is_bridge": True},
        "ER_mid": {"compound": "thapsigargin", "dose_uM": 0.5, "n": 3, "is_bridge": False},
        "ER_mid_bridge": {"compound": "thapsigargin", "dose_uM": 0.5, "n": 2, "is_bridge": True},
        "mito_mid": {"compound": "oligomycin", "dose_uM": 1.0, "n": 5, "is_bridge": False},
        "proteostasis": {"compound": "MG132", "dose_uM": 1.0, "n": 5, "is_bridge": False},
        "oxidative": {"compound": "tBHQ", "dose_uM": 30.0, "n": 3, "is_bridge": False},
    }
    # Total biological (budgeted): 28. Instrument (unbudgeted but included): 2.

    wells: List[Dict] = []

    for cell_line in cell_lines:
        compounds = compounds_group1 if cell_line == "A549" else compounds_group2

        # Deterministic shuffle of experimental positions per cell line (stable across plates)
        cell_line_rng = make_rng(design_seed, f"exp_positions|{cell_line}")
        cell_line_budgeted_positions = budgeted_positions.copy()

        # Fixed scaffold sentinels
        scaffold_tokens = get_sentinel_tokens()
        positioned_sentinels: List[Dict] = []
        for tok in scaffold_tokens:
            positioned_sentinels.append(
                {
                    "compound": tok["compound"],
                    "dose_uM": tok["dose_uM"],
                    "is_sentinel": True,
                    "sentinel_type": tok["sentinel_type"],
                    "is_bridge_control": False,
                    "position": tok["position"],
                }
            )

        # Mark bridges: first 2 vehicle + first 2 ER_mid
        bridge_count = {"vehicle": 0, "ER_mid": 0}
        for s in positioned_sentinels:
            if s["sentinel_type"] == "vehicle" and bridge_count["vehicle"] < 2:
                s["is_bridge_control"] = True
                bridge_count["vehicle"] += 1
            elif s["sentinel_type"] == "ER_mid" and bridge_count["ER_mid"] < 2:
                s["is_bridge_control"] = True
                bridge_count["ER_mid"] += 1

        # Instrument sentinels (fixed excluded wells, included in JSON wells list)
        instrument_positions = ["A01", "A12"]
        for pos in instrument_positions:
            positioned_sentinels.append(
                {
                    "compound": None,
                    "dose_uM": 0.0,
                    "is_sentinel": True,
                    "sentinel_type": "instrument",
                    "is_bridge_control": False,
                    "position": pos,
                    "readout_model": "instrument_only",
                }
            )

        sentinel_positions = {s["position"] for s in positioned_sentinels}

        # Remove sentinel positions from experimental pool (only affects budgeted positions)
        cell_line_exp_positions = [p for p in cell_line_budgeted_positions if p not in sentinel_positions]
        cell_line_rng.shuffle(cell_line_exp_positions)

        for day in days:
            for operator in operators:
                active_timepoints = (
                    perturbed_timepoints.get(day, {}).get(operator, timepoints_h)
                    if perturbed_compound in compounds
                    else timepoints_h
                )

                for timepoint in active_timepoints:
                    plate_id = f"{cell_line}_Day{day}_{operator}_T{timepoint}h"

                    experimental_tokens: List[Dict] = []

                    for compound in compounds:
                        ic50 = compound_ic50.get(compound, 1.0)

                        ic50_doses = (
                            [d for d in dose_multipliers if d < 30.0]
                            if compound in reduced_dose_compounds
                            else dose_multipliers
                        )

                        for dose_mult in ic50_doses:
                            dose_uM = dose_mult * ic50
                            for _ in range(replicates_per_dose):
                                experimental_tokens.append(
                                    {
                                        "cell_line": cell_line,
                                        "compound": compound,
                                        "dose_uM": dose_uM,
                                        "dose_type": "ic50_scaled",
                                        "timepoint_h": timepoint,
                                        "day": day,
                                        "operator": operator,
                                        "is_sentinel": False,
                                    }
                                )

                        if compound in absolute_dose_compounds:
                            for abs_dose in absolute_doses_uM:
                                experimental_tokens.append(
                                    {
                                        "cell_line": cell_line,
                                        "compound": compound,
                                        "dose_uM": abs_dose,
                                        "dose_type": "absolute",
                                        "timepoint_h": timepoint,
                                        "day": day,
                                        "operator": operator,
                                        "is_sentinel": False,
                                    }
                                )

                    # Strict accounting
                    n_experimental = len(experimental_tokens)

                    n_biological_sentinels = len([s for s in positioned_sentinels if s["sentinel_type"] != "instrument"])
                    n_instrument_sentinels = len([s for s in positioned_sentinels if s["sentinel_type"] == "instrument"])

                    n_budgeted_positions = len(cell_line_exp_positions)  # positions available for experimental
                    budgeted_wells_per_plate = len(budgeted_positions)  # 88
                    budgeted_total_expected = budgeted_wells_per_plate  # should equal exp + biological

                    total_wells_per_plate = budgeted_wells_per_plate + n_instrument_sentinels  # 90

                    if n_experimental != n_budgeted_positions:
                        raise ValueError(
                            f"Plate {plate_id}: Experimental position mismatch!\n"
                            f"  Generated experimental tokens: {n_experimental}\n"
                            f"  Available experimental positions: {n_budgeted_positions}\n"
                            f"  (Budgeted wells per plate: {budgeted_wells_per_plate})\n"
                            f"  Biological sentinels (budgeted): {n_biological_sentinels}\n"
                            f"  Instrument sentinels (unbudgeted but included): {n_instrument_sentinels}"
                        )

                    if n_experimental + n_biological_sentinels != budgeted_total_expected:
                        raise ValueError(
                            f"Plate {plate_id}: Budgeted total mismatch!\n"
                            f"  Experimental: {n_experimental}\n"
                            f"  Biological sentinels: {n_biological_sentinels}\n"
                            f"  Experimental + biological: {n_experimental + n_biological_sentinels}\n"
                            f"  Expected budgeted total: {budgeted_total_expected}"
                        )

                    # Assign positions to experimental wells
                    for i, token in enumerate(experimental_tokens):
                        well_pos = cell_line_exp_positions[i]
                        wells.append({**token, "plate_id": plate_id, "well_pos": well_pos})

                    # Add sentinels (biological + instrument)
                    for sentinel in positioned_sentinels:
                        well_data = {
                            "cell_line": cell_line,
                            "compound": sentinel["compound"],
                            "dose_uM": sentinel["dose_uM"],
                            "timepoint_h": timepoint,
                            "day": day,
                            "operator": operator,
                            "is_sentinel": True,
                            "sentinel_type": sentinel["sentinel_type"],
                            "is_bridge_control": sentinel.get("is_bridge_control", False),
                            "plate_id": plate_id,
                            "well_pos": sentinel["position"],
                        }
                        if "readout_model" in sentinel:
                            well_data["readout_model"] = sentinel["readout_model"]
                        wells.append(well_data)

    unique_plates = sorted(set(w["plate_id"] for w in wells))

    # Derive per-plate counts directly from wells list
    n_plates = len(unique_plates)
    wells_per_plate_total = len(wells) // n_plates

    design = {
        "design_id": design_id,
        "design_type": "phase0_shape_learning",
        "description": description,
        "metadata": {
            "primary_goal": "nuisance_model_identification",
            "secondary_goal": "coarse_response_manifold",
            "not_for": ["mechanism_claims", "causal_inference"],
            "created_at": datetime.now().isoformat(),
            "design_seed": design_seed,
            "plate_format": plate_format,
            "n_plates": n_plates,
            # Total wells in JSON (includes instrument sentinels)
            "wells_per_plate": wells_per_plate_total,
            "wells_per_plate_total": wells_per_plate_total,
            # Budgeted wells (phase0 convention)
            "wells_per_plate_budgeted": len(budgeted_positions),
            "n_wells": len(wells),
            "cell_lines": cell_lines,
            "compounds_A549": compounds_group1,
            "compounds_HepG2": compounds_group2,
            "n_compounds": len(compounds_group1),
            "timepoints_h": timepoints_h,
            "days": days,
            "operators": operators,
            "experimental_conditions": {
                "doses": dose_multipliers,
                "replicates": replicates_per_dose,
                "absolute_doses_uM": absolute_doses_uM,
                "absolute_dose_compounds": absolute_dose_compounds,
                "reduced_dose_compounds": reduced_dose_compounds,
            },
            "sentinel_schema": {
                "policy": "fixed_scaffold_enhanced",
                "scaffold_id": SCAFFOLD_ID,
                "scaffold_hash": SCAFFOLD_HASH,
                "biological_sentinels_per_plate_budgeted": 28,
                "instrument_sentinels_per_plate_unbudgeted": 2,
                "total_sentinels_per_plate_in_json": 30,
                "types": sentinel_config_per_plate,
                "bridge_controls": ["vehicle", "ER_mid"],
                "instrument_positions": ["A01", "A12"],
                "excluded_wells": sorted(excluded_wells),
                "note": "88-well budgeted footprint (96-8 excluded) + 2 instrument sentinels in excluded wells; JSON contains 90 wells/plate.",
            },
            "enhancements": {
                "instrument_sentinels": True,
                "diagnostic_sentinel_geometry": True,
                "bridge_controls": True,
                "absolute_dose_ladder": True,
                "timepoint_perturbation": {"compound": perturbed_compound, "perturbation": perturbed_timepoints},
            },
            "batch_structure": {
                "orthogonal_factors": ["day", "operator", "timepoint"],
                "separate_factor": "cell_line",
                "randomization": f"Per-cell-line position shuffle with deterministic RNG (seed={design_seed})",
            },
        },
        "wells": wells,
    }

    return design


if __name__ == "__main__":
    design = create_shape_learning_design(
        design_id="phase0_shape_learning_v1",
        description="Design optimized for learning system shape by separating instrument from biological truth",
        design_seed=42,
    )

    output_path = "../data/designs/phase0_shape_learning_v1.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(design, f, indent=2)

    n_total = design["metadata"]["n_wells"]
    n_plates = design["metadata"]["n_plates"]
    n_exp = len([w for w in design["wells"] if not w["is_sentinel"]])
    n_sent = len([w for w in design["wells"] if w["is_sentinel"]])
    n_instr = len([w for w in design["wells"] if w.get("sentinel_type") == "instrument"])
    n_bridge = len([w for w in design["wells"] if w.get("is_bridge_control")])

    print(f"✅ Shape learning design generated: {output_path}")
    print(f"   Plates: {n_plates}")
    print(f"   Total wells: {n_total} (={n_plates}×{n_total//n_plates} per plate)")
    print(f"   Experimental wells: {n_exp}")
    print(f"   Sentinel wells: {n_sent} (instrument={n_instr})")
    print(f"   Bridge controls: {n_bridge}")
    print(f"   Budgeted wells/plate: {design['metadata']['wells_per_plate_budgeted']}  |  Total wells/plate in JSON: {design['metadata']['wells_per_plate_total']}")
