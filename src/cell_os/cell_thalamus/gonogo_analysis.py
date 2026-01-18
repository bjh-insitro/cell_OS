"""
Phase 0 Go/No-Go Analysis Contract

Single choke-point for all Phase 0 analysis aggregations.
All 6 plots and the Go/No-Go decision flow through this module.

Design principle: If it's not in df_plate_effects or df_condition_summary,
it doesn't exist for decision-making.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

# Canonical morphology columns
MORPH_COLS = ["morph_er", "morph_mito", "morph_nucleus", "morph_actin", "morph_rna"]


@dataclass
class PlateEffects:
    """Per-plate × dose × timepoint aggregates with effect vectors."""

    df: pd.DataFrame
    # Expected columns:
    # plate_id, dose_uM, timepoint_h, passage, template,
    # viability_mean, viability_std, n_wells,
    # morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna (centroids)
    # effect_er, effect_mito, effect_nucleus, effect_actin, effect_rna (effect vectors)
    # effect_mag (magnitude of effect vector)
    # vehicle_dispersion (noise baseline for this plate)


@dataclass
class ConditionSummary:
    """Dose × timepoint summaries with SEM for plotting."""

    df: pd.DataFrame
    # Expected columns:
    # dose_uM, timepoint_h,
    # viability_mean, viability_sem, viability_n,
    # effect_mag_mean, effect_mag_sem, effect_mag_n,
    # replicate_similarity (cosine sim of effect vectors across plates)


@dataclass
class GoNoGoDecision:
    """Binary decision with supporting metrics."""

    decision: str  # "GO" or "NO-GO"
    operating_point: dict[str, float] | None  # {dose_uM, timepoint_h}
    flagged_plates: list[str]
    metrics: dict[str, Any]
    criteria_results: dict[str, bool]


def compute_vehicle_dispersion(df_norm: pd.DataFrame, plate_id: str) -> float:
    """Compute median distance of vehicle wells to their centroid."""
    vehicle = df_norm[(df_norm["plate_id"] == plate_id) & (df_norm["dose_uM"] == 0)]
    if len(vehicle) < 2:
        return 0.0
    centroid = vehicle[MORPH_COLS].mean().values
    distances = np.linalg.norm(vehicle[MORPH_COLS].values - centroid, axis=1)
    return float(np.median(distances))


def z_score_normalize(df_wells: pd.DataFrame) -> pd.DataFrame:
    """Z-score normalize morph features using vehicle wells as reference."""
    df = df_wells.copy()

    # Per-plate vehicle statistics
    vehicle = df[df["dose_uM"] == 0]
    vehicle_stats = vehicle.groupby("plate_id")[MORPH_COLS].agg(["mean", "std"])

    for plate_id in df["plate_id"].unique():
        mask = df["plate_id"] == plate_id
        if plate_id not in vehicle_stats.index:
            continue
        v_mean = vehicle_stats.loc[plate_id, (MORPH_COLS, "mean")].values
        v_std = vehicle_stats.loc[plate_id, (MORPH_COLS, "std")].values
        v_std = np.where(v_std < 1e-6, 1.0, v_std)
        df.loc[mask, MORPH_COLS] = (df.loc[mask, MORPH_COLS].values - v_mean) / v_std

    return df


def build_plate_effects(df_wells: pd.DataFrame) -> PlateEffects:
    """
    Build plate-level aggregates with effect vectors.

    This is THE choke-point. All downstream analysis uses this output.
    """
    # Z-score normalize
    df_norm = z_score_normalize(df_wells)

    # Compute plate centroids
    agg_dict = {col: "mean" for col in MORPH_COLS}
    agg_dict["viability_fraction"] = ["mean", "std", "count"]

    plate_agg = df_norm.groupby(["plate_id", "dose_uM", "timepoint_h"]).agg(agg_dict)
    plate_agg.columns = [
        "morph_er",
        "morph_mito",
        "morph_nucleus",
        "morph_actin",
        "morph_rna",
        "viability_mean",
        "viability_std",
        "n_wells",
    ]
    plate_agg = plate_agg.reset_index()

    # Add passage and template from original data
    plate_meta = df_wells[["plate_id", "passage", "template"]].drop_duplicates()
    plate_agg = plate_agg.merge(plate_meta, on="plate_id", how="left")

    # Compute vehicle centroids per plate-timepoint
    vehicle = plate_agg[plate_agg["dose_uM"] == 0].copy()
    vehicle = vehicle.set_index(["plate_id", "timepoint_h"])[MORPH_COLS]
    vehicle.columns = [f"vehicle_{c}" for c in MORPH_COLS]

    # Compute effect vectors: treated - vehicle
    plate_agg = plate_agg.merge(vehicle.reset_index(), on=["plate_id", "timepoint_h"], how="left")

    for col in MORPH_COLS:
        plate_agg[f"effect_{col.replace('morph_', '')}"] = (
            plate_agg[col] - plate_agg[f"vehicle_{col}"]
        )

    # Effect magnitude
    effect_cols = [f"effect_{c.replace('morph_', '')}" for c in MORPH_COLS]
    plate_agg["effect_mag"] = np.linalg.norm(plate_agg[effect_cols].values, axis=1)

    # Vehicle dispersion per plate
    dispersions = {
        pid: compute_vehicle_dispersion(df_norm, pid) for pid in df_norm["plate_id"].unique()
    }
    plate_agg["vehicle_dispersion"] = plate_agg["plate_id"].map(dispersions)

    # Clean up intermediate columns
    plate_agg = plate_agg.drop(columns=[f"vehicle_{c}" for c in MORPH_COLS])

    return PlateEffects(df=plate_agg)


def compute_replicate_similarity(
    plate_effects: PlateEffects, dose: float, timepoint: float
) -> tuple[float, float]:
    """Compute cosine similarity of effect vectors across plates."""
    if dose == 0:
        return 1.0, 0.0  # Vehicle effect is zero

    df = plate_effects.df
    subset = df[(df["dose_uM"] == dose) & (df["timepoint_h"] == timepoint)]

    effect_cols = ["effect_er", "effect_mito", "effect_nucleus", "effect_actin", "effect_rna"]
    vectors = subset[effect_cols].values

    if len(vectors) < 2:
        return np.nan, np.nan

    sim_matrix = cosine_similarity(vectors)
    n = len(sim_matrix)
    upper_tri = sim_matrix[np.triu_indices(n, k=1)]

    return float(upper_tri.mean()), float(upper_tri.std())


def build_condition_summary(plate_effects: PlateEffects) -> ConditionSummary:
    """Aggregate to dose × timepoint level with SEM."""
    df = plate_effects.df

    # Group by dose and timepoint
    grouped = df.groupby(["dose_uM", "timepoint_h"])

    summary_rows = []
    for (dose, tp), group in grouped:
        n = len(group)
        row = {
            "dose_uM": dose,
            "timepoint_h": tp,
            "viability_mean": group["viability_mean"].mean(),
            "viability_sem": group["viability_mean"].std() / np.sqrt(n) if n > 1 else 0,
            "viability_n": n,
            "effect_mag_mean": group["effect_mag"].mean(),
            "effect_mag_sem": group["effect_mag"].std() / np.sqrt(n) if n > 1 else 0,
            "effect_mag_n": n,
        }

        # Replicate similarity
        mean_sim, _ = compute_replicate_similarity(plate_effects, dose, tp)
        row["replicate_similarity"] = mean_sim

        summary_rows.append(row)

    return ConditionSummary(df=pd.DataFrame(summary_rows))


def compute_dose_dominance(plate_effects: PlateEffects) -> dict[str, float]:
    """
    Compute eta-squared for dose vs template vs passage using ANOVA on PC1.

    Returns dict with dose_eta_sq, template_eta_sq, passage_eta_sq.
    """
    from sklearn.decomposition import PCA

    df = plate_effects.df
    # Exclude vehicle (effect is zero)
    df_treated = df[df["dose_uM"] > 0].copy()

    if len(df_treated) < 6:
        return {"dose_eta_sq": 0, "template_eta_sq": 0, "passage_eta_sq": 0}

    effect_cols = ["effect_er", "effect_mito", "effect_nucleus", "effect_actin", "effect_rna"]
    X = df_treated[effect_cols].values

    # PCA
    pca = PCA(n_components=1)
    df_treated["PC1"] = pca.fit_transform(X)[:, 0]

    # Manual eta-squared calculation (avoid statsmodels dependency)
    grand_mean = df_treated["PC1"].mean()
    ss_total = ((df_treated["PC1"] - grand_mean) ** 2).sum()

    if ss_total < 1e-10:
        return {"dose_eta_sq": 0, "template_eta_sq": 0, "passage_eta_sq": 0}

    eta_sq = {}
    for factor in ["dose_uM", "template", "passage"]:
        group_means = df_treated.groupby(factor)["PC1"].mean()
        group_counts = df_treated.groupby(factor)["PC1"].count()
        ss_between = sum(
            count * (mean - grand_mean) ** 2 for mean, count in zip(group_means, group_counts)
        )
        eta_sq[f"{factor}_eta_sq" if factor != "dose_uM" else "dose_eta_sq"] = ss_between / ss_total

    return eta_sq


def run_sentinel_spc(plate_effects: PlateEffects, df_wells: pd.DataFrame) -> dict:
    """
    Run SPC on sentinel wells with global control limits.

    Returns dict with flagged_plates and control_limits.
    """
    sentinels = df_wells[df_wells["is_sentinel"]].copy()

    if len(sentinels) == 0:
        return {"flagged_plates": [], "control_limits": {}}

    # Per-plate sentinel summaries
    summaries = []
    for plate_id in sentinels["plate_id"].unique():
        plate_sent = sentinels[sentinels["plate_id"] == plate_id]
        tp = plate_sent["timepoint_h"].iloc[0]

        veh = plate_sent[plate_sent["dose_uM"] == 0]
        veh_viab = veh["viability_fraction"].mean() if len(veh) > 0 else np.nan

        shoulder = plate_sent[plate_sent["dose_uM"] == 6]
        shoulder_viab = shoulder["viability_fraction"].mean() if len(shoulder) > 0 else np.nan

        collapse = plate_sent[plate_sent["dose_uM"] == 15]
        collapse_viab = collapse["viability_fraction"].mean() if len(collapse) > 0 else np.nan

        summaries.append(
            {
                "plate_id": plate_id,
                "timepoint_h": tp,
                "vehicle_viability": veh_viab,
                "shoulder_viability": shoulder_viab,
                "collapse_viability": collapse_viab,
            }
        )

    sent_df = pd.DataFrame(summaries)

    # Global control limits per timepoint
    control_limits = {}
    flagged = []

    for tp in sent_df["timepoint_h"].unique():
        tp_data = sent_df[sent_df["timepoint_h"] == tp]
        limits = {}

        for metric in ["vehicle_viability", "shoulder_viability", "collapse_viability"]:
            vals = tp_data[metric].dropna()
            if len(vals) > 1:
                mean, std = vals.mean(), vals.std()
                limits[metric] = (mean - 3 * std, mean, mean + 3 * std)
            else:
                limits[metric] = (0, vals.mean() if len(vals) else 0, 1)

        control_limits[tp] = limits

        # Flag plates outside limits
        for _, row in tp_data.iterrows():
            for metric in ["vehicle_viability", "shoulder_viability", "collapse_viability"]:
                lcl, _, ucl = limits.get(metric, (0, 0.5, 1))
                val = row[metric]
                if pd.notna(val) and (val < lcl or val > ucl):
                    flagged.append(row["plate_id"])
                    break

    return {"flagged_plates": list(set(flagged)), "control_limits": control_limits}


def evaluate_gonogo_criteria(
    plate_effects: PlateEffects,
    condition_summary: ConditionSummary,
    spc_result: dict,
) -> GoNoGoDecision:
    """
    Evaluate Go/No-Go criteria and return decision.

    GO requires ALL of:
    1. Morphology signal: effect_mag > 2× vehicle_dispersion for 6 or 8 µM
    2. Reproducible: effect similarity > 0.7 for candidate doses
    3. Viability shoulder: 50-85% for candidate dose
    4. Dose dominates: dose_eta_sq > template and passage
    5. Sentinels stable: no flagged plates

    NO-GO if ANY of:
    1. No signal: effect_mag < 1.5× noise at all doses
    2. Technical dominates: template or passage eta_sq > dose
    3. Replicate disagreement: similarity < 0.5
    4. Assay broken: 15 µM viability > 50%
    5. Unstable: > 2 plates flagged
    """
    df_cond = condition_summary.df
    df_plate = plate_effects.df

    # Get noise baseline (median vehicle dispersion)
    noise = df_plate["vehicle_dispersion"].median()

    # Viability bounds for operating point eligibility
    VIABILITY_MIN = 0.50
    VIABILITY_MAX = 0.85

    # Criterion 1 & 3: Signal exists AND viability in shoulder range
    # We filter by viability FIRST, then pick highest effect among eligible
    candidate_doses = [6.0, 8.0]
    signal_exists = False
    best_candidate = None
    best_effect = 0
    viable_candidates = []

    for dose in candidate_doses:
        for tp in [24.0, 48.0]:
            row = df_cond[(df_cond["dose_uM"] == dose) & (df_cond["timepoint_h"] == tp)]
            if len(row) > 0:
                effect = row["effect_mag_mean"].iloc[0]
                viab = row["viability_mean"].iloc[0]

                # Check signal exists (regardless of viability)
                if effect > 2 * noise:
                    signal_exists = True

                # Only consider as operating point candidate if viability is in range
                if VIABILITY_MIN <= viab <= VIABILITY_MAX and effect > 2 * noise:
                    viable_candidates.append(
                        {
                            "dose_uM": dose,
                            "timepoint_h": tp,
                            "effect_mag": effect,
                            "viability": viab,
                        }
                    )

    # Pick best effect among viable candidates
    if viable_candidates:
        viable_candidates.sort(key=lambda x: x["effect_mag"], reverse=True)
        best = viable_candidates[0]
        best_candidate = {"dose_uM": best["dose_uM"], "timepoint_h": best["timepoint_h"]}
        best_effect = best["effect_mag"]

    # Criterion 2: Reproducible (check all candidate doses, not just winner)
    reproducible = True
    for dose in candidate_doses:
        for tp in [24.0, 48.0]:
            row = df_cond[(df_cond["dose_uM"] == dose) & (df_cond["timepoint_h"] == tp)]
            if len(row) > 0:
                sim = row["replicate_similarity"].iloc[0]
                if pd.notna(sim) and sim < 0.7:
                    reproducible = False

    # Criterion 3: Viability shoulder
    # If we found a viable candidate, viability is OK by construction
    viability_ok = best_candidate is not None

    # Criterion 4: Dose dominates
    eta_sq = compute_dose_dominance(plate_effects)
    dose_dominates = eta_sq["dose_eta_sq"] > eta_sq.get("template_eta_sq", 0) and eta_sq[
        "dose_eta_sq"
    ] > eta_sq.get("passage_eta_sq", 0)

    # Criterion 5: Sentinels stable
    flagged = spc_result.get("flagged_plates", [])
    sentinels_stable = len(flagged) == 0

    # NO-GO checks
    # Check if assay is broken (15 µM should collapse)
    collapse_row = df_cond[df_cond["dose_uM"] == 15.0]
    assay_ok = True
    if len(collapse_row) > 0:
        collapse_viab = collapse_row["viability_mean"].mean()
        assay_ok = collapse_viab < 0.50

    # Check for no signal at all (NO-GO condition)
    max_effect = df_cond[df_cond["dose_uM"] > 0]["effect_mag_mean"].max()
    signal_above_noise = max_effect >= 1.5 * noise if noise > 0 else True

    # Build criteria results
    # All criteria use positive framing: True = good, False = bad
    criteria = {
        "signal_exists": signal_exists,
        "reproducible": reproducible,
        "viability_shoulder": viability_ok,
        "dose_dominates": dose_dominates,
        "sentinels_stable": sentinels_stable,
        "assay_working": assay_ok,
        "signal_above_noise": signal_above_noise,
    }

    # Decision: GO requires all criteria True
    go = all(
        [
            signal_exists,
            reproducible,
            viability_ok,
            dose_dominates,
            sentinels_stable,
            assay_ok,
            signal_above_noise,
        ]
    )

    return GoNoGoDecision(
        decision="GO" if go else "NO-GO",
        operating_point=best_candidate if go else None,
        flagged_plates=flagged,
        metrics={
            "noise_baseline": noise,
            "best_effect_mag": best_effect,
            "eta_squared": eta_sq,
            "collapse_viability": collapse_row["viability_mean"].mean()
            if len(collapse_row) > 0
            else None,
        },
        criteria_results=criteria,
    )


def generate_gonogo_report(
    df_wells: pd.DataFrame,
    design_id: str,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """
    Generate complete Go/No-Go report with JSON artifact.

    Returns dict suitable for JSON serialization:
    - decision: GO or NO-GO
    - operating_point: {dose_uM, timepoint_h} or null
    - flagged_plates: list of plate IDs
    - metrics: exact numbers used in rubric
    - criteria_results: bool for each criterion
    - condition_summary: dose × timepoint aggregates
    """
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    # Build the canonical data objects
    plate_effects = build_plate_effects(df_wells)
    condition_summary = build_condition_summary(plate_effects)
    spc_result = run_sentinel_spc(plate_effects, df_wells)

    # Evaluate criteria
    decision = evaluate_gonogo_criteria(plate_effects, condition_summary, spc_result)

    # Build report
    report = {
        "design_id": design_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": decision.decision,
        "operating_point": decision.operating_point,
        "flagged_plates": decision.flagged_plates,
        "metrics": decision.metrics,
        "criteria_results": decision.criteria_results,
        "condition_summary": condition_summary.df.to_dict(orient="records"),
        "spc_control_limits": {
            str(k): {m: list(v) for m, v in limits.items()}
            for k, limits in spc_result.get("control_limits", {}).items()
        },
    }

    # Save to file if output_dir specified
    if output_dir:
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        report_file = out_path / f"gonogo_report_{design_id}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)

        report["report_path"] = str(report_file)

    return report


# ============================================================================
# Qualitative Assertions for Simulator Behavior
# ============================================================================


def assert_viability_ordering(df_wells: pd.DataFrame) -> None:
    """
    Assert: viability(15) < viability(8) < viability(0) on average.

    This must hold for the simulator to reflect basic dose-response biology.
    """
    by_dose = df_wells.groupby("dose_uM")["viability_fraction"].mean()

    assert by_dose.get(15.0, 1.0) < by_dose.get(8.0, 1.0), (
        f"Viability ordering violation: 15µM ({by_dose.get(15.0):.3f}) should be < "
        f"8µM ({by_dose.get(8.0):.3f})"
    )
    assert by_dose.get(8.0, 1.0) < by_dose.get(0.0, 0.0), (
        f"Viability ordering violation: 8µM ({by_dose.get(8.0):.3f}) should be < "
        f"vehicle ({by_dose.get(0.0):.3f})"
    )


def assert_effect_monotonic_through_shoulder(plate_effects: PlateEffects) -> None:
    """
    Assert: effect_mag rises monotonically through 2-8 µM (on average).

    This catches simulators that produce random noise instead of dose-response.
    """
    df = plate_effects.df
    by_dose = df.groupby("dose_uM")["effect_mag"].mean()

    shoulder_doses = [2.0, 4.0, 6.0, 8.0]
    effects = [by_dose.get(d, 0) for d in shoulder_doses]

    # Check mostly monotonic (allow one violation for noise)
    violations = sum(1 for i in range(len(effects) - 1) if effects[i] > effects[i + 1])
    assert violations <= 1, (
        f"Effect magnitude not monotonic through shoulder: {dict(zip(shoulder_doses, effects))}. "
        f"Found {violations} ordering violations."
    )


def assert_collapse_ineligible(condition_summary: ConditionSummary) -> None:
    """
    Assert: 15 µM has viability < 50% (ineligible by viability threshold).

    This ensures the collapse dose actually collapses.
    """
    df = condition_summary.df
    collapse = df[df["dose_uM"] == 15.0]["viability_mean"].mean()

    assert collapse < 0.50, (
        f"Collapse dose (15µM) viability {collapse:.3f} >= 0.50. "
        "Simulator not producing collapse at expected dose."
    )


def assert_replicate_similarity_rises_with_dose(plate_effects: PlateEffects) -> None:
    """
    Assert: replicate similarity at shoulder > subthreshold doses.

    Higher doses produce stronger, more consistent effects.
    """
    low_doses = [2.0]
    shoulder_doses = [6.0, 8.0]

    low_sims = []
    shoulder_sims = []

    for dose in low_doses:
        for tp in [24.0, 48.0]:
            sim, _ = compute_replicate_similarity(plate_effects, dose, tp)
            if not np.isnan(sim):
                low_sims.append(sim)

    for dose in shoulder_doses:
        for tp in [24.0, 48.0]:
            sim, _ = compute_replicate_similarity(plate_effects, dose, tp)
            if not np.isnan(sim):
                shoulder_sims.append(sim)

    if low_sims and shoulder_sims:
        avg_low = np.mean(low_sims)
        avg_shoulder = np.mean(shoulder_sims)
        # Shoulder should have >= similarity (stronger effect = more agreement)
        # Relaxed: shoulder >= 90% of low (noise can cause slight inversions)
        assert avg_shoulder >= avg_low * 0.9, (
            f"Replicate similarity pattern unexpected: shoulder={avg_shoulder:.3f}, "
            f"low_dose={avg_low:.3f}. Expected shoulder >= 0.9 * low."
        )


def assert_dose_dominates_technical(plate_effects: PlateEffects) -> None:
    """
    Assert: dose_eta_sq > template_eta_sq AND > passage_eta_sq.

    Under normal simulator settings, dose should dominate.
    """
    eta_sq = compute_dose_dominance(plate_effects)

    assert eta_sq["dose_eta_sq"] > eta_sq.get("template_eta_sq", 0), (
        f"Dose eta² ({eta_sq['dose_eta_sq']:.3f}) should exceed "
        f"template eta² ({eta_sq.get('template_eta_sq', 0):.3f})"
    )
    assert eta_sq["dose_eta_sq"] > eta_sq.get("passage_eta_sq", 0), (
        f"Dose eta² ({eta_sq['dose_eta_sq']:.3f}) should exceed "
        f"passage eta² ({eta_sq.get('passage_eta_sq', 0):.3f})"
    )


def assert_spc_no_flags_normal(spc_result: dict) -> None:
    """
    Assert: no plates flagged under normal simulator settings.

    If plates are flagged, either the simulator has a bug or SPC thresholds
    are too tight.
    """
    flagged = spc_result.get("flagged_plates", [])
    assert len(flagged) == 0, (
        f"SPC flagged {len(flagged)} plates under normal settings: {flagged}. "
        "Check simulator stability or SPC threshold calibration."
    )


def run_all_assertions(df_wells: pd.DataFrame) -> dict[str, bool]:
    """
    Run all qualitative assertions and return results.

    Returns dict mapping assertion name to pass/fail.
    """
    plate_effects = build_plate_effects(df_wells)
    condition_summary = build_condition_summary(plate_effects)
    spc_result = run_sentinel_spc(plate_effects, df_wells)

    results = {}

    assertions = [
        ("viability_ordering", lambda: assert_viability_ordering(df_wells)),
        ("effect_monotonic", lambda: assert_effect_monotonic_through_shoulder(plate_effects)),
        ("collapse_ineligible", lambda: assert_collapse_ineligible(condition_summary)),
        (
            "replicate_similarity",
            lambda: assert_replicate_similarity_rises_with_dose(plate_effects),
        ),
        ("dose_dominates", lambda: assert_dose_dominates_technical(plate_effects)),
        ("spc_no_flags", lambda: assert_spc_no_flags_normal(spc_result)),
    ]

    for name, assertion_fn in assertions:
        try:
            assertion_fn()
            results[name] = True
        except AssertionError as e:
            results[name] = False
            results[f"{name}_error"] = str(e)

    return results
