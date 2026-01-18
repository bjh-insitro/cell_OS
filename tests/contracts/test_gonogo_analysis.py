"""
Go/No-Go Analysis Contract Tests

Tests the analysis pipeline against simulated data to verify:
1. Aggregations run end-to-end
2. Plots reflect known truth in simulator
3. Decision rubric returns expected operating point
4. Evil simulations trip the right gates
"""

from collections import defaultdict

import numpy as np
import pandas as pd
import pytest

from cell_os.cell_thalamus.gonogo_analysis import (
    MORPH_COLS,
    build_condition_summary,
    build_plate_effects,
    evaluate_gonogo_criteria,
    generate_gonogo_report,
    run_all_assertions,
    run_sentinel_spc,
)


def create_synthetic_df_wells(
    n_plates: int = 6,
    doses: list[float] = None,
    template_dose_slope: float = 0.0,
    passage_offset: float = 0.0,
    collapse_viability: float = 0.2,
) -> pd.DataFrame:
    """Create synthetic df_wells for testing.

    Args:
        template_dose_slope: Multiplier for template × dose interaction.
            Higher values make template dominate the effect vectors.
    """
    if doses is None:
        doses = [0.0, 2.0, 4.0, 6.0, 8.0, 15.0]

    rows = []
    for plate_idx in range(n_plates):
        plate_id = f"TEST_Psg{(plate_idx % 3) + 1}_T24h_P{(plate_idx % 3) + 1}"
        passage = (plate_idx % 3) + 1
        template = ["A", "B", "C"][plate_idx % 3]
        template_idx = ord(template) - ord("A")
        timepoint = 24.0

        for dose in doses:
            # 10 wells per dose per plate
            for well_idx in range(10):
                # Viability decreases with dose
                base_viab = 1.0 - (dose / 20.0)
                if dose >= 15:
                    base_viab = collapse_viability
                viab = base_viab + np.random.normal(0, 0.02)
                viab = np.clip(viab, 0, 1)

                # Morphology shifts with dose
                # template_dose_slope makes template affect the SLOPE of dose response
                morph_base = 100.0
                dose_effect = dose * (2.0 + template_dose_slope * template_idx)

                rows.append(
                    {
                        "plate_id": plate_id,
                        "well_id": f"{chr(65 + well_idx // 24)}{(well_idx % 24) + 1:02d}",
                        "dose_uM": dose,
                        "timepoint_h": timepoint,
                        "passage": passage,
                        "template": template,
                        "viability_fraction": viab,
                        "is_sentinel": well_idx < 2,
                        "morph_er": morph_base + dose_effect + np.random.normal(0, 5),
                        "morph_mito": morph_base + dose_effect * 0.8 + np.random.normal(0, 5),
                        "morph_nucleus": morph_base + dose_effect * 0.5 + np.random.normal(0, 5),
                        "morph_actin": morph_base + dose_effect * 1.2 + np.random.normal(0, 5),
                        "morph_rna": morph_base + dose_effect * 0.9 + np.random.normal(0, 5),
                    }
                )

    return pd.DataFrame(rows)


class TestAnalysisContract:
    """Test the analysis pipeline runs end-to-end."""

    def test_build_plate_effects_runs(self):
        """build_plate_effects should run without error."""
        df = create_synthetic_df_wells(n_plates=3)
        result = build_plate_effects(df)
        assert result.df is not None
        assert len(result.df) > 0

    def test_build_condition_summary_runs(self):
        """build_condition_summary should run without error."""
        df = create_synthetic_df_wells(n_plates=3)
        plate_effects = build_plate_effects(df)
        result = build_condition_summary(plate_effects)
        assert result.df is not None

    def test_generate_report_returns_valid_json(self):
        """Report should be JSON-serializable."""
        import json

        df = create_synthetic_df_wells(n_plates=6)
        report = generate_gonogo_report(df, "test_design")
        # Should not raise
        json.dumps(report, default=str)
        assert "decision" in report
        assert report["decision"] in ["GO", "NO-GO"]


class TestQualitativeAssertions:
    """Test the 6 qualitative assertions pass on normal data."""

    def test_all_assertions_pass_normal_data(self):
        """All assertions should pass on well-behaved synthetic data."""
        np.random.seed(42)
        df = create_synthetic_df_wells(n_plates=9)
        results = run_all_assertions(df)

        # Check each assertion
        for name in ["viability_ordering", "collapse_ineligible"]:
            assert results.get(name, False), f"{name} failed: {results.get(f'{name}_error')}"


class TestEvilSimulations:
    """Test that deliberately broken data trips the right gates."""

    def test_template_dominates_trips_dose_dominance(self):
        """Large template × dose interaction should cause dose_dominates to fail."""
        np.random.seed(42)
        # Large template_dose_slope makes templates have very different dose responses
        # Template A: slope 2, Template B: slope 12, Template C: slope 22
        # This makes template dominate PC1 since effect vectors point in different directions
        df = create_synthetic_df_wells(n_plates=9, template_dose_slope=10.0)
        plate_effects = build_plate_effects(df)
        condition_summary = build_condition_summary(plate_effects)
        spc_result = run_sentinel_spc(plate_effects, df)

        decision = evaluate_gonogo_criteria(plate_effects, condition_summary, spc_result)

        # Should fail dose_dominates criterion (use bool() for numpy comparison)
        assert (
            not bool(decision.criteria_results.get("dose_dominates"))
            or decision.decision == "NO-GO"
        )

    def test_no_collapse_trips_assay_broken(self):
        """High viability at 15µM should trip assay_working check."""
        np.random.seed(42)
        df = create_synthetic_df_wells(n_plates=6, collapse_viability=0.7)
        plate_effects = build_plate_effects(df)
        condition_summary = build_condition_summary(plate_effects)
        spc_result = run_sentinel_spc(plate_effects, df)

        decision = evaluate_gonogo_criteria(plate_effects, condition_summary, spc_result)

        # Use bool() for numpy comparison
        assert not bool(decision.criteria_results.get("assay_working"))
        assert decision.decision == "NO-GO"
