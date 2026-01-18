"""
Fine Grid 48h Analysis - Phase 0 Operating Point Search

Runs fine dose grid at 48h to test if longer exposure creates a usable shoulder.
Computes both raw Cohen's d and viability-residualized Cohen's d.

Usage:
    python fine_grid_48h_analysis.py
"""

from dataclasses import dataclass

import numpy as np

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


@dataclass
class DoseStats:
    dose_uM: float
    timepoint_h: float
    n_wells: int
    viab_mean: float
    viab_std: float
    death_pct: float
    er_mean: float
    er_std: float
    er_cv: float
    cohens_d_raw: float
    cohens_d_resid: float  # ER residualized against viability


def run_fine_grid(timepoint_h: float, n_reps: int = 30, seed: int = 42) -> list[DoseStats]:
    """Run fine dose grid simulation at specified timepoint."""

    # Fine grid doses (shoulder region + anchors)
    doses = [0.0, 2.0, 4.0, 4.5, 5.0, 5.5, 6.0, 8.0]

    results_by_dose = {d: {"viab": [], "er": []} for d in doses}

    for rep in range(n_reps):
        vm = BiologicalVirtualMachine(seed=seed + rep, simulation_speed=0)

        for dose in doses:
            vessel_id = f"well_{dose}_{rep}"
            vm.seed_vessel(vessel_id, "A549", initial_count=2000, vessel_type="384-well")
            vm.advance_time(24.0)  # Attachment
            vm.feed_vessel(vessel_id)

            if dose > 0:
                vm.treat_with_compound(vessel_id, "menadione", dose)

            vm.advance_time(timepoint_h)

            vessel = vm.vessel_states[vessel_id]
            result = vm.cell_painting_assay(vessel_id)

            results_by_dose[dose]["viab"].append(vessel.viability)
            results_by_dose[dose]["er"].append(result["morphology"]["er"])

    # Compute stats
    vehicle_er = np.array(results_by_dose[0.0]["er"])
    vehicle_viab = np.array(results_by_dose[0.0]["viab"])

    # For residualization: fit linear regression of ER on viability using ALL data
    all_viab = []
    all_er = []
    for dose in doses:
        all_viab.extend(results_by_dose[dose]["viab"])
        all_er.extend(results_by_dose[dose]["er"])
    all_viab = np.array(all_viab)
    all_er = np.array(all_er)

    # Simple linear regression: ER = a + b * viab
    slope, intercept = np.polyfit(all_viab, all_er, 1)

    stats = []
    for dose in doses:
        viab = np.array(results_by_dose[dose]["viab"])
        er = np.array(results_by_dose[dose]["er"])

        # Raw Cohen's d (ER vs vehicle)
        pooled_std = np.sqrt(
            ((len(vehicle_er) - 1) * vehicle_er.std() ** 2 + (len(er) - 1) * er.std() ** 2)
            / (len(vehicle_er) + len(er) - 2)
        )
        cohens_d_raw = abs(er.mean() - vehicle_er.mean()) / pooled_std if pooled_std > 0 else 0

        # Residualized Cohen's d (remove viability contribution)
        er_resid = er - (slope * viab + intercept)
        vehicle_er_resid = vehicle_er - (slope * vehicle_viab + intercept)

        pooled_std_resid = np.sqrt(
            (
                (len(vehicle_er_resid) - 1) * vehicle_er_resid.std() ** 2
                + (len(er_resid) - 1) * er_resid.std() ** 2
            )
            / (len(vehicle_er_resid) + len(er_resid) - 2)
        )
        cohens_d_resid = (
            abs(er_resid.mean() - vehicle_er_resid.mean()) / pooled_std_resid
            if pooled_std_resid > 0
            else 0
        )

        # Death fraction (viability < 0.4)
        death_pct = (viab < 0.4).mean() * 100

        stats.append(
            DoseStats(
                dose_uM=dose,
                timepoint_h=timepoint_h,
                n_wells=len(viab),
                viab_mean=viab.mean(),
                viab_std=viab.std(),
                death_pct=death_pct,
                er_mean=er.mean(),
                er_std=er.std(),
                er_cv=er.std() / er.mean() if er.mean() > 0 else 0,
                cohens_d_raw=cohens_d_raw,
                cohens_d_resid=cohens_d_resid,
            )
        )

    return stats, slope, intercept


def print_table(stats: list[DoseStats], slope: float, intercept: float):
    """Print results table."""
    print(
        f"\n{'Dose':>6} {'Viab':>6} {'±':>5} {'Death%':>7} {'ER_mean':>8} {'ER_CV':>6} {'d_raw':>6} {'d_resid':>8}"
    )
    print("-" * 60)
    for s in stats:
        print(
            f"{s.dose_uM:>6.1f} {s.viab_mean:>6.2f} {s.viab_std:>5.2f} {s.death_pct:>6.1f}% {s.er_mean:>8.1f} {s.er_cv:>6.2f} {s.cohens_d_raw:>6.2f} {s.cohens_d_resid:>8.2f}"
        )
    print(f"\nER-Viability regression: ER = {slope:.1f} * viab + {intercept:.1f}")


if __name__ == "__main__":
    print("=" * 60)
    print("FINE DOSE GRID ANALYSIS - 24h vs 48h")
    print("=" * 60)

    print("\n--- 24h Timepoint ---")
    stats_24h, slope_24, int_24 = run_fine_grid(24.0, n_reps=30)
    print_table(stats_24h, slope_24, int_24)

    print("\n--- 48h Timepoint ---")
    stats_48h, slope_48, int_48 = run_fine_grid(48.0, n_reps=30)
    print_table(stats_48h, slope_48, int_48)

    # Gate analysis
    print("\n" + "=" * 60)
    print("GATE ANALYSIS (d_raw ≥ 1.0 AND death% ≤ 20%)")
    print("=" * 60)

    for label, stats in [("24h", stats_24h), ("48h", stats_48h)]:
        passing = [s for s in stats if s.cohens_d_raw >= 1.0 and s.death_pct <= 20]
        if passing:
            print(f"\n{label} PASSING DOSES: {[s.dose_uM for s in passing]}")
            for s in passing:
                print(f"  {s.dose_uM} µM: d={s.cohens_d_raw:.2f}, death={s.death_pct:.1f}%")
        else:
            print(f"\n{label}: NO doses pass both gates")

    # Residualized analysis
    print("\n" + "=" * 60)
    print("RESIDUALIZED ANALYSIS (d_resid ≥ 0.5 AND death% ≤ 20%)")
    print("=" * 60)

    for label, stats in [("24h", stats_24h), ("48h", stats_48h)]:
        passing = [s for s in stats if s.cohens_d_resid >= 0.5 and s.death_pct <= 20]
        if passing:
            print(f"\n{label} PASSING DOSES (residualized): {[s.dose_uM for s in passing]}")
            for s in passing:
                print(f"  {s.dose_uM} µM: d_resid={s.cohens_d_resid:.2f}, death={s.death_pct:.1f}%")
        else:
            print(f"\n{label}: NO doses pass residualized gate")
