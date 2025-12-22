"""
Execution Integrity Checker: Detect plate map errors at aggregation boundary.

This module runs QC checks on raw well results BEFORE aggregation into
condition summaries. It detects execution/design mismatches that would
otherwise be invisible to the agent.

Design principles:
- Runs where raw wells still exist (observation_aggregator layer)
- Checks design-intent invariants (well identities, expected locations)
- Does NOT check phenotype similarity (that's agent reasoning)
- Returns violation facts with forensic evidence
- Never crosses into agent belief space (only ExecutionIntegrityState crosses)

Key checks:
1. Anchor position verification (rigid spatial transforms)
2. Replicate clustering (identity-based, not phenotype-based)
3. Dose monotonicity (ladder direction)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Iterable
import math

from ..core.observation import RawWellResult
from .exceptions import IntegrityViolation, ExecutionIntegrityState


@dataclass(frozen=True)
class AnchorSpec:
    """
    Expected anchor specification for integrity checking.

    Anchors are wells with known identity (compound, dose, cell line)
    that should appear in specific spatial positions. They enable
    detection of plate map errors like column shifts and row swaps.

    Examples:
    - DMSO controls in center wells
    - Sentinel stressors (tBHQ mild/strong)
    - Positive/negative control treatments

    Fields:
    - code: Machine-readable anchor type (e.g., "DMSO", "tBHQ_mild")
    - expected_wells: Tuple of well IDs where this anchor should appear
    - compound: Expected compound identity
    - dose_uM: Expected dose (None = any dose)
    - cell_line: Expected cell line (None = any cell line)
    - extra: Optional metadata for forensics
    """
    code: str
    expected_wells: Tuple[str, ...]
    compound: Optional[str] = None
    dose_uM: Optional[float] = None
    cell_line: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


# =============================================================================
# Well Geometry Helpers
# =============================================================================

def _parse_well(well_id: str) -> Tuple[str, int]:
    """Parse well ID into row letter and column number.

    Args:
        well_id: Well identifier like "A5", "H12"

    Returns:
        (row, col) tuple like ("A", 5)
    """
    row = well_id[0].upper()
    col = int(well_id[1:])
    return row, col


def _format_well(row: str, col: int) -> str:
    """Format row letter and column number into well ID.

    Args:
        row: Row letter ("A"-"H" for 96-well, "A"-"P" for 384-well)
        col: Column number (1-12 for 96-well, 1-24 for 384-well)

    Returns:
        Well ID string like "A5"
    """
    return f"{row}{col}"


def _shift_well(well: str, drow: int, dcol: int, max_rows: int = 16, max_cols: int = 24) -> Optional[str]:
    """Apply spatial shift to well ID.

    Args:
        well: Original well ID
        drow: Row shift (positive = down, negative = up)
        dcol: Column shift (positive = right, negative = left)
        max_rows: Maximum number of rows (16 for 384-well, 8 for 96-well)
        max_cols: Maximum number of columns (24 for 384-well, 12 for 96-well)

    Returns:
        Shifted well ID, or None if shift moves outside plate
    """
    row, col = _parse_well(well)
    row_idx = ord(row) - ord("A")
    new_row_idx = row_idx + drow
    new_col = col + dcol

    if new_row_idx < 0 or new_row_idx >= max_rows:
        return None
    if new_col < 1 or new_col > max_cols:
        return None

    return _format_well(chr(ord("A") + new_row_idx), new_col)


def _infer_rigid_shift(expected: Iterable[str], observed: Iterable[str]) -> Optional[Dict[str, Any]]:
    """
    Infer rigid spatial shift (column/row offset) from expected vs observed wells.

    This detects systematic plate map errors like:
    - Column shift: All columns offset by N (e.g., +1 column shift)
    - Row swap: Two rows systematically swapped
    - Block shift: Entire region displaced

    Args:
        expected: List of expected well IDs
        observed: List of observed well IDs

    Returns:
        Dict with shift hypothesis if detected, else None:
        {
            "drow": int,  # Row shift amount
            "dcol": int,  # Column shift amount
            "hits": int,  # How many expected wells match shifted positions
            "n": int,  # Total expected wells
            "frac": float  # Fraction matching (0-1)
        }
    """
    exp = list(expected)
    obs = list(observed)

    if not exp or not obs:
        return None

    # Helper functions for row/column indices
    def r_i(w): return ord(_parse_well(w)[0]) - ord("A")
    def c_i(w): return _parse_well(w)[1]

    # Compute candidate shifts from pairings
    candidates: Dict[Tuple[int, int], int] = {}
    for e in exp:
        for o in obs:
            dr = r_i(o) - r_i(e)
            dc = c_i(o) - c_i(e)
            candidates[(dr, dc)] = candidates.get((dr, dc), 0) + 1

    if not candidates:
        return None

    # Pick the most common shift
    (dr, dc), support = max(candidates.items(), key=lambda kv: kv[1])

    # Validate: apply shift to all expected, see how many land in observed
    shifted = [_shift_well(w, dr, dc) for w in exp]
    shifted_valid = [w for w in shifted if w is not None]
    obs_set = set(obs)
    hits = sum(1 for w in shifted_valid if w in obs_set)

    # Require strong consistency (70%+ match), but allow some missing anchors
    if len(shifted_valid) == 0:
        return None

    frac = hits / len(shifted_valid)
    if frac >= 0.7 and support >= 2:
        return {"drow": dr, "dcol": dc, "hits": hits, "n": len(shifted_valid), "frac": frac}

    return None


# =============================================================================
# Anchor Matching
# =============================================================================

def _matches_anchor(well: RawWellResult, spec: AnchorSpec, dose_tolerance: float = 1e-9) -> bool:
    """Check if a raw well result matches an anchor specification.

    Args:
        well: Raw well result to check
        spec: Anchor specification with identity constraints
        dose_tolerance: Tolerance for floating-point dose comparison

    Returns:
        True if well matches anchor identity constraints
    """
    if spec.compound is not None and well.treatment.compound != spec.compound:
        return False

    if spec.dose_uM is not None:
        if abs(well.treatment.dose_uM - spec.dose_uM) > dose_tolerance:
            return False

    if spec.cell_line is not None and well.cell_line != spec.cell_line:
        return False

    return True


# =============================================================================
# Anchor Position Checker
# =============================================================================

def check_anchor_positions(
    raw_wells: List[RawWellResult],
    expected_anchors: Dict[str, AnchorSpec]
) -> List[IntegrityViolation]:
    """
    Check that anchor identities appear in expected spatial positions.

    This is a DESIGN-INTENT check, not a phenotype check. It verifies:
    - DMSO controls are in center wells (not edge)
    - Sentinel stressors are in expected positions
    - Known compounds haven't been swapped or spatially shifted

    Detects:
    - Column shifts (all columns offset by N)
    - Row swaps (two rows systematically swapped)
    - Reagent swaps (compound identities in wrong wells)
    - Missing anchors (execution incomplete)

    Args:
        raw_wells: List of raw well results from execution
        expected_anchors: Dict of anchor specs keyed by anchor code

    Returns:
        List of IntegrityViolation objects (empty if all anchors OK)

    Evidence payload includes:
    - missing_wells: Expected but not observed
    - unexpected_wells: Observed in wrong positions
    - shift_hypothesis: Inferred rigid transform (if detected)
    """
    violations: List[IntegrityViolation] = []

    # Index wells by well_id for lookup
    by_well: Dict[str, RawWellResult] = {w.location.well_id: w for w in raw_wells}

    # Find observed wells for each anchor type
    observed_by_anchor: Dict[str, List[str]] = {k: [] for k in expected_anchors.keys()}
    observed_elsewhere: Dict[str, List[Dict[str, Any]]] = {k: [] for k in expected_anchors.keys()}

    for anchor_code, spec in expected_anchors.items():
        for well in raw_wells:
            if _matches_anchor(well, spec):
                well_id = well.location.well_id
                observed_by_anchor[anchor_code].append(well_id)

                if well_id not in spec.expected_wells:
                    observed_elsewhere[anchor_code].append({
                        "well_id": well_id,
                        "compound": well.treatment.compound,
                        "dose_uM": well.treatment.dose_uM,
                        "cell_line": well.cell_line,
                    })

    # Evaluate each anchor type
    for anchor_code, spec in expected_anchors.items():
        expected_set = set(spec.expected_wells)
        observed = observed_by_anchor.get(anchor_code, [])
        observed_set = set(observed)

        missing = sorted(list(expected_set - observed_set))
        extras = sorted(list(observed_set - expected_set))

        if missing or extras:
            # Try to infer rigid spatial shift
            shift_hyp = None
            if extras and spec.expected_wells:
                shift_hyp = _infer_rigid_shift(spec.expected_wells, observed)

            # Determine severity
            severity = "halt"  # Position mismatches are serious

            # Build summary message
            summary_parts = []
            if missing:
                summary_parts.append(f"missing={len(missing)}")
            if extras:
                summary_parts.append(f"misplaced={len(extras)}")
            summary = f"Anchor '{anchor_code}' mismatch ({', '.join(summary_parts)})"

            # Create violation with forensic evidence
            violations.append(IntegrityViolation(
                code="anchor_position_mismatch",
                severity=severity,
                summary=summary,
                evidence={
                    "anchor_code": anchor_code,
                    "expected_wells": list(spec.expected_wells),
                    "observed_wells": observed,
                    "missing_wells": missing,
                    "unexpected_wells": extras,
                    "misplaced_records": observed_elsewhere.get(anchor_code, []),
                    "shift_hypothesis": shift_hyp,  # May be None
                    "spec": {
                        "compound": spec.compound,
                        "dose_uM": spec.dose_uM,
                        "cell_line": spec.cell_line,
                        "extra": spec.extra or {},
                    }
                },
                supporting_conditions=[]  # No condition-level support (this is well-level)
            ))

    return violations


# =============================================================================
# Main Entry Point
# =============================================================================

def check_execution_integrity(
    raw_wells: List[RawWellResult],
    expected_anchors: Dict[str, AnchorSpec],
    cycle: int
) -> ExecutionIntegrityState:
    """
    Run all execution integrity checks and return aggregate state.

    This is the main entry point called from observation_aggregator.py.
    It runs all QC checks and produces an ExecutionIntegrityState that
    crosses the aggregation boundary into agent beliefs.

    Args:
        raw_wells: Raw well results from execution
        expected_anchors: Anchor specifications for this design
        cycle: Current cycle number (for hysteresis tracking)

    Returns:
        ExecutionIntegrityState with violations, severity, and recommended action
    """
    violations: List[IntegrityViolation] = []

    # Run anchor position checks
    violations.extend(check_anchor_positions(raw_wells, expected_anchors))

    # TODO: Add more checks
    # violations.extend(check_replicate_clustering(raw_wells))
    # violations.extend(check_dose_monotonicity(raw_wells))

    # Compute aggregate severity
    severity, recommended_action = _compute_integrity_severity(violations)

    return ExecutionIntegrityState(
        suspect=(len(violations) > 0),
        severity=severity,
        recommended_action=recommended_action,
        violations=violations,
        last_check_cycle=cycle,
        consecutive_bad_checks=0,  # Hysteresis managed by BeliefState
        consecutive_good_checks=0,
    )


def _compute_integrity_severity(
    violations: List[IntegrityViolation]
) -> Tuple[str, str]:
    """
    Compute aggregate severity and recommended action from violations.

    This is a simple version - BeliefState will apply hysteresis.

    Args:
        violations: List of detected violations

    Returns:
        (severity, recommended_action) tuple
    """
    if not violations:
        return ("none", "continue")

    # Check for fatal-level violations
    fatal_violations = [v for v in violations if v.severity == "fatal"]
    if fatal_violations:
        return ("fatal", "hard_halt")

    # Multiple violations = halt
    if len(violations) >= 2:
        return ("halt", "diagnose")

    # Single violation = warning (hysteresis in BeliefState)
    return ("warning", "cautious")
