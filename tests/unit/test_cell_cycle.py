"""Tests for cell cycle dynamics model."""

import pytest
import numpy as np
from cell_os.biology.cell_cycle import (
    CellCyclePhase,
    CellLineProfile,
    CELL_LINE_PROFILES,
    PhaseDistribution,
    CellCycleModel,
    DrugCycleEffect,
    DRUG_CYCLE_EFFECTS,
    simulate_drug_treatment_cycle,
    compare_cell_lines_response,
)


class TestPhaseDistribution:
    """Tests for PhaseDistribution dataclass."""

    def test_normalization(self):
        """Test that distribution normalizes to sum to 1."""
        dist = PhaseDistribution(g0=1, g1=2, s=3, g2=2, m=2)
        total = dist.g0 + dist.g1 + dist.s + dist.g2 + dist.m
        assert total == pytest.approx(1.0)

    def test_from_profile(self):
        """Test creation from cell line profile."""
        profile = CELL_LINE_PROFILES['A549']
        dist = PhaseDistribution.from_profile(profile)
        assert dist.g1 == pytest.approx(profile.g1_fraction)
        assert dist.s == pytest.approx(profile.s_fraction)

    def test_to_array_and_back(self):
        """Test array conversion round-trip."""
        dist = PhaseDistribution(g0=0.1, g1=0.4, s=0.3, g2=0.15, m=0.05)
        arr = dist.to_array()
        dist2 = PhaseDistribution.from_array(arr)
        assert dist2.g0 == pytest.approx(dist.g0)
        assert dist2.m == pytest.approx(dist.m)


class TestCellLineProfiles:
    """Tests for cell line profiles."""

    def test_all_profiles_exist(self):
        """Test that expected profiles exist."""
        expected = ['A549', 'HepG2', 'iPSC_NGN2', 'iPSC_Microglia', 'HeLa']
        for name in expected:
            assert name in CELL_LINE_PROFILES

    def test_fractions_sum_to_one(self):
        """Test that phase fractions sum to 1."""
        for name, profile in CELL_LINE_PROFILES.items():
            total = profile.g1_fraction + profile.s_fraction + profile.g2_fraction + profile.m_fraction
            assert total == pytest.approx(1.0), f"{name} fractions don't sum to 1"

    def test_hela_lacks_checkpoints(self):
        """Test HeLa has non-functional p53/Rb (HPV-related)."""
        hela = CELL_LINE_PROFILES['HeLa']
        assert hela.p53_functional is False
        assert hela.rb_functional is False

    def test_ipsc_ngn2_mostly_quiescent(self):
        """Test iPSC-NGN2 neurons are mostly post-mitotic."""
        ngn2 = CELL_LINE_PROFILES['iPSC_NGN2']
        assert ngn2.doubling_time_h > 100  # Very slow
        assert ngn2.quiescence_capacity > 0.9


class TestCellCycleModel:
    """Tests for CellCycleModel core functionality."""

    def test_initialization(self):
        """Test model initializes correctly."""
        model = CellCycleModel(cell_line='A549')
        assert model.profile.name == 'A549'
        assert model.time_h == 0.0
        assert sum(model.distribution.to_array()) == pytest.approx(1.0)

    def test_step_maintains_normalization(self):
        """Test that step maintains distribution normalization."""
        model = CellCycleModel()
        for _ in range(100):
            model.step(0.1)
        total = sum(model.distribution.to_array())
        assert total == pytest.approx(1.0)

    def test_simulate_returns_timeseries(self):
        """Test simulate returns proper time series."""
        model = CellCycleModel()
        result = model.simulate(duration_h=24.0, dt_h=0.5)

        assert 'time_h' in result
        assert 'G1' in result
        assert 'S' in result
        assert len(result['time_h']) == 48  # 24h / 0.5h

    def test_asynchronous_steady_state(self):
        """Test that asynchronous population reaches steady state."""
        model = CellCycleModel(cell_line='A549')
        result = model.simulate(duration_h=100.0, dt_h=1.0)

        # After 100h, should be near steady state
        # Check G1 is roughly stable in last 20h
        g1_late = result['G1'][-20:]
        assert np.std(g1_late) < 0.05  # Low variance = stable


class TestDrugEffects:
    """Tests for drug effects on cell cycle."""

    def test_paclitaxel_m_phase_arrest(self):
        """Test paclitaxel causes M phase accumulation."""
        model = CellCycleModel(cell_line='A549')
        model.add_drug('paclitaxel', 0.1)  # 100nM
        result = model.simulate(duration_h=24.0)

        # M phase should accumulate significantly
        assert model.distribution.m > 0.2  # Much higher than normal ~5%

    def test_palbociclib_g1_arrest(self):
        """Test palbociclib (CDK4/6i) causes G1 arrest."""
        model = CellCycleModel(cell_line='A549')
        model.add_drug('palbociclib', 1.0)  # 1uM
        result = model.simulate(duration_h=48.0)

        # G1 should accumulate
        assert model.distribution.g1 > 0.6

    def test_palbociclib_cytostatic(self):
        """Test palbociclib is cytostatic (low death)."""
        model = CellCycleModel(cell_line='A549')
        model.add_drug('palbociclib', 1.0)
        model.simulate(duration_h=48.0)

        # Should have minimal cell death
        assert model.total_deaths < 0.1

    def test_hydroxyurea_s_phase_arrest(self):
        """Test hydroxyurea causes S phase arrest."""
        model = CellCycleModel(cell_line='A549')
        model.add_drug('hydroxyurea', 1000.0)  # 1mM
        result = model.simulate(duration_h=24.0)

        # S phase should be elevated
        assert model.distribution.s > 0.4

    def test_drug_removal_allows_progression(self):
        """Test drug washout allows cycle to resume."""
        model = CellCycleModel(cell_line='A549')

        # Arrest with nocodazole
        model.add_drug('nocodazole', 0.5)
        model.simulate(duration_h=16.0)
        m_arrested = model.distribution.m

        # Washout
        model.remove_drug('nocodazole')
        model.simulate(duration_h=8.0)
        m_released = model.distribution.m

        assert m_released < m_arrested  # M phase decreased


class TestCheckpoints:
    """Tests for checkpoint mechanisms."""

    def test_dna_damage_activates_g1s_checkpoint(self):
        """Test DNA damage activates G1/S checkpoint in p53+ cells."""
        model = CellCycleModel(cell_line='A549')  # p53+
        model.activate_dna_damage_checkpoint(damage_level=0.5)

        assert model.checkpoints.g1s_arrested is True
        assert model.checkpoints.g1s_arrest_strength > 0.5

    def test_hela_weak_g1s_checkpoint(self):
        """Test HeLa (p53-) has weak G1/S checkpoint."""
        model = CellCycleModel(cell_line='HeLa')
        model.activate_dna_damage_checkpoint(damage_level=0.5)

        # p53-deficient: checkpoint only at high damage
        assert model.checkpoints.g1s_arrest_strength < 0.5

    def test_checkpoint_deactivation(self):
        """Test checkpoints can be deactivated."""
        model = CellCycleModel()
        model.activate_dna_damage_checkpoint(0.5)
        assert model.checkpoints.g1s_arrested is True

        model.deactivate_checkpoints()
        assert model.checkpoints.g1s_arrested is False


class TestSynchronizationProtocols:
    """Tests for cell synchronization protocols."""

    def test_serum_starvation_g0g1_accumulation(self):
        """Test serum starvation causes G0/G1 accumulation."""
        model = CellCycleModel(cell_line='A549')
        model.serum_starve(duration_h=48.0)

        g0g1_fraction = model.distribution.g0 + model.distribution.g1
        assert g0g1_fraction > 0.7

    def test_double_thymidine_block(self):
        """Test double thymidine block protocol runs."""
        model = CellCycleModel(cell_line='A549')
        result = model.double_thymidine_block()

        assert result['protocol'] == 'double_thymidine'
        assert 'stages' in result
        assert len(result['stages']) == 3  # block1, release1, block2

    def test_nocodazole_arrest_m_phase(self):
        """Test nocodazole arrest accumulates M phase."""
        model = CellCycleModel(cell_line='HeLa')  # Fast growing
        baseline_m = model.distribution.m
        result = model.nocodazole_arrest(dose_uM=0.5, duration_h=16.0)

        # M phase should be significantly elevated from baseline (~5%)
        assert model.distribution.m > baseline_m * 2  # At least 2x baseline
        assert model.distribution.m > 0.1  # Absolute threshold


class TestObservableMarkers:
    """Tests for observable marker calculations."""

    def test_dna_content_sums_to_one(self):
        """Test DNA content fractions sum to 1."""
        model = CellCycleModel()
        dna = model.get_dna_content_distribution()
        total = dna['2N'] + dna['2N_4N'] + dna['4N']
        assert total == pytest.approx(1.0)

    def test_mitotic_index_equals_m_fraction(self):
        """Test mitotic index equals M phase fraction."""
        model = CellCycleModel()
        model.distribution.m = 0.15
        assert model.get_mitotic_index() == pytest.approx(0.15)

    def test_ki67_excludes_g0(self):
        """Test Ki-67 positive excludes G0 cells."""
        model = CellCycleModel()
        model.distribution.g0 = 0.3
        ki67 = model.get_ki67_positive()
        assert ki67 == pytest.approx(0.7)

    def test_flow_cytometry_histogram(self):
        """Test flow cytometry histogram generation."""
        model = CellCycleModel()
        result = model.get_flow_cytometry_histogram(n_cells=1000)

        assert 'dna_content' in result
        assert 'histogram' in result
        assert len(result['dna_content']) > 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_simulate_drug_treatment(self):
        """Test simulate_drug_treatment_cycle function."""
        result = simulate_drug_treatment_cycle(
            cell_line='A549',
            drug_name='paclitaxel',
            dose_uM=0.1,
            duration_h=24.0
        )

        assert result['cell_line'] == 'A549'
        assert result['drug'] == 'paclitaxel'
        assert 'treatment' in result
        assert 'final_distribution' in result

    def test_compare_cell_lines(self):
        """Test compare_cell_lines_response function."""
        result = compare_cell_lines_response(
            drug_name='palbociclib',
            dose_uM=1.0,
            duration_h=24.0,
            cell_lines=['A549', 'HeLa']
        )

        assert 'A549' in result
        assert 'HeLa' in result
