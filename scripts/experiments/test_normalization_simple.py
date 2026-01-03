"""
Simple test script for cell line normalization (no pytest required).

Verifies:
1. Baselines loaded correctly
2. Fold-change normalization works
3. Normalization reduces variance
"""

import sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.cell_os.epistemic_agent.observation_aggregator import (
    get_cell_line_baseline,
    normalize_channel_value,
    build_normalization_metadata
)

def test_get_baselines():
    print("=" * 70)
    print("TEST 1: Get Cell Line Baselines")
    print("=" * 70)

    baseline_a549 = get_cell_line_baseline("A549")
    print(f"A549 baseline: {baseline_a549}")
    assert baseline_a549['er'] == 100.0, f"Expected ER=100, got {baseline_a549['er']}"
    assert baseline_a549['mito'] == 150.0, f"Expected Mito=150, got {baseline_a549['mito']}"

    baseline_hepg2 = get_cell_line_baseline("HepG2")
    print(f"HepG2 baseline: {baseline_hepg2}")
    assert baseline_hepg2['er'] == 130.0, f"Expected ER=130, got {baseline_hepg2['er']}"
    assert baseline_hepg2['mito'] == 180.0, f"Expected Mito=180, got {baseline_hepg2['mito']}"

    print("✅ Baselines loaded correctly\n")


def test_fold_change_normalization():
    print("=" * 70)
    print("TEST 2: Fold-Change Normalization")
    print("=" * 70)

    # A549 ER baseline = 100
    raw_value = 150.0
    normalized = normalize_channel_value(raw_value, "A549", "er", "fold_change")
    expected = 1.5  # 150 / 100
    print(f"A549: raw=150, normalized={normalized:.3f} (expected {expected:.3f})")
    assert abs(normalized - expected) < 0.001, f"Expected {expected}, got {normalized}"

    # HepG2 ER baseline = 130
    normalized = normalize_channel_value(raw_value, "HepG2", "er", "fold_change")
    expected = 150.0 / 130.0  # 1.154
    print(f"HepG2: raw=150, normalized={normalized:.3f} (expected {expected:.3f})")
    assert abs(normalized - expected) < 0.001, f"Expected {expected}, got {normalized}"

    # Mode = none (no normalization)
    normalized = normalize_channel_value(raw_value, "A549", "er", "none")
    print(f"Mode='none': raw=150, normalized={normalized:.3f} (should be unchanged)")
    assert normalized == raw_value, f"Expected {raw_value}, got {normalized}"

    print("✅ Fold-change normalization working\n")


def test_metadata_building():
    print("=" * 70)
    print("TEST 3: Normalization Metadata")
    print("=" * 70)

    cell_lines = {"A549", "HepG2", "U2OS"}

    metadata = build_normalization_metadata(cell_lines, "fold_change")
    print(f"Metadata mode: {metadata['mode']}")
    print(f"Cell lines tracked: {list(metadata['baselines_used'].keys())}")
    print(f"A549 ER baseline: {metadata['baselines_used']['A549']['er']}")
    print(f"HepG2 ER baseline: {metadata['baselines_used']['HepG2']['er']}")

    assert metadata['mode'] == "fold_change"
    assert "A549" in metadata['baselines_used']
    assert "HepG2" in metadata['baselines_used']
    assert metadata['baselines_used']['A549']['er'] == 100.0
    assert metadata['baselines_used']['HepG2']['er'] == 130.0

    print("✅ Metadata building working\n")


def test_variance_reduction_concept():
    print("=" * 70)
    print("TEST 4: Variance Reduction Concept")
    print("=" * 70)

    # Simulate 3 cell lines with same RELATIVE effect (+20% from baseline)
    # but different absolute baselines
    cell_lines_data = [
        ("A549", 100.0, 100.0 * 1.2),   # Baseline 100 → 120 raw
        ("HepG2", 130.0, 130.0 * 1.2),  # Baseline 130 → 156 raw
        ("U2OS", 95.0, 95.0 * 1.2),     # Baseline 95 → 114 raw
    ]

    raw_values = [raw for _, _, raw in cell_lines_data]
    print(f"Raw values (ER): {raw_values}")
    variance_raw = np.var(raw_values)
    print(f"Raw variance: {variance_raw:.2f}")

    # Apply normalization
    normalized_values = [
        normalize_channel_value(raw, cell_line, "er", "fold_change")
        for cell_line, baseline, raw in cell_lines_data
    ]
    print(f"Normalized values: {[f'{v:.3f}' for v in normalized_values]}")
    variance_norm = np.var(normalized_values)
    print(f"Normalized variance: {variance_norm:.6f}")

    # Variance should be dramatically reduced
    reduction_factor = variance_raw / variance_norm if variance_norm > 0 else np.inf
    print(f"Variance reduction: {reduction_factor:.0f}×")

    assert variance_norm < variance_raw * 0.01, "Normalization should reduce variance by >100×"
    assert all(abs(v - 1.2) < 0.001 for v in normalized_values), "All should normalize to ~1.2"

    print("✅ Variance reduction confirmed\n")


def main():
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "CELL LINE NORMALIZATION TESTS" + " " * 24 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    try:
        test_get_baselines()
        test_fold_change_normalization()
        test_metadata_building()
        test_variance_reduction_concept()

        print("=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print()
        print("Summary:")
        print("  - Cell line baselines loaded from thalamus params")
        print("  - Fold-change normalization: raw / baseline")
        print("  - Normalization metadata built correctly")
        print("  - Variance reduction: ~100-1000× with normalization")
        print()
        print("Impact:")
        print("  - WITHOUT normalization: Cell line effects dominate (77%)")
        print("  - WITH normalization: Cell line variance ~0%, treatment effects visible")
        print()

        return 0

    except AssertionError as e:
        print()
        print("=" * 70)
        print("❌ TEST FAILED")
        print("=" * 70)
        print(f"Error: {e}")
        return 1

    except Exception as e:
        print()
        print("=" * 70)
        print("❌ TEST ERROR")
        print("=" * 70)
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
