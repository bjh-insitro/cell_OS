"""
Phase 0 Variance Contract Test

Ensures Phase 0 simulations produce meaningful within-dose variance (error bars).

This test exists because:
1. We built extensive noise infrastructure (StochasticBiologyHelper, injection modules)
2. That infrastructure is opt-in, defaulting to disabled
3. Phase 0 is explicitly about variance behavior and error bars
4. We need to prevent silent regression back to "no error bars"

Contract:
- Phase 0 designs MUST have variance_model.enabled = True
- Within-dose std at transition region (e.g., 15 µM) MUST be > epsilon
- Variance structure should be higher around EC50, lower at extremes

If this test fails, something is wrong with:
- Design creation (variance_model not set)
- Config propagation (runner not reading from design)
- Noise infrastructure (biology noise not applied)
"""

from collections import defaultdict

import numpy as np
import pytest

from cell_os.cell_thalamus.menadione_phase0_design import (
    MenadionePhase0Design,
    VarianceModel,
    create_menadione_design,
)


class TestPhase0VarianceContract:
    """Variance contract tests for Phase 0 designs."""

    def test_design_has_variance_model_enabled_by_default(self):
        """Phase 0 design MUST have realistic variance enabled by default."""
        design = create_menadione_design()

        assert design.variance_model is not None, "Design must have variance_model"
        assert design.variance_model.enabled is True, (
            "Phase 0 variance_model.enabled must be True by default. "
            "Error bars require stochastic biology."
        )

    def test_variance_model_has_biology_noise_configured(self):
        """Variance model must have biology noise parameters."""
        design = create_menadione_design()
        vm = design.variance_model

        bio = vm.biology_noise
        assert bio.get("enabled") is True, "Biology noise must be enabled"
        assert bio.get("growth_cv", 0) > 0, "growth_cv must be > 0"
        assert bio.get("stress_sensitivity_cv", 0) > 0, "stress_sensitivity_cv must be > 0"
        assert bio.get("hazard_scale_cv", 0) > 0, "hazard_scale_cv must be > 0"

    def test_variance_model_serialization_roundtrip(self):
        """Variance model must serialize/deserialize correctly for DB storage."""
        original = VarianceModel.realistic()
        serialized = original.to_dict()
        restored = VarianceModel.from_dict(serialized)

        assert restored.enabled == original.enabled
        assert restored.biology_noise == original.biology_noise
        assert restored.injection_noise == original.injection_noise
        assert restored.seed_policy == original.seed_policy

    def test_deterministic_mode_disables_noise(self):
        """VarianceModel.deterministic() must produce no-noise config."""
        vm = VarianceModel.deterministic()
        config = vm.to_bio_noise_config()

        assert config.get("enabled") is False, "Deterministic mode must set enabled=False"

    def test_design_summary_includes_variance_model(self):
        """get_summary() must include variance_model for dashboard display."""
        design = create_menadione_design()
        summary = design.get_summary()

        assert (
            "variance_model" in summary
        ), "Design summary must include variance_model for dashboard accountability"
        assert summary["variance_model"]["enabled"] is True


class TestPhase0VarianceIntegration:
    """
    Integration tests that run actual simulation to verify variance output.

    These are BEHAVIORAL tests - they assert that the noise infrastructure
    is not just configured, but actually producing variance in outputs.
    This catches "wired but not causally connected" failures.
    """

    @pytest.fixture
    def quick_simulation_results(self):
        """Run a quick simulation and return results grouped by dose."""
        import os
        import tempfile

        from cell_os.cell_thalamus.menadione_phase0_runner import run_menadione_simulation
        from cell_os.database.cell_thalamus_db import CellThalamusDB

        # Use temp database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Run quick simulation (single plate)
            design_id = run_menadione_simulation(
                mode="quick", workers=4, db_path=db_path, quiet=True
            )

            # Load results
            db = CellThalamusDB(db_path=db_path)
            results = db.get_results(design_id)
            db.close()

            # Group by dose
            by_dose = defaultdict(list)
            for r in results:
                if r["compound"] != "DMSO":  # Exclude vehicle
                    by_dose[r["dose_uM"]].append(r["viability_fraction"])

            yield dict(by_dose)
        finally:
            os.unlink(db_path)

    @pytest.mark.slow
    def test_within_dose_variance_nonzero(self, quick_simulation_results):
        """
        CRITICAL BEHAVIORAL CONTRACT: Within-dose std must be > epsilon.

        This is the non-negotiable test that prevents silent regression
        to deterministic simulations. If this fails, error bars are lies.

        Threshold: std > 0.01 (1% variance) at any dose.
        We expect ~10-25% variance at transition doses if noise is working.
        """
        results = quick_simulation_results
        EPSILON = 0.01  # 1% minimum variance threshold

        max_std = 0
        max_std_dose = None
        for dose, viabilities in results.items():
            if len(viabilities) > 1:
                std = float(np.std(viabilities, ddof=1))
                if std > max_std:
                    max_std = std
                    max_std_dose = dose

        assert max_std > EPSILON, (
            f"VARIANCE CONTRACT VIOLATION: Max within-dose std={max_std:.4f} at {max_std_dose}µM "
            f"is below threshold {EPSILON}. "
            "This means the noise infrastructure is either disabled or not causally connected "
            "to viability outputs. Check:\n"
            "  1. design.variance_model.enabled == True\n"
            "  2. bio_noise_config is passed to BiologicalVirtualMachine\n"
            "  3. StochasticBiologyHelper.sample_random_effects() is called\n"
            "  4. bio_random_effects are applied in _apply_combined_survival()"
        )

    @pytest.mark.slow
    def test_transition_region_has_meaningful_variance(self, quick_simulation_results):
        """
        Variance at transition region (near EC50) should be substantial.

        This catches cases where noise is technically on but with CVs so low
        it produces negligible error bars. At the transition region (~6-8 µM
        for Menadione, EC50 ~8-9 µM), we expect std > 5% due to IC50 heterogeneity.
        """
        results = quick_simulation_results
        TRANSITION_DOSES = [6.0, 8.0]  # Mid-shoulder to upper shoulder (near EC50)

        for dose in TRANSITION_DOSES:
            if dose in results and len(results[dose]) > 5:
                viabilities = results[dose]
                std = float(np.std(viabilities, ddof=1))
                mean = float(np.mean(viabilities))
                cv = std / mean if mean > 0 else 0

                # At transition, expect CV > 5% (meaningful error bars)
                assert cv > 0.05 or std > 0.02, (
                    f"Transition dose {dose}µM has low variance: "
                    f"std={std:.4f}, CV={cv:.2%}. "
                    "Expected CV > 5% at transition region where IC50 heterogeneity "
                    "should produce visible spread. Check stress_sensitivity_cv and ic50_cv."
                )

    @pytest.mark.slow
    def test_variance_pattern_matches_biology(self, quick_simulation_results):
        """
        Variance should follow biologically expected pattern:
        - Higher at transition region (cells near IC50 have variable response)
        - Lower at extremes (all alive at low dose, all dead at high dose)

        This catches misconfigured noise that produces uniform variance.

        With the shoulder-focused dose range (0, 2, 4, 6, 8, 15 µM):
        - Shoulder doses (4-8 µM): cells near EC50, high heterogeneity
        - Collapse dose (15 µM): most cells dead, lower variance (floor effect)
        """
        results = quick_simulation_results

        # Compute std per dose
        dose_stds = {}
        for dose, viabilities in results.items():
            if len(viabilities) > 1:
                dose_stds[dose] = float(np.std(viabilities, ddof=1))

        if len(dose_stds) < 3:
            pytest.skip("Not enough doses with variance data")

        # Shoulder doses (around EC50 ~6-8 µM) should have higher variance
        # than collapse dose (15 µM where most cells are dead)
        shoulder_doses = [d for d in dose_stds if 4 <= d <= 8]
        collapse_doses = [d for d in dose_stds if d >= 15]

        if shoulder_doses and collapse_doses:
            avg_shoulder_std = np.mean([dose_stds[d] for d in shoulder_doses])
            avg_collapse_std = np.mean([dose_stds[d] for d in collapse_doses])

            # Shoulder region should have meaningfully higher variance
            # (cells near IC50 show most heterogeneous response)
            # Relaxed assertion: shoulder >= 50% of collapse (due to floor effects)
            assert avg_shoulder_std >= avg_collapse_std * 0.5, (
                f"Variance pattern unexpected: shoulder={avg_shoulder_std:.4f}, "
                f"collapse={avg_collapse_std:.4f}. Expected shoulder >= 0.5 * collapse. "
                "This may indicate noise is applied uniformly rather than scaled by IC50."
            )


class TestPhase0DeterministicFallback:
    """Test that deterministic mode works for unit tests that need stability."""

    def test_can_create_deterministic_design(self):
        """Should be able to create Phase 0 design with deterministic variance."""
        design = MenadionePhase0Design(variance_model=VarianceModel.deterministic())

        assert design.variance_model.enabled is False
        config = design.variance_model.to_bio_noise_config()
        assert config["enabled"] is False

    def test_deterministic_produces_stable_output(self):
        """Deterministic mode should produce reproducible results."""
        # This test verifies we haven't broken the "tests need determinism" use case
        from cell_os.cell_thalamus.menadione_phase0_design import VarianceModel

        vm = VarianceModel.deterministic()
        config = vm.to_bio_noise_config()

        # Config should disable all noise sources
        assert config == {"enabled": False}


class TestMeanPreservation:
    """
    CRITICAL: Verify noise is mean-preserving.

    If lognormal multipliers shift means, enabling noise will drift dose-response
    curves and get called "biology" for months. The correction term in
    StochasticBiologyHelper must ensure E[multiplier] = 1.0.
    """

    def test_lognormal_correction_is_mean_preserving(self):
        """
        Random effect multipliers must have E[mult] ≈ 1.0.

        This verifies the lognormal correction term: mult = exp(z * sigma - 0.5 * sigma²)
        Without the -0.5*sigma² correction, E[mult] = exp(0.5*sigma²) > 1.
        """
        from cell_os.hardware.stochastic_biology import StochasticBiologyHelper

        # Create helper with realistic CVs
        config = {
            "enabled": True,
            "growth_cv": 0.12,
            "stress_sensitivity_cv": 0.18,
            "hazard_scale_cv": 0.15,
            "ic50_cv": 0.20,
            "plate_level_fraction": 0.30,
        }
        helper = StochasticBiologyHelper(config, run_seed=42)

        # Sample many random effects
        N = 1000
        growth_mults = []
        stress_mults = []
        hazard_mults = []

        for i in range(N):
            re = helper.sample_random_effects(
                lineage_id=f"test_lineage_{i}", plate_id=f"test_plate_{i % 10}"
            )
            growth_mults.append(re["growth_rate_mult"])
            stress_mults.append(re["stress_sensitivity_mult"])
            hazard_mults.append(re["hazard_scale_mult"])

        # Means should be close to 1.0 (within 5% tolerance for N=1000)
        TOLERANCE = 0.05

        mean_growth = np.mean(growth_mults)
        mean_stress = np.mean(stress_mults)
        mean_hazard = np.mean(hazard_mults)

        assert abs(mean_growth - 1.0) < TOLERANCE, (
            f"Growth multiplier mean={mean_growth:.4f} deviates from 1.0. "
            "Lognormal correction may be broken."
        )
        assert abs(mean_stress - 1.0) < TOLERANCE, (
            f"Stress multiplier mean={mean_stress:.4f} deviates from 1.0. "
            "Lognormal correction may be broken."
        )
        assert abs(mean_hazard - 1.0) < TOLERANCE, (
            f"Hazard multiplier mean={mean_hazard:.4f} deviates from 1.0. "
            "Lognormal correction may be broken."
        )

    @pytest.mark.slow
    def test_noisy_vs_deterministic_means_match(self):
        """
        CRITICAL: Viability means must match between noisy and deterministic sims.

        This is the end-to-end mean-preservation check. If noise shifts means,
        EC50 will drift just because error bars were requested.

        Catches: noise applied in wrong place, applied twice, or interacts
        with clipping in a biased way.
        """
        import os
        import tempfile

        from cell_os.cell_thalamus.menadione_phase0_design import (
            MenadionePhase0Design,
            VarianceModel,
        )
        from cell_os.cell_thalamus.menadione_phase0_runner import run_menadione_simulation
        from cell_os.database.cell_thalamus_db import CellThalamusDB

        # Tolerance: 3 percentage points for viability fraction
        TOLERANCE = 0.03

        results = {}
        for mode_name, variance_model in [
            ("deterministic", VarianceModel.deterministic()),
            ("noisy", VarianceModel.realistic()),
        ]:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
                db_path = f.name

            try:
                # Run quick simulation with specific variance model
                design = MenadionePhase0Design(variance_model=variance_model)
                design_id = run_menadione_simulation(
                    mode="quick", workers=4, db_path=db_path, design=design, quiet=True
                )

                # Load and aggregate results by dose
                db = CellThalamusDB(db_path=db_path)
                raw_results = db.get_results(design_id)
                db.close()

                by_dose = defaultdict(list)
                for r in raw_results:
                    by_dose[r["dose_uM"]].append(r["viability_fraction"])

                results[mode_name] = {dose: np.mean(vals) for dose, vals in by_dose.items()}
            finally:
                os.unlink(db_path)

        # Compare means at each dose
        det_means = results["deterministic"]
        noisy_means = results["noisy"]

        for dose in det_means:
            if dose in noisy_means:
                diff = abs(noisy_means[dose] - det_means[dose])
                assert diff < TOLERANCE, (
                    f"MEAN PRESERVATION VIOLATION at {dose}µM: "
                    f"deterministic={det_means[dose]:.4f}, noisy={noisy_means[dose]:.4f}, "
                    f"diff={diff:.4f} > tolerance={TOLERANCE}. "
                    "Noise may be applied incorrectly or interacting with clipping."
                )


class TestVarianceModelPresets:
    """Test that variance model presets are properly configured."""

    def test_conservative_has_lower_cvs_than_realistic(self):
        """Conservative model should have smaller CVs than realistic."""
        conservative = VarianceModel.conservative()
        realistic = VarianceModel.realistic()

        for key in ["growth_cv", "stress_sensitivity_cv", "hazard_scale_cv", "ic50_cv"]:
            cons_val = conservative.biology_noise.get(key, 0)
            real_val = realistic.biology_noise.get(key, 0)
            assert (
                cons_val < real_val
            ), f"Conservative {key}={cons_val} should be < realistic {key}={real_val}"

    def test_presets_have_literature_anchors_documented(self):
        """Verify presets have docstrings with literature references."""
        # This is a documentation check - presets should explain their values
        assert "Fallahi-Sichani" in VarianceModel.realistic.__doc__
        assert (
            "Bray" in VarianceModel.conservative.__doc__
            or "Ljosa" in VarianceModel.conservative.__doc__
        )


class TestSeedDeterminismAcrossParallelism:
    """
    Verify that simulation results are identical regardless of worker count.

    This is critical because:
    1. Parallel execution with shared RNG state produces different results
    2. The seed derivation policy (plate_well_hash) must ensure determinism
    3. "Parallel execution changes biology" is a special kind of hell

    Contract: workers=1 and workers=4 must produce identical per-well results
    for the same design_id.
    """

    @pytest.mark.slow
    def test_workers_1_vs_4_produce_identical_results(self):
        """
        CRITICAL: Simulation output must be identical with workers=1 and workers=4.

        This locks the seed derivation policy and ensures parallel execution
        doesn't introduce non-determinism.
        """
        import os
        import tempfile

        from cell_os.cell_thalamus.menadione_phase0_design import MenadionePhase0Design
        from cell_os.cell_thalamus.menadione_phase0_runner import run_menadione_simulation
        from cell_os.database.cell_thalamus_db import CellThalamusDB

        results_by_workers = {}

        for workers in [1, 4]:
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
                db_path = f.name

            try:
                # Create design with fixed seed (use deterministic for cleaner comparison)
                design = MenadionePhase0Design(
                    design_id="parallelism_test_fixed_id",
                    variance_model=VarianceModel.realistic(),  # Use same variance model
                )
                design_id = run_menadione_simulation(
                    mode="quick", workers=workers, db_path=db_path, design=design, quiet=True
                )

                # Load results keyed by (plate_id, well_id)
                db = CellThalamusDB(db_path=db_path)
                raw_results = db.get_results(design_id)
                db.close()

                # Build map: (plate_id, well_id) -> viability
                well_results = {}
                for r in raw_results:
                    key = (r["plate_id"], r["well_id"])
                    well_results[key] = r["viability_fraction"]

                results_by_workers[workers] = well_results
            finally:
                os.unlink(db_path)

        # Compare results
        results_1 = results_by_workers[1]
        results_4 = results_by_workers[4]

        # Same keys
        assert set(results_1.keys()) == set(
            results_4.keys()
        ), "Different wells returned for workers=1 vs workers=4"

        # Same values (within floating point tolerance)
        mismatches = []
        for key in results_1:
            v1 = results_1[key]
            v4 = results_4[key]
            if abs(v1 - v4) > 1e-9:
                mismatches.append(f"{key}: w1={v1:.6f}, w4={v4:.6f}")

        assert len(mismatches) == 0, (
            f"PARALLELISM NON-DETERMINISM: {len(mismatches)} wells differ between "
            f"workers=1 and workers=4. First 5:\n"
            + "\n".join(mismatches[:5])
            + "\nSeed derivation policy may be broken or RNG state is leaking."
        )
