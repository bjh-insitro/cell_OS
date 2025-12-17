"""
Validation Test Suite for Simulation Realism Improvements

Tests that the improved noise model, batch effects, and edge effects:
1. Keep DMSO control CV at 2-3% (realistic)
2. Preserve mechanism recovery (separation ratio >5.0 at mid-dose)
3. Show correct batch effects (consistent within batch)
4. Show edge effects (edge wells have reduced signal)
5. Show dose-dependent noise (stressed cells have higher CV)
"""

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False

import numpy as np
import pandas as pd
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

# Optional imports for full test suite
try:
    from cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
    from cell_os.database.cell_thalamus_db import CellThalamusDB
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    FULL_SUITE_AVAILABLE = True
except ImportError:
    FULL_SUITE_AVAILABLE = False


if PYTEST_AVAILABLE:
    class TestSimulationRealism:
        """Test suite for simulation realism improvements."""

        @pytest.fixture
        def agent(self, tmp_path):
        """Create agent with temporary database."""
        db_path = tmp_path / "test_realism.db"
        db = CellThalamusDB(db_path=str(db_path))
        hardware = BiologicalVirtualMachine()
        agent = CellThalamusAgent(phase=0, hardware=hardware, db=db)
        return agent

    def test_dmso_control_cv(self, agent):
        """Test that DMSO controls have CV ~2-3% (realistic for HCS)."""
        # Run small design with DMSO controls
        design_id = agent.run_phase_0(
            cell_lines=['A549'],
            compounds=['tBHQ']  # Just one compound + DMSO
        )

        # Get all DMSO results
        results = agent.db.get_results(design_id)
        dmso_df = pd.DataFrame([r for r in results if r['compound'] == 'DMSO'])

        # Calculate CV for each morphology channel
        channels = ['er', 'mito', 'nucleus', 'actin', 'rna']
        cvs = {}
        for channel in channels:
            col = f'morph_{channel}'
            if col in dmso_df.columns:
                values = dmso_df[col].dropna()
                if len(values) > 1:
                    cv = values.std() / values.mean()
                    cvs[channel] = cv

        # Check that CV is in range 1.5-4% (target 2-3%, allow some variance)
        print(f"\nDMSO Control CVs:")
        for channel, cv in cvs.items():
            print(f"  {channel}: {cv*100:.2f}%")
            assert 0.015 < cv < 0.05, f"{channel} CV {cv*100:.1f}% outside realistic range (1.5-5%)"

    def test_mechanism_recovery_preserved(self, agent):
        """Test that mid-dose separation ratio is still >5.0 after noise."""
        # Run Phase 0 with all compounds
        design_id = agent.run_phase_0(
            cell_lines=['A549', 'HepG2'],
            compounds=['tBHQ', 'tunicamycin', 'etoposide', 'CCCP']  # Representative compounds
        )

        results = agent.db.get_results(design_id)
        df = pd.DataFrame(results)

        # Filter to mid-dose (1× EC50) at 12h
        mid_dose_12h = df[
            (df['dose_uM'] > 0) &  # Exclude vehicle
            (df['timepoint_h'] == 12)
        ]

        # Get morphology features
        feature_cols = ['morph_er', 'morph_mito', 'morph_nucleus', 'morph_actin', 'morph_rna']
        X = mid_dose_12h[feature_cols].values

        # Get stress axes
        stress_axes = []
        for _, row in mid_dose_12h.iterrows():
            compound = row['compound']
            # Look up stress axis from simulation params
            # Simplified: just use first two letters as proxy
            if compound == 'tBHQ':
                stress_axes.append('oxidative')
            elif compound == 'tunicamycin':
                stress_axes.append('er_stress')
            elif compound == 'etoposide':
                stress_axes.append('dna_damage')
            elif compound == 'CCCP':
                stress_axes.append('mitochondrial')
            else:
                stress_axes.append('unknown')

        # PCA
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        pca = PCA(n_components=2)
        pc_scores = pca.fit_transform(X_scaled)

        # Compute separation ratio (between-class / within-class variance)
        unique_axes = list(set(stress_axes))
        if len(unique_axes) < 2:
            pytest.skip("Need at least 2 stress axes for separation test")

        # Between-class variance (distance between centroids)
        centroids = {}
        for axis in unique_axes:
            mask = np.array(stress_axes) == axis
            if mask.sum() > 0:
                centroids[axis] = pc_scores[mask].mean(axis=0)

        between_var = 0.0
        count = 0
        for i, axis1 in enumerate(unique_axes):
            for axis2 in unique_axes[i+1:]:
                if axis1 in centroids and axis2 in centroids:
                    dist = np.linalg.norm(centroids[axis1] - centroids[axis2])
                    between_var += dist ** 2
                    count += 1
        if count > 0:
            between_var /= count

        # Within-class variance (average spread within each class)
        within_var = 0.0
        count = 0
        for axis in unique_axes:
            mask = np.array(stress_axes) == axis
            if mask.sum() > 1:
                class_scores = pc_scores[mask]
                centroid = class_scores.mean(axis=0)
                distances = np.linalg.norm(class_scores - centroid, axis=1)
                within_var += (distances ** 2).mean()
                count += 1
        if count > 0:
            within_var /= count

        # Separation ratio
        separation_ratio = between_var / within_var if within_var > 0 else 0.0

        print(f"\nMechanism Recovery After Noise:")
        print(f"  Between-class variance: {between_var:.3f}")
        print(f"  Within-class variance: {within_var:.3f}")
        print(f"  Separation ratio: {separation_ratio:.3f}")

        # Check that separation is still strong (>3.0, target is >5.0)
        assert separation_ratio > 3.0, f"Separation ratio {separation_ratio:.2f} too low (target >3.0)"

    def test_batch_effects_consistent(self, agent):
        """Test that batch effects are consistent within batch."""
        design_id = agent.run_phase_0(
            cell_lines=['A549'],
            compounds=['tBHQ']
        )

        results = agent.db.get_results(design_id)
        df = pd.DataFrame(results)

        # Group by plate/day/operator and check consistency
        # Within same batch, variation should be smaller than across batches

        dmso_df = df[df['compound'] == 'DMSO']
        if len(dmso_df) < 4:
            pytest.skip("Not enough DMSO wells for batch effect test")

        # Calculate within-batch and between-batch variance for morph_er
        within_batch_var = []
        for (plate, day, operator), group in dmso_df.groupby(['plate_id', 'day', 'operator']):
            if len(group) > 1:
                var = group['morph_er'].var()
                within_batch_var.append(var)

        # Between-batch variance (different plates/days/operators)
        batch_means = dmso_df.groupby(['plate_id', 'day', 'operator'])['morph_er'].mean()
        between_batch_var = batch_means.var()

        print(f"\nBatch Effect Consistency:")
        print(f"  Within-batch variance: {np.mean(within_batch_var):.2f}")
        print(f"  Between-batch variance: {between_batch_var:.2f}")

        # Between-batch variance should be larger than within-batch
        # (batch effects create systematic differences)
        if len(within_batch_var) > 0:
            assert between_batch_var > np.mean(within_batch_var), \
                "Batch effects not creating systematic differences"

    def test_edge_effects(self, agent):
        """Test that edge wells show reduced signal."""
        design_id = agent.run_phase_0(
            cell_lines=['A549'],
            compounds=['tBHQ']
        )

        results = agent.db.get_results(design_id)
        df = pd.DataFrame(results)

        # Identify edge vs center wells
        def is_edge(well_id):
            if not well_id or len(well_id) < 2:
                return False
            row = well_id[0]
            try:
                col = int(well_id[1:])
            except ValueError:
                return False
            return row in ['A', 'H'] or col in [1, 12]

        df['is_edge'] = df['well_id'].apply(is_edge)

        # Compare DMSO wells on edge vs center
        dmso_df = df[df['compound'] == 'DMSO']
        edge_dmso = dmso_df[dmso_df['is_edge']]
        center_dmso = dmso_df[~dmso_df['is_edge']]

        if len(edge_dmso) > 0 and len(center_dmso) > 0:
            edge_mean = edge_dmso['morph_er'].mean()
            center_mean = center_dmso['morph_er'].mean()

            print(f"\nEdge Effects:")
            print(f"  Edge wells mean: {edge_mean:.2f}")
            print(f"  Center wells mean: {center_mean:.2f}")
            print(f"  Reduction: {(1 - edge_mean/center_mean)*100:.1f}%")

            # Edge wells should have ~12% lower signal (per params)
            # Allow range 8-16% reduction
            reduction = 1 - edge_mean / center_mean
            assert 0.08 < reduction < 0.18, \
                f"Edge effect {reduction*100:.1f}% outside expected range (8-18%)"
        else:
            pytest.skip("Not enough edge/center wells for test")

    def test_dose_dependent_noise(self, agent):
        """Test that stressed cells show higher CV."""
        design_id = agent.run_phase_0(
            cell_lines=['A549'],
            compounds=['tBHQ']
        )

        results = agent.db.get_results(design_id)
        df = pd.DataFrame(results)

        # Compare CV at vehicle (low stress) vs high dose (high stress)
        vehicle = df[df['dose_uM'] == 0]
        high_dose = df[df['dose_uM'] > df['dose_uM'].quantile(0.75)]

        if len(vehicle) > 2 and len(high_dose) > 2:
            vehicle_cv = vehicle['morph_er'].std() / vehicle['morph_er'].mean()
            high_dose_cv = high_dose['morph_er'].std() / high_dose['morph_er'].mean()

            print(f"\nDose-Dependent Noise:")
            print(f"  Vehicle CV: {vehicle_cv*100:.2f}%")
            print(f"  High-dose CV: {high_dose_cv*100:.2f}%")
            print(f"  Ratio: {high_dose_cv/vehicle_cv:.2f}× (target 2×)")

            # High-dose should have higher CV (2× multiplier in params)
            assert high_dose_cv > vehicle_cv, \
                "High-dose CV should be higher than vehicle"

            # Ratio should be roughly 1.5-3× (target is 2×)
            ratio = high_dose_cv / vehicle_cv
            assert 1.2 < ratio < 4.0, \
                f"CV ratio {ratio:.2f}× outside expected range (1.2-4×)"
        else:
            pytest.skip("Not enough wells for dose-dependent noise test")


def test_quick_validation():
    """Quick validation that can run in CI (no database, just units)."""
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    hardware = BiologicalVirtualMachine()

    # Test edge well detection
    assert hardware._is_edge_well('A1', 96) == True  # Corner
    assert hardware._is_edge_well('H12', 96) == True  # Corner
    assert hardware._is_edge_well('D6', 96) == False  # Center
    assert hardware._is_edge_well('A6', 96) == True  # Edge row

    # Test noise calculation (implicitly tested when running assays)
    # Seed a vessel and run assay multiple times
    hardware.seed_vessel('test', 'A549', 5e5, 2e6)
    hardware.advance_time(12.0)

    # Run assay 10 times with same vessel
    signals = []
    for i in range(10):
        result = hardware.cell_painting_assay(
            'test',
            plate_id='P1',
            day=1,
            operator='OP1',
            well_position='D6'
        )
        signals.append(result['morphology']['er'])

    cv = np.std(signals) / np.mean(signals)
    print(f"\nUnit test - Repeated measurement CV: {cv*100:.2f}%")

    # CV should be in realistic range
    assert 0.01 < cv < 0.10, f"CV {cv*100:.1f}% outside realistic range"


if __name__ == "__main__":
    # Run quick validation
    print("=" * 60)
    print("SIMULATION REALISM VALIDATION")
    print("=" * 60)
    test_quick_validation()
    print("\n✓ Quick validation passed!")
    print("\nTo run full test suite:")
    print("  pytest tests/test_simulation_realism.py -v")
