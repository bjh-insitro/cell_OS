"""
Phase 0 Founder Design Generator (Audit-Driven)

This generator enforces Phase 0 constraints by construction:
1. Fixed sentinel schema (no timepoint variance)
2. Batch-first allocation (identical conditions per timepoint)
3. Hard capacity constraints (no silent dropping)
4. Exact fill requirement (no partial plates)

Usage:
    python design_generator_phase0.py
"""

from typing import List, Dict, Set
from dataclasses import dataclass
from datetime import datetime
import json
import sys
import os
import random
import hashlib

# Import fixed sentinel scaffold
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase0_sentinel_scaffold import (
    SENTINEL_SCAFFOLD,
    get_sentinel_tokens,
    get_scaffold_metadata,
    SCAFFOLD_ID,
    SCAFFOLD_HASH,
)


def make_rng(design_seed: int | None, salt: str) -> random.Random:
    """
    Create a deterministic RNG seeded per design + salt.

    This ensures:
    - Same seed + salt = same shuffle (reproducible)
    - Different salt = independent shuffle (no coupling)
    - Per-plate shuffles use plate-specific salts
    """
    base = str(design_seed if design_seed is not None else 0) + "|" + salt
    h = hashlib.sha256(base.encode("utf-8")).hexdigest()
    # Fit into Python int range
    seed_int = int(h[:16], 16)
    return random.Random(seed_int)


@dataclass
class Violation:
    type: str
    severity: str  # 'error' or 'warning'
    message: str
    details: Dict


@dataclass
class PlatePlan:
    """Validated plate allocation plan"""
    plate_format: int  # 96 or 384
    available_wells: int
    sentinel_count: int
    experimental_count: int
    require_exact_fill: bool = True

    def validate(self) -> List[Violation]:
        """Hard capacity constraint - no silent failures"""
        violations = []
        total_needed = self.sentinel_count + self.experimental_count

        if total_needed > self.available_wells:
            violations.append(Violation(
                type='capacity_overflow',
                severity='error',
                message=f"Cannot fit {total_needed} wells into {self.available_wells} available.",
                details={
                    'sentinels': self.sentinel_count,
                    'experiments': self.experimental_count,
                    'available': self.available_wells,
                    'overflow': total_needed - self.available_wells,
                    'fix': 'Reduce sentinel count OR reduce experimental conditions OR use larger plate format',
                }
            ))

        if self.require_exact_fill and total_needed < self.available_wells:
            violations.append(Violation(
                type='capacity_underfill',
                severity='error',
                message=f"Only using {total_needed} of {self.available_wells} available wells.",
                details={
                    'sentinels': self.sentinel_count,
                    'experiments': self.experimental_count,
                    'available': self.available_wells,
                    'empty': self.available_wells - total_needed,
                    'note': 'Phase 0 requires exact fill. Add more conditions or sentinels.',
                }
            ))

        return violations


# Phase 0 Founder Policy: FIXED sentinel schema
PHASE0_SENTINEL_SCHEMA = {
    'vehicle': {'compound': 'DMSO', 'dose_uM': 0.0, 'n': 8},
    'ER_mid': {'compound': 'thapsigargin', 'dose_uM': 0.5, 'n': 5},
    'mito_mid': {'compound': 'oligomycin', 'dose_uM': 1.0, 'n': 5},
    'proteostasis': {'compound': 'MG132', 'dose_uM': 1.0, 'n': 5},
    'oxidative': {'compound': 'tBHQ', 'dose_uM': 30.0, 'n': 5},
}
# Total: 28 sentinels
# Works for ALL timepoints
# NO timepoint-dependent variance for Phase 0


def get_phase0_compound_ic50() -> Dict[str, float]:
    """IC50 values for Phase 0 compounds"""
    return {
        'tBHQ': 30.0,
        'H2O2': 100.0,
        'tunicamycin': 1.0,
        'thapsigargin': 0.5,
        'CCCP': 5.0,
        'oligomycin': 1.0,
        'etoposide': 10.0,
        'MG132': 1.0,
        'nocodazole': 0.5,
        'paclitaxel': 0.01,
    }


def generate_phase0_v2_founder(design_seed: int = 42):
    """
    Generate Phase 0 V2 Founder Design (audit-compliant)

    Args:
        design_seed: Seed for deterministic RNG (shuffles experimental positions per plate)

    Fixed parameters:
    - 2 cell lines: A549, HepG2 (separate plates)
    - 10 compounds × 6 doses × 2 replicates = 120 experimental conditions
    - Split into 2 groups of 5 compounds = 60 conditions per plate
    - 28 sentinels per plate (FIXED schema, all timepoints)
    - = 88 wells exactly (96-well with 8 excluded)
    - 3 timepoints: 12h, 24h, 48h
    - 2 days × 2 operators = 4 batch slices per timepoint
    - = 24 plates total
    """

    # Phase 0 V2 fixed parameters
    cell_lines = ['A549', 'HepG2']
    compounds = [
        'tBHQ', 'H2O2', 'tunicamycin', 'thapsigargin', 'CCCP',
        'oligomycin', 'etoposide', 'MG132', 'nocodazole', 'paclitaxel'
    ]
    dose_multipliers = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0]  # 6 doses
    replicates_per_dose = 2
    days = [1, 2]
    operators = ['Operator_A', 'Operator_B']
    timepoints_h = [12.0, 24.0, 48.0]

    # Plate format
    plate_format = 96
    n_rows, n_cols = 8, 12
    row_labels = [chr(65 + i) for i in range(n_rows)]  # A-H

    # Exclusions (Phase 0 V2: corners + mid-row)
    excluded_wells = {
        'A01', 'A12', 'H01', 'H12',  # Corners
        'A06', 'A07', 'H06', 'H07',  # Mid-row
    }

    all_well_positions = [f"{row}{col:02d}" for row in row_labels for col in range(1, n_cols + 1)]
    available_well_positions = [w for w in all_well_positions if w not in excluded_wells]
    available_wells_count = len(available_well_positions)  # 88

    # Sentinel count (FIXED for all timepoints)
    sentinel_count = sum(config['n'] for config in PHASE0_SENTINEL_SCHEMA.values())  # 28

    # Experimental conditions
    # 10 compounds × 6 doses × 2 reps = 120 total
    # Split into 2 groups of 5 compounds = 60 per plate
    experimental_count = 5 * 6 * 2  # 60

    # VALIDATE CAPACITY BEFORE GENERATING ANYTHING
    plan = PlatePlan(
        plate_format=plate_format,
        available_wells=available_wells_count,
        sentinel_count=sentinel_count,
        experimental_count=experimental_count,
        require_exact_fill=True,
    )

    violations = plan.validate()
    if violations:
        print("❌ CAPACITY VALIDATION FAILED")
        for v in violations:
            print(f"\n{v.severity.upper()}: {v.type}")
            print(f"  {v.message}")
            print(f"  Details: {json.dumps(v.details, indent=2)}")
        raise ValueError("Design violates capacity constraints. Cannot proceed.")

    print("✅ CAPACITY VALIDATION PASSED")
    print(f"  Available wells: {available_wells_count}")
    print(f"  Sentinels: {sentinel_count}")
    print(f"  Experimental: {experimental_count}")
    print(f"  Total: {sentinel_count + experimental_count} (exact fit)")
    print()

    # Split compounds into 2 groups (5 each)
    compound_group_1 = compounds[:5]
    compound_group_2 = compounds[5:]

    # Build experimental condition keys (canonical set for each group)
    ic50_map = get_phase0_compound_ic50()

    def build_condition_keys(compound_list):
        """Build canonical experimental conditions"""
        conditions = []
        for compound in compound_list:
            ic50 = ic50_map.get(compound, 1.0)
            for dose_mult in dose_multipliers:
                dose_uM = dose_mult * ic50
                for rep in range(replicates_per_dose):
                    conditions.append({
                        'compound': compound,
                        'dose_uM': dose_uM,
                        'replicate': rep,
                    })
        return conditions

    conditions_group_1 = build_condition_keys(compound_group_1)
    conditions_group_2 = build_condition_keys(compound_group_2)

    print(f"Experimental conditions:")
    print(f"  Group 1 ({', '.join(compound_group_1)}): {len(conditions_group_1)} conditions")
    print(f"  Group 2 ({', '.join(compound_group_2)}): {len(conditions_group_2)} conditions")
    print()

    # Generate wells with BATCH-FIRST allocation
    wells = []
    well_counter = 0
    plate_counter = 1

    for cell_line in cell_lines:
        # Determine compound group for this cell line
        # A549 gets group 1, HepG2 gets group 2 (arbitrary but deterministic)
        conditions = conditions_group_1 if cell_line == 'A549' else conditions_group_2

        # CRITICAL: Shuffle experimental positions ONCE per cell line
        # This ensures position stability: same position = same condition across all plates for this cell line
        # But eliminates spatial confounding: compounds are scattered, not clustered
        cell_line_exp_positions = [pos for pos in available_well_positions
                                   if pos not in {s['position'] for s in get_sentinel_tokens()}]
        cell_line_rng = make_rng(design_seed, f"exp_positions|{cell_line}")
        cell_line_rng.shuffle(cell_line_exp_positions)

        for day in days:
            for operator in operators:
                for timepoint in timepoints_h:
                    plate_id = f"Plate_{plate_counter}"
                    plate_counter += 1

                    # Get sentinel tokens from FIXED scaffold (with positions pre-assigned)
                    sentinel_tokens = get_sentinel_tokens()
                    sentinel_positions = {s['position'] for s in sentinel_tokens}

                    # HARD CHECK: sentinel count must match schema
                    if len(sentinel_tokens) != sentinel_count:
                        raise AssertionError(
                            f"Sentinel scaffold mismatch on {plate_id}: "
                            f"scaffold has {len(sentinel_tokens)}, expected {sentinel_count}"
                        )

                    # Build experimental tokens (IDENTICAL for this timepoint)
                    experimental_tokens = []
                    for cond in conditions:
                        experimental_tokens.append({
                            'compound': cond['compound'],
                            'dose_uM': cond['dose_uM'],
                            'is_sentinel': False,
                            'sentinel_type': None,
                        })

                    # Use pre-shuffled positions for this cell line
                    # (shuffled once per cell line to ensure position stability across plates)
                    experimental_positions = cell_line_exp_positions

                    # HARD CHECK: experimental count must match available positions
                    if len(experimental_tokens) != len(experimental_positions):
                        raise AssertionError(
                            f"Experimental position mismatch on {plate_id}: "
                            f"need {len(experimental_tokens)} positions, have {len(experimental_positions)}"
                        )

                    # HARD CHECK: total wells must equal available
                    total_wells = len(sentinel_tokens) + len(experimental_tokens)
                    if total_wells != available_wells_count:
                        raise AssertionError(
                            f"Total well count mismatch on {plate_id}: "
                            f"generated {total_wells}, expected {available_wells_count}"
                        )

                    # Place sentinels at fixed positions
                    for sentinel_token in sentinel_tokens:
                        wells.append({
                            'well_id': f"{plate_id}_W{well_counter:03d}",
                            'plate_id': plate_id,
                            'well_pos': sentinel_token['position'],
                            'row': sentinel_token['position'][0],
                            'col': int(sentinel_token['position'][1:]),
                            'cell_line': cell_line,
                            'compound': sentinel_token['compound'],
                            'dose_uM': sentinel_token['dose_uM'],
                            'is_sentinel': True,
                            'sentinel_type': sentinel_token['sentinel_type'],
                            'day': day,
                            'operator': operator,
                            'timepoint_h': timepoint,
                        })
                        well_counter += 1

                    # Place experimental wells in remaining positions
                    for exp_token, exp_pos in zip(experimental_tokens, experimental_positions):
                        wells.append({
                            'well_id': f"{plate_id}_W{well_counter:03d}",
                            'plate_id': plate_id,
                            'well_pos': exp_pos,
                            'row': exp_pos[0],
                            'col': int(exp_pos[1:]),
                            'cell_line': cell_line,
                            'compound': exp_token['compound'],
                            'dose_uM': exp_token['dose_uM'],
                            'is_sentinel': False,
                            'sentinel_type': None,
                            'day': day,
                            'operator': operator,
                            'timepoint_h': timepoint,
                        })
                        well_counter += 1

    # Create design object
    design = {
        'design_id': 'phase0_founder_v2_controls_stratified',
        'design_type': 'phase0_v2_founder',
        'description': 'Phase 0 V2 Founder Design (Audit-Compliant)',
        'metadata': {
            'generated_at_utc': datetime.utcnow().isoformat() + 'Z',
            'generator': 'design_generator_phase0.py',
            'generator_version': '1.0.0_audit_driven',
            'design_seed': design_seed,
            'cell_lines': cell_lines,
            'operators': operators,
            'days': days,
            'timepoints_h': timepoints_h,
            'n_plates': len(cell_lines) * len(days) * len(operators) * len(timepoints_h),
            'wells_per_plate': available_wells_count,
            'unused_wells_per_plate': sorted(excluded_wells),
            'sentinel_schema': {
                'policy': 'fixed_scaffold',
                'total_per_plate': sentinel_count,
                'types': {k: v['n'] for k, v in PHASE0_SENTINEL_SCHEMA.items()},
                'note': 'FIXED positions and types on ALL plates (same 28 positions, all timepoints/days/operators/cell lines)',
                'scaffold_source': 'phase0_sentinel_scaffold.py',
                'scaffold_metadata': get_scaffold_metadata(),
            },
            'experimental_conditions': {
                'total_per_plate': experimental_count,
                'compounds_per_plate': 5,
                'doses': dose_multipliers,
                'replicates': replicates_per_dose,
            },
            'capacity_validation': {
                'required': sentinel_count + experimental_count,
                'available': available_wells_count,
                'fit': 'exact',
            },
            'batch_structure': {
                'orthogonal_factors': ['day', 'operator', 'timepoint'],
                'separate_factors': ['cell_line'],
                'note': 'Batch-first allocation with fixed sentinel scaffolding and randomized experimental positions',
                'allocation': 'Identical experimental conditions per timepoint (batch orthogonality)',
                'placement': 'Sentinels at fixed positions (same 28 positions on all plates), experimentals randomly shuffled per cell line (eliminates spatial confounding while preserving position stability)',
                'randomization': f'Per-cell-line position shuffle with deterministic RNG (seed={design_seed}): same position = same condition across all plates for that cell line, but compounds scattered spatially',
            },
        },
        'wells': wells,
    }

    # Save to file
    output_path = 'data/designs/phase0_founder_v2_regenerated.json'
    with open(output_path, 'w') as f:
        json.dump(design, f, indent=2)

    print(f"✅ Design generated successfully")
    print(f"  Total wells: {len(wells)}")
    print(f"  Plates: {plate_counter - 1}")
    print(f"  Output: {output_path}")

    return design


if __name__ == '__main__':
    generate_phase0_v2_founder()
