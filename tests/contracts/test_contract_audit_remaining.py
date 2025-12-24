"""
Audit test: Deterministic violation extraction for systematic fixing.

Runs all assays in record mode, collects violations, dedupes, and reports.
This is the ONLY test that should use record mode - all others use strict mode.
"""

import os
import pytest
from src.cell_os.contracts import (
    get_recorded_contract_violations,
    clear_recorded_contract_violations,
)


def test_contract_audit_remaining(make_vm_and_vessel):
    """
    Run all assays in record mode and verify zero violations.

    This test runs in CELL_OS_CONTRACT_RECORD=1 mode to collect ALL violations
    without raising. It then dedupes and categorizes them for systematic fixing.

    Expected behavior:
    - ✓ No contract violations detected (after fixes)

    If violations are found:
    1. Group by assay and violation type
    2. Fix in batches using standard substitution map
    3. Re-run audit until clean
    """
    # Enable violation recording
    os.environ["CELL_OS_CONTRACT_RECORD"] = "1"
    clear_recorded_contract_violations()

    try:
        vm, vessel = make_vm_and_vessel(debug_truth_enabled=False)

        # Run all assays, ignoring crashes (we only care about contract violations)
        assays = [
            ("CellPaintingAssay", lambda: vm.cell_painting_assay.measure(
                vessel, plate_id="P1", well_position="A1", batch_id="batch1"
            )),
            ("LDHViabilityAssay", lambda: vm.atp_viability_assay.measure(
                vessel, plate_id="P1", well_position="A1", batch_id="batch1"
            )),
            ("scRNASeqAssay", lambda: vm.scrna_seq_assay.measure(
                vessel, plate_id="P1"
            )),
        ]

        for assay_name, measure_fn in assays:
            try:
                measure_fn()
            except Exception as e:
                # Ignore crashes - we're only auditing contract violations
                # Crashes are tested separately in functional tests
                pass

        # Collect and dedupe violations
        violations = get_recorded_contract_violations()
        unique_violations = sorted(set(violations))

        # Categorize violations for reporting
        if unique_violations:
            by_assay = {}
            for v in unique_violations:
                assay = v.split("]")[0].split("[")[1] if "[" in v else "unknown"
                if assay not in by_assay:
                    by_assay[assay] = []
                by_assay[assay].append(v)

            report = ["Contract violations detected:"]
            for assay, assay_violations in sorted(by_assay.items()):
                report.append(f"\n{assay}:")
                for v in assay_violations:
                    report.append(f"  {v}")

            pytest.fail("\n".join(report))

        # If we get here, audit is clean
        print("✓ No contract violations detected!")

    finally:
        # Restore default mode
        os.environ.pop("CELL_OS_CONTRACT_RECORD", None)
        clear_recorded_contract_violations()


def test_audit_categorization_examples():
    """
    Document standard violation categories and fixes.

    This is NOT a real test - it's documentation of the substitution map
    used during systematic fixing.
    """
    substitution_map = {
        # Category 1: Cross-modal coupling (Cell Painting → cell_count)
        "state.cell_count": "float(vessel.confluence * 10000)  # Confluence-based estimate",

        # Category 2: Treatment leakage (reading compound identity/dose)
        "state.compounds": "Remove - use latent stress states",
        "state.compound_meta": "Remove - use latent stress states",
        "state.compound_start_time": "Use time_since_last_perturbation_h",

        # Category 3: Ground truth leakage (death labels)
        "state.death_mode": "Remove branching logic or gate behind _debug_truth",
        "state.death_compound": "Gate behind _debug_truth",
        "state.death_confluence": "Gate behind _debug_truth",
        "state.death_unknown": "Gate behind _debug_truth",

        # Category 4: scRNA cross-modal coupling
        "state.cell_count (scRNA)": "Use state.capturable_cells proxy",
    }

    # This test always passes - it's just documentation
    assert substitution_map is not None
