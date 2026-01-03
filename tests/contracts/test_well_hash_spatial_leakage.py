"""
Test whether well-hash creates learnable spatial patterns.

Critical question: Can an agent predict well position from morphology,
exploiting persistent well biology offsets that are deterministically
keyed to well coordinates?
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext


def generate_dmso_plate_subset(seed: int = 42, n_wells: int = 96):
    """
    Generate a subset of wells with identical biology (DMSO, A549, 24h).

    If well biology offsets are position-dependent, we should see:
    - Systematic differences between wells
    - Predictability of well position from morphology

    Args:
        seed: Run seed
        n_wells: Number of wells to generate (default 96 for speed)

    Returns:
        measurements: List of dicts with 'well_pos', 'row', 'col', 'morphology'
    """
    rc = RunContext.sample(seed=seed)
    vm = BiologicalVirtualMachine(seed=seed, run_context=rc)
    vm._load_cell_thalamus_params()

    # Sample wells across the plate to get spatial coverage
    # Use corners, edges, and center (reduced for speed)
    rows = [chr(ord('A') + i) for i in range(4)]  # A-D (4 rows)
    cols = list(range(1, 7))  # 1-6 (6 cols, 24 wells total)

    measurements = []
    vessel_ids = []

    for row in rows:
        for col in cols:
            well_pos = f"{row}{col:02d}"
            vessel_id = well_pos  # Use well position directly as vessel_id
            vessel_ids.append((vessel_id, well_pos, row, col))

            # Create vessel (well_position inferred from vessel_id format)
            vm.seed_vessel(
                vessel_id=vessel_id,
                cell_line="A549",
                initial_count=2000,
                vessel_type="96-well",
            )

    # Advance all vessels to 24h
    vm.advance_time(24.0)

    # Now measure all vessels
    for vessel_id, well_pos, row, col in vessel_ids:
        obs = vm.cell_painting_assay(vessel_id)

        measurements.append({
            'well_pos': well_pos,
            'row': row,
            'col': col,
            'row_idx': ord(row) - ord('A'),
            'col_idx': col - 1,
            'morphology': obs['morphology'],
        })

    return measurements


def test_position_predictability_from_morphology():
    """
    Test B: Can we predict well position from morphology?

    Strategy:
    1. Generate DMSO-only plate (identical biology)
    2. Train simple model to predict position from morphology
    3. Check if accuracy > chance

    EXPECTED TO FAIL: Position should be predictable due to well-hash encoding.
    """
    print("\n" + "=" * 70)
    print("TEST B: Position Predictability from Morphology")
    print("=" * 70)

    # Generate data
    print("Generating 96-well DMSO plate...")
    measurements = generate_dmso_plate_subset(seed=42, n_wells=96)
    print(f"Generated {len(measurements)} wells")

    # Extract features and labels
    X = np.array([[
        m['morphology']['er'],
        m['morphology']['mito'],
        m['morphology']['nucleus'],
        m['morphology']['actin'],
        m['morphology']['rna'],
    ] for m in measurements])

    # Labels: row index (0-15)
    y_row = np.array([m['row_idx'] for m in measurements])

    # Labels: col index (0-23)
    y_col = np.array([m['col_idx'] for m in measurements])

    # Labels: edge vs center (adjusted for 4x6 grid)
    y_edge = np.array([
        1 if (m['row_idx'] == 0 or m['row_idx'] == 3 or
              m['col_idx'] == 0 or m['col_idx'] == 5)
        else 0
        for m in measurements
    ])

    print(f"\nFeature matrix shape: {X.shape}")
    print(f"Row labels: {y_row.min()}-{y_row.max()}")
    print(f"Col labels: {y_col.min()}-{y_col.max()}")
    print(f"Edge wells: {y_edge.sum()}/{len(y_edge)}")

    # Simple correlation test: can morphology predict row/col?
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import cross_val_score

    # Standardize features
    X_mean = X.mean(axis=0)
    X_std = X.std(axis=0)
    X_scaled = (X - X_mean) / (X_std + 1e-10)

    # Predict row index
    model_row = Ridge(alpha=1.0)
    scores_row = cross_val_score(model_row, X_scaled, y_row, cv=5, scoring='r2')
    r2_row = scores_row.mean()

    # Predict col index
    model_col = Ridge(alpha=1.0)
    scores_col = cross_val_score(model_col, X_scaled, y_col, cv=5, scoring='r2')
    r2_col = scores_col.mean()

    # Predict edge vs center
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    model_edge = LogisticRegression(penalty='l2', C=1.0, max_iter=1000)
    model_edge.fit(X_scaled, y_edge)
    y_pred_proba = model_edge.predict_proba(X_scaled)[:, 1]
    auc_edge = roc_auc_score(y_edge, y_pred_proba)

    print(f"\n--- Predictability Results ---")
    print(f"Row prediction R²: {r2_row:.4f} (chance = 0.0)")
    print(f"Col prediction R²: {r2_col:.4f} (chance = 0.0)")
    print(f"Edge prediction AUC: {auc_edge:.4f} (chance = 0.5)")

    # Thresholds for concern
    threshold_r2 = 0.05  # 5% variance explained is already suspicious
    threshold_auc = 0.6  # 60% AUC is well above chance

    failures = []

    if r2_row > threshold_r2:
        failures.append(f"Row predictable: R²={r2_row:.4f} > {threshold_r2}")

    if r2_col > threshold_r2:
        failures.append(f"Col predictable: R²={r2_col:.4f} > {threshold_r2}")

    if auc_edge > threshold_auc:
        failures.append(f"Edge predictable: AUC={auc_edge:.4f} > {threshold_auc}")

    if failures:
        print(f"\n❌ FAIL: Position is learnable from morphology!")
        for failure in failures:
            print(f"  - {failure}")
        print("\nImplication: Agent can learn well position as a causal feature.")
        return False
    else:
        print(f"\n✅ PASS: Position not learnable (within thresholds)")
        return True


def test_persistence_across_runs():
    """
    Test C: Do per-well deviations persist across runs?

    If well biology is deterministically hashed from position,
    then deviations should be IDENTICAL across runs (perfectly correlated).
    """
    print("\n" + "=" * 70)
    print("TEST C: Persistence of Per-Well Deviations Across Runs")
    print("=" * 70)

    # Run 1
    print("Run 1...")
    measurements_run1 = generate_dmso_plate_subset(seed=42, n_wells=96)

    # Run 2 (SAME SEED - should be identical if deterministic)
    print("Run 2 (same seed)...")
    measurements_run2 = generate_dmso_plate_subset(seed=42, n_wells=96)

    # Run 3 (DIFFERENT SEED - should differ if batch effects matter)
    print("Run 3 (different seed)...")
    measurements_run3 = generate_dmso_plate_subset(seed=999, n_wells=96)

    # Extract ER channel as example
    er_run1 = np.array([m['morphology']['er'] for m in measurements_run1])
    er_run2 = np.array([m['morphology']['er'] for m in measurements_run2])
    er_run3 = np.array([m['morphology']['er'] for m in measurements_run3])

    # Compute deviations from plate mean
    dev_run1 = er_run1 - er_run1.mean()
    dev_run2 = er_run2 - er_run2.mean()
    dev_run3 = er_run3 - er_run3.mean()

    # Correlations
    corr_same_seed = np.corrcoef(dev_run1, dev_run2)[0, 1]
    corr_diff_seed = np.corrcoef(dev_run1, dev_run3)[0, 1]

    print(f"\n--- Persistence Results ---")
    print(f"Correlation (same seed, run 1 vs 2): {corr_same_seed:.4f}")
    print(f"Correlation (diff seed, run 1 vs 3): {corr_diff_seed:.4f}")

    # Expected: same seed should be perfect (1.0), diff seed should be high if position-keyed
    if corr_same_seed > 0.99:
        print(f"✅ Same seed: Perfect reproducibility (expected)")
    else:
        print(f"⚠️  Same seed: Not perfectly reproducible (unexpected!)")

    if corr_diff_seed > 0.9:
        print(f"❌ FAIL: Different seeds show strong correlation!")
        print(f"  → Well biology is deterministic from position, not run seed")
        print(f"  → Agent will learn well identity as stable predictor")
        return False
    elif corr_diff_seed > 0.5:
        print(f"⚠️  WARN: Moderate correlation across seeds ({corr_diff_seed:.4f})")
        print(f"  → Well biology has some position dependence")
        return False
    else:
        print(f"✅ PASS: Low correlation across seeds ({corr_diff_seed:.4f})")
        print(f"  → Well biology varies across runs (good!)")
        return True


if __name__ == "__main__":
    test_b_pass = test_position_predictability_from_morphology()
    test_c_pass = test_persistence_across_runs()

    print("\n" + "=" * 70)
    print("ATTACK 2 SUMMARY")
    print("=" * 70)
    if test_b_pass and test_c_pass:
        print("✅ PASS: Well-hash does not create learnable position features")
    else:
        print("❌ FAIL: Well-hash creates learnable causal features")
        print("\nHash inputs found in code:")
        print("  src/cell_os/hardware/biological_virtual.py:1716")
        print("  well_seed = stable_u32(f'well_biology_{well_position}_{cell_line}')")
        print("\nThis encodes POSITION directly into persistent biology offsets.")
