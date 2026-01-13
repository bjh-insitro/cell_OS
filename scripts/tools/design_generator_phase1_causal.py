"""
Phase 1 Causal Design Generator (STRICT)

Goal: causal estimation of a single intervention (compound dose-response)
under controlled conditions, while preserving the Phase 0 scaffold:

- Fixed biological sentinel scaffold (diagnostic geometry baked in)
- Instrument-only sentinels in excluded wells (do not count toward 88)
- Within-plate randomized treatment placement (prevents spatial confounding)
- High replication for defensible causal contrasts
- Exact 88-well accounting (fail fast)

Usage:
    python design_generator_phase1_causal.py
"""

from __future__ import annotations

from typing import Dict, List, Optional
from datetime import datetime
import json
import os
import sys
import random
import hashlib

# Import fixed sentinel scaffold
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase0_sentinel_scaffold import (
    get_sentinel_tokens,
    SCAFFOLD_ID,
    SCAFFOLD_HASH,
)


# -------------------------
# RNG
# -------------------------

def make_rng(seed: int, salt: str) -> random.Random:
    h = hashlib.sha256(f"{seed}|{salt}".encode("utf-8")).hexdigest()
    return random.Random(int(h[:16], 16))


# -------------------------
# Helpers
# -------------------------

def all_96_positions() -> List[str]:
    rows = "ABCDEFGH"
    cols = range(1, 13)
    return [f"{r}{c:02d}" for r in rows for c in cols]


def build_experimental_tokens(
    *,
    cell_line: str,
    compound: str,
    ic50_uM: float,
    dose_multipliers: List[float],
    reps_per_dose: int,
    vehicle_reps: int,
    day: int,
    operator: str,
    timepoint_h: float,
    include_absolute_doses: Optional[List[float]] = None,
) -> List[Dict]:
    tokens: List[Dict] = []

    # Vehicle controls (explicit causal baseline)
    for _ in range(vehicle_reps):
        tokens.append({
            "cell_line": cell_line,
            "compound": "DMSO",
            "dose_uM": 0.0,
            "dose_type": "vehicle",
            "timepoint_h": timepoint_h,
            "day": day,
            "operator": operator,
            "is_sentinel": False,
        })

    # Dose ladder
    for mult in dose_multipliers:
        dose_uM = float(mult) * float(ic50_uM)
        for _ in range(reps_per_dose):
            tokens.append({
                "cell_line": cell_line,
                "compound": compound,
                "dose_uM": dose_uM,
                "dose_type": "ic50_scaled",
                "timepoint_h": timepoint_h,
                "day": day,
                "operator": operator,
                "is_sentinel": False,
            })

    # Optional absolute anchors (useful if you think IC50 is wrong)
    if include_absolute_doses:
        for d in include_absolute_doses:
            tokens.append({
                "cell_line": cell_line,
                "compound": compound,
                "dose_uM": float(d),
                "dose_type": "absolute",
                "timepoint_h": timepoint_h,
                "day": day,
                "operator": operator,
                "is_sentinel": False,
            })

    return tokens


# -------------------------
# Main
# -------------------------

def create_phase1_causal_design(
    design_id: str = "phase1_causal_v1",
    description: str = "Causal design: single compound dose-response with high replication; fixed scaffold + instrument sentinels",
    design_seed: int = 1337,

    # What you are trying to estimate causally
    cell_lines: List[str] = None,
    compound_by_cell_line: Dict[str, str] = None,
    ic50_by_compound: Dict[str, float] = None,

    # Batch structure
    days: List[int] = None,
    operators: List[str] = None,
    timepoints_h: List[float] = None,

    # Causal core
    dose_multipliers: List[float] = None,
    reps_per_dose: int = 8,
    vehicle_reps: int = 12,

    # Optional absolute anchors (kept off by default for strict causality)
    absolute_anchors_by_compound: Optional[Dict[str, List[float]]] = None,
) -> Dict:

    # Defaults
    if cell_lines is None:
        cell_lines = ["A549", "HepG2"]

    if compound_by_cell_line is None:
        # Pick one "causal target" per cell line
        compound_by_cell_line = {
            "A549": "tunicamycin",
            "HepG2": "oligomycin",
        }

    if ic50_by_compound is None:
        ic50_by_compound = {
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

    if days is None:
        days = [1, 2]

    if operators is None:
        operators = ["Operator_A", "Operator_B"]

    if timepoints_h is None:
        # Keep time fixed/small set for causal clarity
        timepoints_h = [24.0]

    if dose_multipliers is None:
        dose_multipliers = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0]

    # Plate geometry and exclusions
    excluded = {"A01", "A06", "A07", "A12", "H01", "H06", "H07", "H12"}
    instrument_positions = ["A01", "A12"]
    assert set(instrument_positions).issubset(excluded)

    all_pos = all_96_positions()
    usable_pos = [p for p in all_pos if p not in excluded]

    # Sentinels: fixed scaffold
    scaffold = get_sentinel_tokens()
    scaffold_positions = {s["position"] for s in scaffold}
    n_bio_sentinels = len(scaffold)

    wells: List[Dict] = []

    for cell_line in cell_lines:
        if cell_line not in compound_by_cell_line:
            raise ValueError(f"Missing compound_by_cell_line for {cell_line}")

        compound = compound_by_cell_line[cell_line]
        if compound not in ic50_by_compound:
            raise ValueError(f"Missing ic50 for compound {compound}")
        ic50_uM = ic50_by_compound[compound]

        # Available experimental positions are fixed per cell line,
        # but assignment within a plate is randomized to prevent spatial confounding.
        exp_positions_base = [p for p in usable_pos if p not in scaffold_positions]

        for day in days:
            for operator in operators:
                for t in timepoints_h:
                    plate_id = f"{cell_line}_Day{day}_{operator}_T{t}h"

                    # Build experimental tokens for causal estimation
                    anchors = None
                    if absolute_anchors_by_compound and compound in absolute_anchors_by_compound:
                        anchors = absolute_anchors_by_compound[compound]

                    exp_tokens = build_experimental_tokens(
                        cell_line=cell_line,
                        compound=compound,
                        ic50_uM=ic50_uM,
                        dose_multipliers=dose_multipliers,
                        reps_per_dose=reps_per_dose,
                        vehicle_reps=vehicle_reps,
                        day=day,
                        operator=operator,
                        timepoint_h=t,
                        include_absolute_doses=anchors,
                    )

                    # Strict accounting: experimental wells + biological sentinels = 88 exactly
                    if len(exp_tokens) + n_bio_sentinels != 88:
                        raise ValueError(
                            f"{plate_id}: bad plate fill\n"
                            f"  experimental={len(exp_tokens)}\n"
                            f"  biological_sentinels={n_bio_sentinels}\n"
                            f"  total_in_88_budget={len(exp_tokens) + n_bio_sentinels} (expected 88)\n"
                            f"  Hint: adjust reps_per_dose/vehicle_reps or add/remove anchors."
                        )

                    if len(exp_positions_base) != len(exp_tokens):
                        raise ValueError(
                            f"{plate_id}: position/token mismatch\n"
                            f"  exp_positions_available={len(exp_positions_base)}\n"
                            f"  exp_tokens={len(exp_tokens)}\n"
                            f"  (This usually means your scaffold size changed.)"
                        )

                    # Randomize placement WITHIN PLATE to prevent spatial confounding
                    rng = make_rng(design_seed, f"plate_assign|{plate_id}")
                    exp_positions = exp_positions_base.copy()
                    rng.shuffle(exp_positions)

                    # Place experimental wells
                    for tok, pos in zip(exp_tokens, exp_positions):
                        wells.append({
                            **tok,
                            "plate_id": plate_id,
                            "well_pos": pos,
                        })

                    # Place biological sentinels at fixed scaffold positions
                    for s in scaffold:
                        wells.append({
                            "cell_line": cell_line,
                            "compound": s["compound"],
                            "dose_uM": s["dose_uM"],
                            "timepoint_h": t,
                            "day": day,
                            "operator": operator,
                            "is_sentinel": True,
                            "sentinel_type": s["sentinel_type"],
                            # If you want true "bridge" semantics, do it explicitly later.
                            # For Phase 1 causal, these can stay diagnostic not bridge.
                            "is_bridge_control": False,
                            "plate_id": plate_id,
                            "well_pos": s["position"],
                        })

                    # Place instrument-only sentinels (excluded wells, outside 88-well budget)
                    for pos in instrument_positions:
                        wells.append({
                            "cell_line": cell_line,
                            "compound": None,
                            "dose_uM": 0.0,
                            "timepoint_h": t,
                            "day": day,
                            "operator": operator,
                            "is_sentinel": True,
                            "sentinel_type": "instrument",
                            "readout_model": "instrument_only",
                            "plate_id": plate_id,
                            "well_pos": pos,
                        })

    plates = sorted({w["plate_id"] for w in wells})

    design = {
        "design_id": design_id,
        "design_type": "phase1_causal",
        "description": description,
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "design_seed": design_seed,
            "scaffold_id": SCAFFOLD_ID,
            "scaffold_hash": SCAFFOLD_HASH,
            "n_plates": len(plates),
            "plate_size": 96,
            "biological_wells_per_plate": 88,
            "instrument_sentinels_per_plate": 2,
            "primary_goal": "causal_effect_estimation",
            "not_for": ["broad_manifold_mapping"],
            "batch_structure": {
                "days": days,
                "operators": operators,
                "timepoints_h": timepoints_h,
                "cell_lines": cell_lines,
            },
            "causal_core": {
                "dose_multipliers": dose_multipliers,
                "reps_per_dose": reps_per_dose,
                "vehicle_reps": vehicle_reps,
                "compound_by_cell_line": compound_by_cell_line,
            },
        },
        "wells": wells,
    }

    return design


if __name__ == "__main__":
    design = create_phase1_causal_design()

    out = "../data/designs/phase1_causal_v1.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)

    with open(out, "w") as f:
        json.dump(design, f, indent=2)

    print(f"✅ Phase 1 causal design generated: {out}")
    print(f"   Plates: {design['metadata']['n_plates']}")
    print(f"   Wells: {len(design['wells'])}")
    print(f"   Example plate: {sorted({w['plate_id'] for w in design['wells']})[0]}")
