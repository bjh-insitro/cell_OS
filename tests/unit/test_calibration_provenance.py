"""
Unit tests for CalibrationProvenance (Issue #1).

Tests that calibration provenance:
1. Tracks position distribution (edge vs center wells)
2. Accumulates correctly across multiple calibration updates
3. Serializes/deserializes correctly
4. Computes center_fraction and edge_fraction correctly
"""

import pytest
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from cell_os.epistemic_agent.beliefs.state import BeliefState, CalibrationProvenance


class TestCalibrationProvenanceDataclass:
    """Test CalibrationProvenance dataclass behavior."""

    def test_default_initialization(self):
        """Default provenance starts empty."""
        prov = CalibrationProvenance()

        assert prov.position_counts == {}
        assert prov.plate_ids == set()
        assert prov.channel_baselines == {}
        assert prov.total_wells == 0
        assert prov.last_update_cycle is None

    def test_center_fraction_empty(self):
        """Center fraction is 0 when no wells."""
        prov = CalibrationProvenance()
        assert prov.center_fraction() == 0.0

    def test_edge_fraction_empty(self):
        """Edge fraction is 0 when no wells."""
        prov = CalibrationProvenance()
        assert prov.edge_fraction() == 0.0

    def test_center_fraction_all_center(self):
        """Center fraction is 1.0 when all wells are center."""
        prov = CalibrationProvenance(
            position_counts={"center": 96},
            total_wells=96,
        )
        assert prov.center_fraction() == 1.0
        assert prov.edge_fraction() == 0.0

    def test_edge_fraction_all_edge(self):
        """Edge fraction is 1.0 when all wells are edge."""
        prov = CalibrationProvenance(
            position_counts={"edge": 32},
            total_wells=32,
        )
        assert prov.edge_fraction() == 1.0
        assert prov.center_fraction() == 0.0

    def test_mixed_position_fractions(self):
        """Fractions compute correctly with mixed positions."""
        prov = CalibrationProvenance(
            position_counts={"center": 76, "edge": 20},
            total_wells=96,
        )
        assert abs(prov.center_fraction() - 76/96) < 1e-9
        assert abs(prov.edge_fraction() - 20/96) < 1e-9

    def test_to_dict_serialization(self):
        """Provenance serializes to dict correctly."""
        prov = CalibrationProvenance(
            position_counts={"center": 76, "edge": 20},
            plate_ids={"plate_001", "plate_002"},
            channel_baselines={"ER": 100.5, "Mito": 85.3},
            total_wells=96,
            last_update_cycle=3,
        )

        d = prov.to_dict()

        assert d["position_counts"] == {"center": 76, "edge": 20}
        assert d["plate_ids"] == ["plate_001", "plate_002"]  # Sorted list
        assert d["channel_baselines"] == {"ER": 100.5, "Mito": 85.3}
        assert d["total_wells"] == 96
        assert d["last_update_cycle"] == 3

    def test_from_dict_deserialization(self):
        """Provenance deserializes from dict correctly."""
        d = {
            "position_counts": {"center": 76, "edge": 20},
            "plate_ids": ["plate_001", "plate_002"],
            "channel_baselines": {"ER": 100.5, "Mito": 85.3},
            "total_wells": 96,
            "last_update_cycle": 3,
        }

        prov = CalibrationProvenance.from_dict(d)

        assert prov.position_counts == {"center": 76, "edge": 20}
        assert prov.plate_ids == {"plate_001", "plate_002"}
        assert prov.channel_baselines == {"ER": 100.5, "Mito": 85.3}
        assert prov.total_wells == 96
        assert prov.last_update_cycle == 3

    def test_roundtrip_serialization(self):
        """Provenance survives dict roundtrip."""
        prov = CalibrationProvenance(
            position_counts={"center": 50, "edge": 30, "any": 16},
            plate_ids={"cal_001", "cal_002", "cal_003"},
            channel_baselines={"ER": 100.0, "Mito": 90.0, "Nucleus": 80.0},
            total_wells=96,
            last_update_cycle=5,
        )

        prov2 = CalibrationProvenance.from_dict(prov.to_dict())

        assert prov2.position_counts == prov.position_counts
        assert prov2.plate_ids == prov.plate_ids
        assert prov2.channel_baselines == prov.channel_baselines
        assert prov2.total_wells == prov.total_wells
        assert prov2.last_update_cycle == prov.last_update_cycle


class TestBeliefStateIntegration:
    """Test CalibrationProvenance integration with BeliefState."""

    def test_belief_state_has_calibration_provenance(self):
        """BeliefState includes calibration_provenance field."""
        beliefs = BeliefState()

        assert hasattr(beliefs, 'calibration_provenance')
        assert isinstance(beliefs.calibration_provenance, CalibrationProvenance)

    def test_belief_state_default_provenance_empty(self):
        """Default BeliefState has empty provenance."""
        beliefs = BeliefState()

        assert beliefs.calibration_provenance.total_wells == 0
        assert beliefs.calibration_provenance.position_counts == {}

    def test_belief_state_to_dict_includes_provenance(self):
        """BeliefState.to_dict() includes calibration_provenance."""
        beliefs = BeliefState()
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 48},
            total_wells=48,
            last_update_cycle=1,
        )

        d = beliefs.to_dict()

        assert "calibration_provenance" in d
        assert d["calibration_provenance"]["position_counts"] == {"center": 48}
        assert d["calibration_provenance"]["total_wells"] == 48


class TestMockConditionProvenance:
    """Test provenance accumulation with mock conditions."""

    @dataclass
    class MockCondition:
        """Mock ConditionSummary for testing."""
        compound: str = "DMSO"
        position_tag: str = "center"
        n_wells: int = 16
        mean: float = 100.0
        std: float = 10.0
        cv: float = 0.1
        feature_means: Optional[Dict[str, float]] = None
        feature_stds: Optional[Dict[str, float]] = None
        time_h: float = 48.0
        cell_line: str = "A549"
        dose_uM: float = 0.0
        assay: str = "cell_painting"

    def test_provenance_accumulates_position_counts(self):
        """Provenance accumulates position counts from conditions."""
        beliefs = BeliefState()
        beliefs.begin_cycle(1)

        # Manually simulate what NoiseBeliefUpdater._accumulate_calibration_provenance does
        cond = self.MockCondition(position_tag="center", n_wells=16)

        prov = beliefs.calibration_provenance
        new_counts = dict(prov.position_counts)
        new_counts["center"] = new_counts.get("center", 0) + cond.n_wells

        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts=new_counts,
            total_wells=prov.total_wells + cond.n_wells,
            last_update_cycle=1,
        )

        assert beliefs.calibration_provenance.position_counts == {"center": 16}
        assert beliefs.calibration_provenance.total_wells == 16
        assert beliefs.calibration_provenance.center_fraction() == 1.0

    def test_provenance_accumulates_mixed_positions(self):
        """Provenance tracks mixed center/edge wells."""
        beliefs = BeliefState()

        # Add center wells
        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts={"center": 76},
            total_wells=76,
        )

        # Add edge wells
        prov = beliefs.calibration_provenance
        new_counts = dict(prov.position_counts)
        new_counts["edge"] = new_counts.get("edge", 0) + 20

        beliefs.calibration_provenance = CalibrationProvenance(
            position_counts=new_counts,
            total_wells=prov.total_wells + 20,
        )

        assert beliefs.calibration_provenance.position_counts == {"center": 76, "edge": 20}
        assert beliefs.calibration_provenance.total_wells == 96
        assert abs(beliefs.calibration_provenance.center_fraction() - 76/96) < 1e-9
        assert abs(beliefs.calibration_provenance.edge_fraction() - 20/96) < 1e-9


class TestProvenanceInflationDefense:
    """Test that provenance cannot be inflated after cycle 0.

    This is the key defense against the provenance inflation attack:
    - Agent could run DMSO wells during biology cycles to fake coverage
    - With the cycle-0 gate, only calibration-phase DMSO earns provenance

    Regression test for: "provenance inflation via non-calibration DMSO"
    """

    @dataclass
    class MockCondition:
        """Mock ConditionSummary for testing."""
        compound: str = "DMSO"
        position_tag: str = "center"
        n_wells: int = 16
        mean: float = 100.0
        std: float = 10.0
        cv: float = 0.1
        feature_means: Optional[Dict[str, float]] = None
        feature_stds: Optional[Dict[str, float]] = None
        time_h: float = 48.0
        cell_line: str = "A549"
        dose_uM: float = 0.0
        assay: str = "cell_painting"

    def test_provenance_earned_during_cycle0(self):
        """Provenance IS earned when DMSO runs during cycle 0 (calibration)."""
        from cell_os.epistemic_agent.beliefs.updates.noise import NoiseBeliefUpdater

        beliefs = BeliefState()
        beliefs.begin_cycle(0)  # Calibration phase

        updater = NoiseBeliefUpdater(beliefs)
        cond = self.MockCondition(position_tag="center", n_wells=48)
        diagnostics = []

        updater.update([cond], diagnostics)

        # Provenance SHOULD be earned during cycle 0
        assert beliefs.calibration_provenance.total_wells == 48
        assert beliefs.calibration_provenance.position_counts.get("center", 0) == 48

    def test_provenance_not_earned_after_cycle0(self):
        """Provenance is NOT earned when DMSO runs after cycle 0 (biology phase).

        This is the key regression test: an agent cannot inflate provenance
        by running DMSO wells during biology cycles.
        """
        from cell_os.epistemic_agent.beliefs.updates.noise import NoiseBeliefUpdater

        beliefs = BeliefState()

        # Cycle 0: Run calibration, earn provenance
        beliefs.begin_cycle(0)
        updater = NoiseBeliefUpdater(beliefs)
        cal_cond = self.MockCondition(position_tag="center", n_wells=48)
        diagnostics = []
        updater.update([cal_cond], diagnostics)

        provenance_after_cal = beliefs.calibration_provenance.total_wells
        assert provenance_after_cal == 48, "Should earn provenance in cycle 0"

        # Cycle 1: Run more DMSO (should NOT earn provenance)
        beliefs.begin_cycle(1)
        bio_cond = self.MockCondition(position_tag="center", n_wells=24)
        diagnostics = []
        updater.update([bio_cond], diagnostics)

        provenance_after_bio = beliefs.calibration_provenance.total_wells
        assert provenance_after_bio == provenance_after_cal, (
            f"Provenance should NOT change after cycle 0. "
            f"Was {provenance_after_cal}, now {provenance_after_bio}"
        )

    def test_provenance_not_earned_in_late_cycles(self):
        """Provenance blocked even in late cycles (cycle 5, 10, etc)."""
        from cell_os.epistemic_agent.beliefs.updates.noise import NoiseBeliefUpdater

        beliefs = BeliefState()
        beliefs.begin_cycle(0)

        updater = NoiseBeliefUpdater(beliefs)

        # Cycle 0: calibrate
        updater.update([self.MockCondition(n_wells=48)], [])
        initial_provenance = beliefs.calibration_provenance.total_wells

        # Skip to cycle 5 and try to inflate
        for cycle in [1, 2, 5, 10]:
            beliefs.begin_cycle(cycle)
            updater.update([self.MockCondition(n_wells=48)], [])

            assert beliefs.calibration_provenance.total_wells == initial_provenance, (
                f"Provenance inflated in cycle {cycle}"
            )

    def test_noise_estimates_still_update_after_cycle0(self):
        """Noise estimates (sigma, CV) DO update after cycle 0, just not provenance.

        DMSO during biology still contributes to noise tracking for drift detection.
        Only provenance (position coverage) is locked to cycle 0.
        """
        from cell_os.epistemic_agent.beliefs.updates.noise import NoiseBeliefUpdater

        beliefs = BeliefState()
        beliefs.begin_cycle(0)

        updater = NoiseBeliefUpdater(beliefs)
        updater.update([self.MockCondition(n_wells=48)], [])

        sigma_after_cal = beliefs.noise_sigma_hat
        df_after_cal = beliefs.noise_df_total

        # Cycle 1: more DMSO
        beliefs.begin_cycle(1)
        updater.update([self.MockCondition(n_wells=24)], [])

        # Noise estimates SHOULD update (drift detection needs this)
        assert beliefs.noise_df_total > df_after_cal, "DF should increase"

        # But provenance should NOT change
        assert beliefs.calibration_provenance.total_wells == 48


class TestProvenanceAttackDetection:
    """Test that provenance enables position mismatch detection.

    These tests document the attack scenario:
    - Agent calibrates on edge-heavy wells (biased toward edge artifacts)
    - Agent then runs biology on center wells (where calibration doesn't apply)

    With provenance tracking, we can detect this mismatch.
    """

    def test_detect_edge_heavy_calibration(self):
        """Detect when calibration was edge-heavy (potential exploit)."""
        prov = CalibrationProvenance(
            position_counts={"center": 10, "edge": 86},  # 90% edge
            total_wells=96,
        )

        # If center_fraction < 0.5, calibration was edge-heavy
        assert prov.center_fraction() < 0.5
        assert prov.edge_fraction() > 0.5

        # This is suspicious: edge wells have different noise characteristics
        edge_heavy = prov.edge_fraction() > 0.7
        assert edge_heavy, "Should detect edge-heavy calibration"

    def test_detect_center_only_calibration(self):
        """Detect when calibration used only center wells."""
        prov = CalibrationProvenance(
            position_counts={"center": 96},
            total_wells=96,
        )

        # 100% center calibration
        assert prov.center_fraction() == 1.0
        assert prov.edge_fraction() == 0.0

        # If biology later uses edge wells, there's a coverage gap
        biology_uses_edge = True  # Hypothetical
        calibration_covers_edge = prov.edge_fraction() > 0.1

        coverage_gap = biology_uses_edge and not calibration_covers_edge
        assert coverage_gap, "Should detect coverage gap for edge wells"

    def test_balanced_calibration_no_alert(self):
        """Balanced calibration shouldn't trigger alerts."""
        prov = CalibrationProvenance(
            position_counts={"center": 50, "edge": 46},
            total_wells=96,
        )

        # Roughly balanced
        assert 0.4 < prov.center_fraction() < 0.6
        assert 0.4 < prov.edge_fraction() < 0.6

        # No position bias detected
        edge_heavy = prov.edge_fraction() > 0.7
        center_only = prov.edge_fraction() < 0.1

        assert not edge_heavy
        assert not center_only


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
