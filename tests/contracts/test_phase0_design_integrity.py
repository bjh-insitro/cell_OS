"""
Phase 0 Design Integrity Contract Test

Ensures the Phase 0 Menadione design produces a complete, internally consistent
experimental design. This catches "everything passes locally but global composition
is wrong" bugs.

This test exists because:
1. Design files (menadione_phase0_design.py), templates (plate_template_generator.py),
   and documentation can drift out of sync
2. Partial changes (e.g., updating doses in one place but not another) can silently
   produce malformed designs
3. The design is the single source of truth for the entire experiment

Contract (per docs/PHASE_0_THALAMUS_PLAN_VarP.md and Menadione_Phase0_Plate_Design_Analysis.md):
- Total plates: 18 (3 passages × 2 timepoints × 3 plates)
- Wells per plate: 382 (64 sentinels + 318 experimental)
- Total wells: 6,876
- Sentinels per plate: 64 (40 vehicle + 12 shoulder + 12 collapse)
- Sentinel doses: {0.0, 6.0, 15.0}
- Experimental wells per plate: 318 (53 reps × 6 doses)
- Doses: [0.0, 2.0, 4.0, 6.0, 8.0, 15.0]
"""

from collections import defaultdict

import pytest

from cell_os.cell_thalamus.menadione_phase0_design import (
    MenadionePhase0Design,
    create_menadione_design,
)
from cell_os.cell_thalamus.plate_template_generator import create_phase0_templates


class TestDesignGlobalComposition:
    """Verify the global composition of the generated design."""

    @pytest.fixture
    def design(self):
        """Create a fresh design instance."""
        return create_menadione_design()

    @pytest.fixture
    def all_assignments(self, design):
        """Generate all well assignments."""
        return design.generate_design()

    def test_total_plates_equals_18(self, design, all_assignments):
        """
        Design must have exactly 18 plates:
        3 passages × 2 timepoints × 3 plates = 18
        """
        unique_plates = set(w.plate_id for w in all_assignments)
        assert len(unique_plates) == 18, (
            f"Expected 18 plates (3 passages × 2 timepoints × 3 plates), "
            f"got {len(unique_plates)}. "
            f"Check passages={design.passages}, timepoints={design.timepoints_h}, "
            f"plates_per_timepoint={design.plates_per_timepoint}"
        )

    def test_total_wells_equals_6876(self, all_assignments):
        """
        Design must have exactly 6,876 wells:
        18 plates × 382 wells = 6,876
        """
        assert len(all_assignments) == 6876, (
            f"Expected 6,876 wells (18 plates × 382 wells), got {len(all_assignments)}. "
            "Check wells_per_plate calculation."
        )

    def test_each_plate_has_382_wells(self, all_assignments):
        """Each plate must have exactly 382 wells (64 sentinels + 318 experimental)."""
        wells_per_plate = defaultdict(list)
        for w in all_assignments:
            wells_per_plate[w.plate_id].append(w)

        for plate_id, wells in wells_per_plate.items():
            assert len(wells) == 382, (
                f"Plate {plate_id} has {len(wells)} wells, expected 382. "
                "Each plate should have 64 sentinels + 318 experimental."
            )

    def test_each_plate_has_64_sentinels(self, all_assignments):
        """Each plate must have exactly 64 sentinel wells."""
        sentinels_per_plate = defaultdict(list)
        for w in all_assignments:
            if w.is_sentinel:
                sentinels_per_plate[w.plate_id].append(w)

        for plate_id, sentinels in sentinels_per_plate.items():
            assert len(sentinels) == 64, (
                f"Plate {plate_id} has {len(sentinels)} sentinels, expected 64. "
                "Sentinel count: 40 vehicle + 12 shoulder (6µM) + 12 collapse (15µM)."
            )

    def test_each_plate_has_318_experimental_wells(self, all_assignments):
        """Each plate must have exactly 318 experimental wells (53 × 6 doses)."""
        exp_per_plate = defaultdict(list)
        for w in all_assignments:
            if not w.is_sentinel:
                exp_per_plate[w.plate_id].append(w)

        for plate_id, experimental in exp_per_plate.items():
            assert len(experimental) == 318, (
                f"Plate {plate_id} has {len(experimental)} experimental wells, expected 318. "
                "Expected 53 replicates × 6 doses = 318."
            )


class TestDoseDistribution:
    """Verify dose distribution is balanced."""

    @pytest.fixture
    def design(self):
        return create_menadione_design()

    @pytest.fixture
    def all_assignments(self, design):
        return design.generate_design()

    def test_doses_are_shoulder_focused(self, design):
        """Doses must match the shoulder-focused range."""
        expected_doses = [0.0, 2.0, 4.0, 6.0, 8.0, 15.0]
        assert design.doses_uM == expected_doses, (
            f"Expected shoulder-focused doses {expected_doses}, got {design.doses_uM}. "
            "Phase 0 is NOT a toxicology study - doses should focus on pre-collapse shoulder."
        )

    def test_each_plate_has_53_reps_per_dose_in_experimental(self, all_assignments):
        """
        Each plate must have exactly 53 replicates per dose in experimental wells.
        This is the core replication requirement.
        """
        # Group by plate
        by_plate = defaultdict(list)
        for w in all_assignments:
            if not w.is_sentinel:
                by_plate[w.plate_id].append(w)

        for plate_id, wells in by_plate.items():
            # Count by dose
            dose_counts = defaultdict(int)
            for w in wells:
                dose_counts[w.dose_uM] += 1

            for dose, count in dose_counts.items():
                assert count == 53, (
                    f"Plate {plate_id}: dose {dose}µM has {count} reps, expected 53. "
                    "Dose balance is broken."
                )


class TestSentinelStructure:
    """Verify sentinel well structure."""

    @pytest.fixture
    def all_assignments(self):
        design = create_menadione_design()
        return design.generate_design()

    def test_sentinel_doses_are_correct(self, all_assignments):
        """
        Sentinel doses must be exactly {0.0, 6.0, 15.0}:
        - 0.0 µM: Vehicle sentinels (40 per plate)
        - 6.0 µM: Shoulder sentinels (~70% viability)
        - 15.0 µM: Collapse sentinels (~20% viability)
        """
        # Get unique sentinel doses across all plates
        sentinel_doses = set()
        for w in all_assignments:
            if w.is_sentinel:
                sentinel_doses.add(w.dose_uM)

        expected = {0.0, 6.0, 15.0}
        assert sentinel_doses == expected, (
            f"Sentinel doses are {sentinel_doses}, expected {expected}. "
            "Sentinels should be: vehicle (0µM), shoulder (6µM), collapse (15µM)."
        )

    def test_sentinel_counts_per_plate_are_40_12_12(self, all_assignments):
        """
        Each plate must have sentinel counts: 40 vehicle, 12 shoulder, 12 collapse.
        """
        # Group sentinels by plate
        by_plate = defaultdict(list)
        for w in all_assignments:
            if w.is_sentinel:
                by_plate[w.plate_id].append(w)

        for plate_id, sentinels in by_plate.items():
            # Count by dose
            dose_counts = defaultdict(int)
            for s in sentinels:
                dose_counts[s.dose_uM] += 1

            assert (
                dose_counts[0.0] == 40
            ), f"Plate {plate_id}: vehicle sentinels = {dose_counts[0.0]}, expected 40"
            assert (
                dose_counts[6.0] == 12
            ), f"Plate {plate_id}: shoulder sentinels (6µM) = {dose_counts[6.0]}, expected 12"
            assert (
                dose_counts[15.0] == 12
            ), f"Plate {plate_id}: collapse sentinels (15µM) = {dose_counts[15.0]}, expected 12"


class TestTemplateConsistency:
    """Verify templates are consistent with design."""

    def test_templates_match_design_constants(self):
        """Template generator constants must match design constants."""
        design = MenadionePhase0Design()
        templates = create_phase0_templates()

        # Check one template
        template = templates["A"]
        summary = template.get_summary()

        assert summary["sentinel_wells"] == design.SENTINEL_TOTAL, (
            f"Template sentinels ({summary['sentinel_wells']}) != "
            f"design constant ({design.SENTINEL_TOTAL})"
        )
        assert summary["experimental_wells"] == design.EXPERIMENTAL_WELLS_PER_PLATE, (
            f"Template experimental ({summary['experimental_wells']}) != "
            f"design constant ({design.EXPERIMENTAL_WELLS_PER_PLATE})"
        )

    def test_all_templates_have_same_sentinel_positions(self):
        """Sentinel positions must be identical across all templates."""
        templates = create_phase0_templates()

        sentinel_positions = {}
        for tid, template in templates.items():
            wells = template.get_all_wells()
            positions = frozenset(pos for pos, info in wells.items() if info["is_sentinel"])
            sentinel_positions[tid] = positions

        # All templates should have same sentinel positions
        pos_list = list(sentinel_positions.values())
        for i, pos in enumerate(pos_list[1:], 1):
            assert pos == pos_list[0], (
                f"Template {list(sentinel_positions.keys())[i]} has different "
                f"sentinel positions than Template {list(sentinel_positions.keys())[0]}. "
                "Sentinels must be fixed across all templates."
            )

    def test_templates_have_different_experimental_layouts(self):
        """Experimental well layouts must differ between templates."""
        templates = create_phase0_templates()

        exp_layouts = {}
        for tid, template in templates.items():
            wells = template.get_all_wells()
            # Map position -> dose for experimental wells only
            layout = {
                pos: info["dose_uM"] for pos, info in wells.items() if not info["is_sentinel"]
            }
            exp_layouts[tid] = layout

        # Templates should have different layouts
        # (same positions, different dose assignments)
        a_layout = exp_layouts["A"]
        b_layout = exp_layouts["B"]

        matching_doses = sum(
            1 for pos in a_layout if pos in b_layout and a_layout[pos] == b_layout[pos]
        )
        match_fraction = matching_doses / len(a_layout)

        # Should be ~16.7% by chance (1/6 doses)
        # Allow some tolerance but ensure they're different
        assert match_fraction < 0.25, (
            f"Templates A and B have {match_fraction:.1%} matching experimental positions, "
            f"expected ~16.7% by chance. Templates should be randomized differently."
        )


class TestReplicationMath:
    """Verify replication calculations match documentation."""

    def test_reps_per_dose_per_timepoint(self):
        """Replicates per dose/timepoint = 53 × 3 plates × 3 passages = 477."""
        design = create_menadione_design()
        expected = 53 * 3 * 3  # REPS_PER_DOSE_PER_PLATE × plates × passages

        assert design.reps_per_dose_per_timepoint == expected, (
            f"reps_per_dose_per_timepoint = {design.reps_per_dose_per_timepoint}, "
            f"expected {expected} (53 × 3 × 3)"
        )

    def test_total_plates_property(self):
        """total_plates property must return 18."""
        design = create_menadione_design()
        assert design.total_plates == 18

    def test_wells_per_plate_property(self):
        """wells_per_plate property must return 382."""
        design = create_menadione_design()
        assert design.wells_per_plate == 382

    def test_total_wells_property(self):
        """total_wells property must return 6876."""
        design = create_menadione_design()
        assert design.total_wells == 6876


class TestDesignSummaryAccuracy:
    """Verify get_summary() returns accurate values."""

    def test_summary_matches_generated_design(self):
        """Summary values must match actual generated design."""
        design = create_menadione_design()
        summary = design.get_summary()
        all_wells = design.generate_design()

        # Compare summary to actual
        actual_total = len(all_wells)
        actual_experimental = len([w for w in all_wells if not w.is_sentinel])
        actual_sentinels = len([w for w in all_wells if w.is_sentinel])
        actual_plates = len(set(w.plate_id for w in all_wells))

        assert summary["total_wells"] == actual_total
        assert summary["experimental_wells"] == actual_experimental
        assert summary["sentinel_wells"] == actual_sentinels
        assert summary["total_plates"] == actual_plates
        assert summary["wells_per_plate"] == actual_total // actual_plates
        assert summary["reps_per_dose_per_plate"] == 53
        assert summary["reps_per_dose_timepoint"] == 477  # 53 × 3 × 3


class TestDoseInvariantBidirectional:
    """Verify the dose invariant catches both failure modes."""

    def test_phantom_dose_in_design_raises_error(self):
        """
        Adding a dose to design that doesn't exist in templates must raise.

        This catches: "design claims 10µM exists but no plate has it."
        """
        with pytest.raises(AssertionError, match="In design but not on template"):
            MenadionePhase0Design(
                doses_uM=[0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 15.0]  # 10.0 is phantom
            )

    def test_rogue_dose_in_template_raises_error(self):
        """
        Template having a dose not in design must raise.

        This catches: "template generator was updated but design wasn't."
        Note: This is harder to test directly since we can't easily modify templates.
        Instead, we test by removing a dose from design that IS in templates.
        """
        with pytest.raises(AssertionError, match="On template but not in design"):
            MenadionePhase0Design(
                doses_uM=[0.0, 2.0, 4.0, 6.0, 15.0]  # Missing 8.0 that's in template
            )

    def test_valid_design_passes_invariant(self):
        """Valid design with matching doses passes invariant."""
        # Should not raise
        design = MenadionePhase0Design()
        assert design.doses_uM == [0.0, 2.0, 4.0, 6.0, 8.0, 15.0]


class TestVarianceModeParameter:
    """Verify variance_mode parameter works correctly."""

    def test_default_variance_mode_is_realistic(self):
        """Default variance_mode must be 'realistic'."""
        design = create_menadione_design()
        assert design.variance_model.enabled is True
        # Realistic has higher CVs than conservative
        bio = design.variance_model.biology_noise
        assert bio["growth_cv"] >= 0.10, "Realistic growth_cv should be >= 10%"

    def test_deterministic_mode_disables_variance(self):
        """Deterministic mode must disable all variance."""
        design = create_menadione_design(variance_mode="deterministic")
        assert design.variance_model.enabled is False

    def test_conservative_mode_has_lower_cvs(self):
        """Conservative mode must have lower CVs than realistic."""
        conservative = create_menadione_design(variance_mode="conservative")
        realistic = create_menadione_design(variance_mode="realistic")

        cons_bio = conservative.variance_model.biology_noise
        real_bio = realistic.variance_model.biology_noise

        assert cons_bio["growth_cv"] < real_bio["growth_cv"], (
            f"Conservative growth_cv ({cons_bio['growth_cv']}) should be < "
            f"realistic ({real_bio['growth_cv']})"
        )
        assert cons_bio["stress_sensitivity_cv"] < real_bio["stress_sensitivity_cv"], (
            f"Conservative stress_cv ({cons_bio['stress_sensitivity_cv']}) should be < "
            f"realistic ({real_bio['stress_sensitivity_cv']})"
        )

    def test_invalid_variance_mode_raises(self):
        """Invalid variance_mode must raise ValueError."""
        with pytest.raises(ValueError, match="Unknown variance_mode"):
            create_menadione_design(variance_mode="invalid_mode")

    def test_variance_mode_does_not_affect_design_structure(self):
        """Variance mode should not affect plate/well counts."""
        deterministic = create_menadione_design(variance_mode="deterministic")
        realistic = create_menadione_design(variance_mode="realistic")

        # Generate designs
        det_wells = deterministic.generate_design()
        real_wells = realistic.generate_design()

        # Same structure
        assert len(det_wells) == len(real_wells), "Variance mode should not change well count"
        assert deterministic.total_plates == realistic.total_plates
        assert deterministic.wells_per_plate == realistic.wells_per_plate
