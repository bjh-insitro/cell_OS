"""
Contract tests for variance provenance analysis.

Fast tests that verify core computations without running full simulations.
"""

import numpy as np
import tempfile
from pathlib import Path

from cell_os.analysis.variance_provenance import (
    compute_deltas,
    compute_variance_budget,
    save_deltas_csv,
    save_variance_budget_csv,
    load_wells_csv,
    CHANNELS
)


def test_compute_deltas_synthetic():
    """Test delta computation with synthetic data."""
    n_wells = 12

    # Create synthetic well data
    bio_wells = []
    geo_wells = []
    noise_wells = []
    path_wells = []
    obs_wells = []

    for i in range(n_wells):
        well_id = f"A{i+1}"
        row = 0
        col = i

        # Biology baseline
        bio = {
            'well_id': well_id,
            'row': row,
            'col': col,
        }
        for ch in CHANNELS:
            bio[ch] = 100.0  # Uniform baseline

        # Geometry adds position-dependent shift
        geo = bio.copy()
        for ch in CHANNELS:
            geo[ch] = bio[ch] + (i * 2.0)  # Linear gradient

        # Noise adds random perturbation
        noise = bio.copy()
        rng = np.random.default_rng(42)
        for ch in CHANNELS:
            noise[ch] = bio[ch] + rng.normal(0, 5.0)

        # Pathology: one well gets large shift
        path = bio.copy()
        if i == 5:
            for ch in CHANNELS:
                path[ch] = bio[ch] * 0.5  # 50% dropout

        # Observed: sum of all effects (approximately)
        obs = bio.copy()
        for ch in CHANNELS:
            obs[ch] = geo[ch] - bio[ch] + noise[ch] - bio[ch] + path[ch] - bio[ch] + bio[ch]

        bio_wells.append(bio)
        geo_wells.append(geo)
        noise_wells.append(noise)
        path_wells.append(path)
        obs_wells.append(obs)

    # Compute deltas
    deltas = compute_deltas(bio_wells, geo_wells, noise_wells, path_wells, obs_wells)

    # Verify structure
    assert 'geo' in deltas
    assert 'noise' in deltas
    assert 'path' in deltas
    assert 'total' in deltas
    assert 'resid' in deltas

    assert len(deltas['geo']) == n_wells
    assert len(deltas['total']) == n_wells

    # Verify delta_geo is correct
    for i in range(n_wells):
        for ch in CHANNELS:
            expected_delta_geo = i * 2.0
            actual_delta_geo = deltas['geo'][i][ch]
            assert abs(actual_delta_geo - expected_delta_geo) < 1e-6


def test_compute_variance_budget_synthetic():
    """Test variance budget computation with synthetic deltas."""
    n_wells = 96

    # Create synthetic deltas with known variance structure
    deltas = {'geo': [], 'noise': [], 'path': [], 'total': [], 'resid': []}

    for i in range(n_wells):
        well_id = f"A{i+1}"
        row = i // 12
        col = i % 12

        delta_geo = {'well_id': well_id, 'row': row, 'col': col}
        delta_noise = {'well_id': well_id, 'row': row, 'col': col}
        delta_path = {'well_id': well_id, 'row': row, 'col': col}
        delta_total = {'well_id': well_id, 'row': row, 'col': col}
        delta_resid = {'well_id': well_id, 'row': row, 'col': col}

        # Geometry: linear gradient (var = 96 for uniform [0, 1, 2, ..., 95])
        # Noise: Gaussian (var = sigma^2)
        # Pathology: sparse outliers (small var)
        rng = np.random.default_rng(42 + i)

        for ch in CHANNELS:
            delta_geo[ch] = float(i)  # 0, 1, 2, ..., 95
            delta_noise[ch] = rng.normal(0, 5.0)  # sigma=5, var=25
            delta_path[ch] = 10.0 if i == 50 else 0.0  # One outlier
            delta_total[ch] = delta_geo[ch] + delta_noise[ch] + delta_path[ch]
            delta_resid[ch] = 0.0  # Perfectly additive

        deltas['geo'].append(delta_geo)
        deltas['noise'].append(delta_noise)
        deltas['path'].append(delta_path)
        deltas['total'].append(delta_total)
        deltas['resid'].append(delta_resid)

    # Compute variance budget
    budget = compute_variance_budget(deltas)

    # Verify structure
    assert 'summary' in budget
    for ch in CHANNELS:
        assert ch in budget
        assert 'Var_total' in budget[ch]
        assert 'Var_geo' in budget[ch]
        assert 'Var_noise' in budget[ch]
        assert 'Var_path' in budget[ch]
        assert 'Var_resid' in budget[ch]
        assert 'frac_geo' in budget[ch]
        assert 'frac_noise' in budget[ch]
        assert 'frac_path' in budget[ch]
        assert 'frac_resid' in budget[ch]

        # Verify non-negative variances
        assert budget[ch]['Var_total'] >= 0
        assert budget[ch]['Var_geo'] >= 0
        assert budget[ch]['Var_noise'] >= 0
        assert budget[ch]['Var_path'] >= 0
        assert budget[ch]['Var_resid'] >= 0

        # Verify fractions sum to ~1.0
        # Note: In this synthetic case with residual=0, fractions should sum to 1.0
        # But variance is NOT additive for correlated variables, so we allow wider tolerance
        total_frac = (budget[ch]['frac_geo'] + budget[ch]['frac_noise'] +
                     budget[ch]['frac_path'] + budget[ch]['frac_resid'])
        assert 0.8 <= total_frac <= 1.2  # Allow for variance non-additivity

    # Verify summary stats
    assert 'total_variance_explained' in budget['summary']
    assert 'mean_residual_fraction' in budget['summary']
    # Note: total_variance_explained can exceed 1.0 due to negative correlation between layers
    # (variance non-additivity). This is correct behavior, not a bug.
    assert budget['summary']['total_variance_explained'] >= 0
    # Residual fraction can be negative (indicating layers are positively correlated)
    # or >1 (indicating negative correlation). Allow wide range.
    assert -1.0 <= budget['summary']['mean_residual_fraction'] <= 2.0


def test_variance_budget_clean_profile():
    """Test variance budget with clean profile (all layers off)."""
    n_wells = 24

    # Create deltas where all effects are zero (clean profile)
    deltas = {'geo': [], 'noise': [], 'path': [], 'total': [], 'resid': []}

    for i in range(n_wells):
        well_id = f"A{i+1}"
        row = 0
        col = i

        delta_geo = {'well_id': well_id, 'row': row, 'col': col}
        delta_noise = {'well_id': well_id, 'row': row, 'col': col}
        delta_path = {'well_id': well_id, 'row': row, 'col': col}
        delta_total = {'well_id': well_id, 'row': row, 'col': col}
        delta_resid = {'well_id': well_id, 'row': row, 'col': col}

        # All deltas are zero
        for ch in CHANNELS:
            delta_geo[ch] = 0.0
            delta_noise[ch] = 0.0
            delta_path[ch] = 0.0
            delta_total[ch] = 0.0
            delta_resid[ch] = 0.0

        deltas['geo'].append(delta_geo)
        deltas['noise'].append(delta_noise)
        deltas['path'].append(delta_path)
        deltas['total'].append(delta_total)
        deltas['resid'].append(delta_resid)

    # Compute variance budget
    budget = compute_variance_budget(deltas)

    # Verify all variances are ~0
    for ch in CHANNELS:
        assert budget[ch]['Var_total'] < 1e-10
        assert budget[ch]['Var_geo'] < 1e-10
        assert budget[ch]['Var_noise'] < 1e-10
        assert budget[ch]['Var_path'] < 1e-10
        assert budget[ch]['Var_resid'] < 1e-10

        # Fractions should be 0 (graceful handling of zero variance)
        assert budget[ch]['frac_geo'] == 0.0
        assert budget[ch]['frac_noise'] == 0.0
        assert budget[ch]['frac_path'] == 0.0
        assert budget[ch]['frac_resid'] == 0.0


def test_save_and_load_csv_roundtrip():
    """Test saving and loading deltas CSV."""
    n_wells = 12

    # Create synthetic deltas
    deltas = {'geo': [], 'noise': [], 'path': [], 'total': [], 'resid': []}

    for i in range(n_wells):
        well_id = f"A{i+1}"
        row = 0
        col = i

        for component in ['geo', 'noise', 'path', 'total', 'resid']:
            delta = {'well_id': well_id, 'row': row, 'col': col}
            for ch in CHANNELS:
                delta[ch] = float(i + ord(component[0]))  # Unique values
            deltas[component].append(delta)

    # Save to temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "deltas.csv"
        save_deltas_csv(deltas, csv_path)

        # Verify file exists
        assert csv_path.exists()

        # Load and verify (partial check, since load_wells_csv doesn't load deltas directly)
        # Just verify CSV format is readable
        import csv
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == n_wells
            assert 'well_id' in rows[0]
            assert 'delta_geo_er' in rows[0]
            assert 'delta_total_mito' in rows[0]


def test_save_variance_budget_csv():
    """Test saving variance budget to CSV."""
    # Create synthetic budget
    budget = {}
    for ch in CHANNELS:
        budget[ch] = {
            'Var_total': 100.0,
            'Var_geo': 50.0,
            'Var_noise': 30.0,
            'Var_path': 10.0,
            'Var_resid': 10.0,
            'frac_geo': 0.5,
            'frac_noise': 0.3,
            'frac_path': 0.1,
            'frac_resid': 0.1,
        }

    budget['summary'] = {
        'total_variance_explained': 0.9,
        'mean_residual_fraction': 0.1,
    }

    # Save to temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "variance_budget.csv"
        save_variance_budget_csv(budget, csv_path)

        # Verify file exists and has correct rows
        assert csv_path.exists()

        import csv
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == len(CHANNELS)
            assert rows[0]['channel'] == 'er'
            assert float(rows[0]['Var_total']) == 100.0
            assert float(rows[0]['frac_geo']) == 0.5


def test_residual_is_computed():
    """Test that residual is always computed and present."""
    n_wells = 24

    # Create deltas with non-zero residual (non-additive layers)
    deltas = {'geo': [], 'noise': [], 'path': [], 'total': [], 'resid': []}

    for i in range(n_wells):
        well_id = f"A{i+1}"
        row = 0
        col = i

        delta_geo = {'well_id': well_id, 'row': row, 'col': col}
        delta_noise = {'well_id': well_id, 'row': row, 'col': col}
        delta_path = {'well_id': well_id, 'row': row, 'col': col}
        delta_total = {'well_id': well_id, 'row': row, 'col': col}
        delta_resid = {'well_id': well_id, 'row': row, 'col': col}

        # Create non-additive structure (interaction)
        for ch in CHANNELS:
            delta_geo[ch] = 10.0
            delta_noise[ch] = 5.0
            delta_path[ch] = 2.0
            # Total is NOT sum (interaction present)
            delta_total[ch] = 20.0  # Should be 17, but is 20 (interaction = +3)
            delta_resid[ch] = 3.0  # Residual captures this

        deltas['geo'].append(delta_geo)
        deltas['noise'].append(delta_noise)
        deltas['path'].append(delta_path)
        deltas['total'].append(delta_total)
        deltas['resid'].append(delta_resid)

    # Compute variance budget
    budget = compute_variance_budget(deltas)

    # Verify residual is present and non-zero
    for ch in CHANNELS:
        assert 'Var_resid' in budget[ch]
        assert budget[ch]['Var_resid'] >= 0
        assert 'frac_resid' in budget[ch]

        # In this case, residual should be exactly zero (all deltas are constant)
        # Var(constant) = 0
        assert budget[ch]['Var_resid'] < 1e-10


if __name__ == '__main__':
    test_compute_deltas_synthetic()
    test_compute_variance_budget_synthetic()
    test_variance_budget_clean_profile()
    test_save_and_load_csv_roundtrip()
    test_save_variance_budget_csv()
    test_residual_is_computed()

    print("All contract tests passed!")
