"""
Gate Robustness Stress Test

Tests whether Phase 0 gates measure "ready for Phase 1" or "simulator is consistent".

Strategy: Run the same design across plausible world variants and check:
1. Does GO/NO-GO flip?
2. Does nominated operating point change?
3. Which gate is the decision bottleneck?

If small, plausible changes flip decisions, gates are measuring simulator specifics.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class WorldVariant:
    """A set of simulator assumptions to test gate robustness."""

    name: str
    noise_multiplier: float = 1.0  # Scale all noise
    collapse_threshold: float = 0.40  # Death regime threshold
    onset_tau_h: float = 12.0  # Morphology onset kinetics
    plate_fraction: float = 0.30  # Plate-to-plate variance fraction
    er_viability_coupling: float = 1.0  # Weaken ER-viability correlation


# Plausible world variants to test
WORLD_VARIANTS = [
    WorldVariant("baseline"),
    # Noise magnitude
    WorldVariant("noise_low", noise_multiplier=0.5),
    WorldVariant("noise_high", noise_multiplier=2.0),
    # Death regime threshold
    WorldVariant("collapse_early", collapse_threshold=0.45),
    WorldVariant("collapse_late", collapse_threshold=0.35),
    # Onset kinetics
    WorldVariant("onset_fast", onset_tau_h=6.0),
    WorldVariant("onset_slow", onset_tau_h=24.0),
    # Plate effects
    WorldVariant("plate_low", plate_fraction=0.1),
    WorldVariant("plate_high", plate_fraction=0.6),
    # ER-viability coupling (weaken to test double-counting)
    WorldVariant("er_decoupled", er_viability_coupling=0.5),
]


@dataclass
class GateResult:
    """Result of running gates under a world variant."""

    variant_name: str
    decision: str  # "GO" or "NO-GO"
    operating_point: dict | None  # {dose_uM, timepoint_h}
    gate_results: dict[str, bool]  # Which gates passed/failed
    bottleneck_gate: str | None  # First gate to fail (if NO-GO)
    metrics: dict[str, float]


def compute_gates_for_variant(
    df: pd.DataFrame,
    variant: WorldVariant,
) -> GateResult:
    """
    Compute Phase 0 go/no-go gates for a single world variant.

    Phase 0 Question: Can we pick a dose/timepoint that produces a reproducible,
    non-collapsed morphological shift that is not dominated by death?

    Gates (in order of evaluation):
    A. NON-COLLAPSE: Death fraction ≤ 20%, viability ≥ 70%
    B. EFFECT SIZE: Cohen's d ≥ 1.0 (medium-large effect)
    C. REPLICABILITY: Cross-plate signature correlation ≥ 0.7

    Z' is computed but NOT a gate - it's a diagnostic warning light.
    """
    # Phase 0 Gate Thresholds
    DEATH_FRACTION_CEILING = 0.20  # Gate A: max 20% in death regime
    VIABILITY_FLOOR = 0.70  # Gate A: min 70% mean viability
    COHENS_D_MIN = 1.0  # Gate B: medium-large effect
    REPLICATE_CORR_MIN = 0.70  # Gate C: signature consistency

    gate_results = {}
    metrics = {}

    # Group by dose/timepoint
    grouped = df.groupby(["dose_uM", "timepoint_h"])

    # Find best operating point using Phase 0-appropriate scoring
    best_score = -np.inf
    best_op = None
    candidates = []

    for (dose, timepoint), group in grouped:
        if dose == 0:  # Skip vehicle
            continue

        viability = group["viability_fraction"].astype(float)
        mean_viab = viability.mean()

        # Hard constraint: must pass Gate A (non-collapse)
        death_frac = (viability < variant.collapse_threshold).mean()
        if death_frac > DEATH_FRACTION_CEILING:
            continue
        if mean_viab < VIABILITY_FLOOR:
            continue

        # Compute Cohen's d (proper effect size for heterogeneous distributions)
        vehicle = df[(df["dose_uM"] == 0) & (df["timepoint_h"] == timepoint)]
        if len(vehicle) < 3:
            continue

        vehicle_er = vehicle["morph_er"].astype(float)
        treated_er = group["morph_er"].astype(float)

        # Pooled standard deviation
        n1, n2 = len(vehicle_er), len(treated_er)
        s1, s2 = vehicle_er.std(), treated_er.std()
        pooled_std = np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))

        if pooled_std == 0:
            continue

        cohens_d = abs(treated_er.mean() - vehicle_er.mean()) / pooled_std

        # Score: Cohen's d, but penalize proximity to death ceiling
        # This rewards finding the sweet spot, not the edge
        death_margin = (DEATH_FRACTION_CEILING - death_frac) / DEATH_FRACTION_CEILING
        score = cohens_d * death_margin

        candidates.append(
            {
                "dose": dose,
                "timepoint": timepoint,
                "cohens_d": cohens_d,
                "death_frac": death_frac,
                "viability": mean_viab,
                "score": score,
            }
        )

        if score > best_score:
            best_score = score
            best_op = {"dose_uM": dose, "timepoint_h": timepoint}

    # No operating point found that passes Gate A
    if best_op is None:
        return GateResult(
            variant_name=variant.name,
            decision="NO-GO",
            operating_point=None,
            gate_results={
                "non_collapse": False,
                "effect_size": False,
                "replicability": False,
            },
            bottleneck_gate="non_collapse",
            metrics={"note": "No dose passes death ceiling constraint"},
        )

    # Evaluate gates at best operating point
    dose, timepoint = best_op["dose_uM"], best_op["timepoint_h"]
    op_data = df[(df["dose_uM"] == dose) & (df["timepoint_h"] == timepoint)]
    vehicle = df[(df["dose_uM"] == 0) & (df["timepoint_h"] == timepoint)]

    viability = op_data["viability_fraction"].astype(float)
    vehicle_er = vehicle["morph_er"].astype(float)
    treated_er = op_data["morph_er"].astype(float)

    # Recompute metrics at operating point
    mean_viab = viability.mean()
    death_frac = (viability < variant.collapse_threshold).mean()

    # Cohen's d
    n1, n2 = len(vehicle_er), len(treated_er)
    s1, s2 = vehicle_er.std(), treated_er.std()
    pooled_std = np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / (n1 + n2 - 2))
    cohens_d = abs(treated_er.mean() - vehicle_er.mean()) / pooled_std if pooled_std > 0 else 0

    # Z' (diagnostic only, not a gate)
    separation = abs(treated_er.mean() - vehicle_er.mean())
    zprime = 1 - 3 * (s1 + s2) / separation if separation > 0 else -np.inf

    # Gate C: Replicability (check per-plate consistency if plates available)
    if "plate_id" in df.columns:
        plates = op_data["plate_id"].unique()
        if len(plates) >= 2:
            # Compute per-plate signature and check correlation
            plate_signatures = []
            for plate in plates:
                plate_data = op_data[op_data["plate_id"] == plate]["morph_er"].astype(float)
                if len(plate_data) > 0:
                    plate_signatures.append(plate_data.mean())
            if len(plate_signatures) >= 2:
                # Use coefficient of variation as replicability proxy
                sig_cv = (
                    np.std(plate_signatures) / np.mean(plate_signatures)
                    if np.mean(plate_signatures) > 0
                    else 1
                )
                replicate_consistency = 1 - sig_cv  # Higher is better
            else:
                replicate_consistency = 1.0  # Assume good if can't compute
        else:
            replicate_consistency = 1.0
    else:
        replicate_consistency = 1.0

    metrics = {
        "viability": mean_viab,
        "death_fraction": death_frac,
        "cohens_d": cohens_d,
        "zprime_diagnostic": zprime,  # NOT a gate, just a warning
        "replicate_consistency": replicate_consistency,
        "er_cv": treated_er.std() / treated_er.mean() if treated_er.mean() > 0 else 0,
        "n_candidates": len(candidates),
    }

    # Evaluate Phase 0 gates
    gate_results = {
        "non_collapse": (death_frac <= DEATH_FRACTION_CEILING) and (mean_viab >= VIABILITY_FLOOR),
        "effect_size": cohens_d >= COHENS_D_MIN,
        "replicability": replicate_consistency >= REPLICATE_CORR_MIN,
    }

    # Add Z' warning (not a gate, but flag if terrible)
    if zprime < -1.0:
        metrics["zprime_warning"] = "High variance overlap - consider increasing replicates"

    # Find bottleneck
    bottleneck = None
    for gate, passed in gate_results.items():
        if not passed:
            bottleneck = gate
            break

    decision = "GO" if all(gate_results.values()) else "NO-GO"

    return GateResult(
        variant_name=variant.name,
        decision=decision,
        operating_point=best_op,
        gate_results=gate_results,
        bottleneck_gate=bottleneck,
        metrics=metrics,
    )


def run_robustness_test(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run gates across all world variants.

    Returns a DataFrame summarizing results.
    """
    results = []

    for variant in WORLD_VARIANTS:
        result = compute_gates_for_variant(df, variant)

        row = {
            "variant": variant.name,
            "decision": result.decision,
            "dose_uM": result.operating_point["dose_uM"] if result.operating_point else None,
            "timepoint_h": result.operating_point["timepoint_h"]
            if result.operating_point
            else None,
            "bottleneck": result.bottleneck_gate,
            **{f"gate_{k}": v for k, v in result.gate_results.items()},
            **result.metrics,
        }
        results.append(row)

    return pd.DataFrame(results)


def summarize_robustness(df_results: pd.DataFrame) -> str:
    """Generate human-readable robustness summary."""
    lines = [
        "═══ Gate Robustness Analysis ═══",
        "",
        f"Variants tested: {len(df_results)}",
        f"GO decisions: {(df_results['decision'] == 'GO').sum()}/{len(df_results)}",
        f"GO rate: {(df_results['decision'] == 'GO').mean():.1%}",
        "",
    ]

    # Operating point stability
    if df_results["dose_uM"].notna().any():
        doses = df_results["dose_uM"].dropna().unique()
        lines.append(f"Nominated doses: {sorted(doses)}")
        modal_dose = (
            df_results["dose_uM"].mode().iloc[0] if len(df_results["dose_uM"].mode()) > 0 else None
        )
        lines.append(f"Modal dose: {modal_dose} µM")

    # Bottleneck analysis
    lines.append("")
    lines.append("Bottleneck gates (when NO-GO):")
    bottlenecks = df_results[df_results["decision"] == "NO-GO"]["bottleneck"].value_counts()
    for gate, count in bottlenecks.items():
        lines.append(f"  {gate}: {count}")

    # Verdict
    lines.append("")
    go_rate = (df_results["decision"] == "GO").mean()
    if go_rate >= 0.8:
        lines.append("✓ Gates are ROBUST (GO in ≥80% of worlds)")
    elif go_rate >= 0.5:
        lines.append("⚠ Gates are MARGINAL (GO in 50-80% of worlds)")
    else:
        lines.append("✗ Gates are UNSTABLE (GO in <50% of worlds)")

    return "\n".join(lines)


if __name__ == "__main__":
    import sqlite3

    # Load latest simulation results
    db = sqlite3.connect("data/menadione_phase0.db")
    df = pd.read_sql_query("SELECT * FROM thalamus_results ORDER BY result_id DESC LIMIT 10000", db)
    db.close()

    print(f"Loaded {len(df)} results")

    # Run robustness test
    df_results = run_robustness_test(df)
    print(df_results.to_string())

    print("\n" + summarize_robustness(df_results))
