"""
Test mechanism-conditional calibration bias.

Run 3 compounds (MT, ER, mito), extract weak-posterior belief states,
check if calibrator boosts are mechanism-invariant.

This is the killer test for calibration shortcuts.
"""

import logging
import numpy as np
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict
import pickle

from src.cell_os.hardware.beam_search import Phase5EpisodeRunner, BeamSearch
from src.cell_os.hardware.masked_compound_phase5 import PHASE5_LIBRARY
from src.cell_os.hardware.episode import Action

logging.basicConfig(level=logging.WARNING)  # Suppress VM spam
logger = logging.getLogger(__name__)


@dataclass
class BeliefStateRecord:
    """Captured belief state for analysis."""
    compound_id: str
    true_mechanism: str
    seed: int
    timestep: int
    time_h: float

    # Posterior
    predicted_axis: str
    posterior_top_prob: float
    posterior_margin: float

    # Nuisance
    nuisance_frac: float
    nuisance_mean_shift_mag: float
    nuisance_var_inflation: float

    # Calibration
    calibrated_conf: float

    # Ground truth (for accuracy check)
    is_correct: bool


def run_compound_exploration(compound_id: str, n_seeds: int = 20) -> List[BeliefStateRecord]:
    """
    Run beam search for compound and extract belief states.

    Focus: Capture states at multiple timesteps to get geometry diversity.
    """
    phase5_compound = PHASE5_LIBRARY[compound_id]
    true_mechanism = phase5_compound.true_stress_axis

    records = []

    for seed in range(n_seeds):
        logger.info(f"Running {compound_id} seed {seed}")

        # Create runner
        runner = Phase5EpisodeRunner(
            phase5_compound=phase5_compound,
            cell_line="A549",
            horizon_h=48.0,
            step_h=6.0,
            seed=seed,
            lambda_dead=2.0,
            lambda_ops=0.1,
            actin_threshold=1.4
        )

        # Create beam search with small beam (fast exploration)
        beam_search = BeamSearch(
            runner=runner,
            beam_width=3,  # Small for speed
            max_interventions=2,
            death_tolerance=0.20,
            w_mechanism=2.0,
            w_viability=0.5,
            w_interventions=0.1
        )

        # Disable COMMIT logging for speed
        beam_search.debug_commit_decisions = False

        # Manually explore timesteps to gather belief states
        # Instead of full beam search, just sample representative schedules
        test_schedules = [
            [],  # Baseline
            [Action(dose_fraction=0.25, washout=False, feed=False)],  # Low dose
            [Action(dose_fraction=0.5, washout=False, feed=False)],   # Mid dose
            [Action(dose_fraction=1.0, washout=False, feed=False)],   # High dose
        ]

        for schedule in test_schedules:
            if len(schedule) == 0:
                continue  # Skip baseline

            try:
                # Run prefix rollout to get belief state
                prefix_result = runner.rollout_prefix(schedule)

                timestep = len(schedule)
                time_h = timestep * runner.step_h

                # Check if correct
                predicted_mechanism = prefix_result.predicted_axis
                is_correct = (predicted_mechanism == true_mechanism)

                # Store record
                record = BeliefStateRecord(
                    compound_id=compound_id,
                    true_mechanism=true_mechanism,
                    seed=seed,
                    timestep=timestep,
                    time_h=time_h,
                    predicted_axis=predicted_mechanism,
                    posterior_top_prob=prefix_result.posterior_top_prob,
                    posterior_margin=prefix_result.posterior_margin,
                    nuisance_frac=prefix_result.nuisance_fraction,
                    nuisance_mean_shift_mag=prefix_result.nuisance_mean_shift_mag,
                    nuisance_var_inflation=prefix_result.nuisance_var_inflation,
                    calibrated_conf=prefix_result.calibrated_confidence,
                    is_correct=is_correct
                )

                records.append(record)

            except Exception as e:
                logger.warning(f"Failed rollout for {compound_id} seed {seed} schedule {schedule}: {e}")
                continue

    return records


def analyze_mechanism_bias(records: List[BeliefStateRecord]):
    """
    Check if calibrator boosts are mechanism-invariant.

    Filter to weak-posterior slice and compare distributions.
    """

    # PRE-FILTER DIAGNOSTICS
    print("\n" + "=" * 80)
    print("PRE-FILTER DIAGNOSTICS (All Records)")
    print("=" * 80)

    by_compound = defaultdict(list)
    for r in records:
        by_compound[r.compound_id].append(r)

    for cid, recs in sorted(by_compound.items()):
        post_probs = [r.posterior_top_prob for r in recs]
        nuisance_fracs = [r.nuisance_frac for r in recs]
        concrete = [r for r in recs if r.predicted_axis != "unknown"]

        print(f"\n{cid} (n={len(recs)}):")
        print(f"  posterior_top_prob: mean={np.mean(post_probs):.3f}, range=[{min(post_probs):.3f}, {max(post_probs):.3f}]")
        print(f"  nuisance_frac: mean={np.mean(nuisance_fracs):.3f}, range=[{min(nuisance_fracs):.3f}, {max(nuisance_fracs):.3f}]")
        print(f"  Concrete predictions: {len(concrete)}/{len(recs)} ({100*len(concrete)/len(recs):.1f}%)")
        print(f"  In slice [0.35, 0.50] posterior, [0.4, 0.6] nuisance: {sum(1 for r in concrete if 0.35 <= r.posterior_top_prob <= 0.50 and 0.4 <= r.nuisance_frac <= 0.6)}")

    # Filter to target geometry slice
    weak_posterior_slice = [
        r for r in records
        if 0.35 <= r.posterior_top_prob <= 0.50
        and 0.4 <= r.nuisance_frac <= 0.6
        and r.predicted_axis != "unknown"  # Concrete mechanisms only
    ]

    logger.info(f"\nWeak-posterior slice: {len(weak_posterior_slice)} records")
    logger.info(f"  posterior_top_prob: [0.35, 0.50]")
    logger.info(f"  nuisance_frac: [0.4, 0.6]")
    logger.info(f"  predicted_axis: concrete mechanisms only")

    # Group by predicted mechanism
    by_mechanism = defaultdict(list)
    for r in weak_posterior_slice:
        by_mechanism[r.predicted_axis].append(r)

    print("\n" + "=" * 80)
    print("MECHANISM-CONDITIONAL CALIBRATION ANALYSIS")
    print("=" * 80)

    # Summary per mechanism
    results = {}
    for mech, recs in sorted(by_mechanism.items()):
        cal_confs = [r.calibrated_conf for r in recs]
        post_probs = [r.posterior_top_prob for r in recs]
        boosts = [r.calibrated_conf - r.posterior_top_prob for r in recs]
        accuracies = [r.is_correct for r in recs]

        mean_cal = np.mean(cal_confs)
        std_cal = np.std(cal_confs)
        mean_post = np.mean(post_probs)
        mean_boost = np.mean(boosts)
        accuracy = np.mean(accuracies)
        count = len(recs)

        # Underlying feature distributions in slice
        margins = [r.posterior_margin for r in recs]
        nuisance_fracs = [r.nuisance_frac for r in recs]
        mean_shifts = [r.nuisance_mean_shift_mag for r in recs]
        var_inflations = [r.nuisance_var_inflation for r in recs]

        results[mech] = {
            'count': count,
            'mean_posterior': mean_post,
            'mean_calibrated': mean_cal,
            'std_calibrated': std_cal,
            'mean_boost': mean_boost,
            'accuracy': accuracy,
            'mean_margin': np.mean(margins),
            'mean_nuisance_frac': np.mean(nuisance_fracs),
            'mean_mean_shift_mag': np.mean(mean_shifts),
            'mean_var_inflation': np.mean(var_inflations)
        }

        print(f"\n{mech.upper()}:")
        print(f"  Count: {count}")
        print(f"  Mean posterior_top_prob: {mean_post:.3f}")
        print(f"  Mean calibrated_conf: {mean_cal:.3f} ± {std_cal:.3f}")
        print(f"  Mean boost: {mean_boost:.3f}")
        print(f"  Empirical accuracy: {accuracy:.3f}")
        print(f"  Slice geometry:")
        print(f"    Mean margin: {np.mean(margins):.3f}")
        print(f"    Mean nuisance_frac: {np.mean(nuisance_fracs):.3f}")
        print(f"    Mean mean_shift_mag: {np.mean(mean_shifts):.4f}")
        print(f"    Mean var_inflation: {np.mean(var_inflations):.4f}")

    # Check sample sizes
    print("\n" + "=" * 80)
    print("SAMPLE SIZE CHECK")
    print("=" * 80)

    counts = [results[m]['count'] for m in results.keys()]
    min_count = min(counts)
    max_count = max(counts)
    ratio = max_count / max(min_count, 1)

    print(f"Min count: {min_count}")
    print(f"Max count: {max_count}")
    print(f"Ratio: {ratio:.2f}x")

    if ratio > 3.0:
        print(f"\n⚠️  WARNING: Sample sizes unbalanced (ratio {ratio:.1f}x)")
        print(f"   Statistics may be unreliable")
        print(f"   Consider widening slice or downsampling")

    # Check for bias
    print("\n" + "=" * 80)
    print("BIAS CHECK")
    print("=" * 80)

    if len(results) < 2:
        print("WARNING: Need at least 2 mechanisms in slice for comparison")
        return

    mechs = list(results.keys())
    cal_means = [results[m]['mean_calibrated'] for m in mechs]
    cal_stds = [results[m]['std_calibrated'] for m in mechs]
    counts = [results[m]['count'] for m in mechs]

    max_mech = mechs[np.argmax(cal_means)]
    min_mech = mechs[np.argmin(cal_means)]

    diff = max(cal_means) - min(cal_means)

    print(f"\nMax calibrated_conf: {max_mech} ({max(cal_means):.3f})")
    print(f"Min calibrated_conf: {min_mech} ({min(cal_means):.3f})")
    print(f"Difference: {diff:.3f}")

    if diff > 0.10:
        print(f"\n⚠️  WARNING: Calibrator appears MECHANISM-BIASED")
        print(f"   Difference {diff:.3f} > 0.10 threshold")
        print(f"   {max_mech} is favored over {min_mech}")

        # Check if accuracy justifies the bias
        max_acc = results[max_mech]['accuracy']
        min_acc = results[min_mech]['accuracy']
        acc_diff = max_acc - min_acc

        if acc_diff > 0.10:
            print(f"\n   BUT: Accuracy difference is {acc_diff:.3f}")
            print(f"        {max_mech} is actually easier to identify")
            print(f"        Bias may be justified")
        else:
            print(f"\n   AND: Accuracy difference is only {acc_diff:.3f}")
            print(f"        Calibrator is overconfident on {max_mech} without justification")
            print(f"        This is a SHORTCUT LEARNED FROM TRAINING DATA")
    else:
        print(f"\n✓ PASS: Calibrator appears MECHANISM-INVARIANT")
        print(f"  Difference {diff:.3f} ≤ 0.10 threshold")
        print(f"  Boost is geometry-dependent, not mechanism-dependent")

    # Overconfidence check per mechanism
    print("\n" + "=" * 80)
    print("OVERCONFIDENCE CHECK")
    print("=" * 80)

    for mech, recs in sorted(by_mechanism.items()):
        print(f"\n{mech.upper()}:")

        # Bin by calibrated_conf
        bins = [(0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]
        for low, high in bins:
            bin_recs = [r for r in recs if low <= r.calibrated_conf < high]
            if len(bin_recs) == 0:
                continue

            mean_cal = np.mean([r.calibrated_conf for r in bin_recs])
            accuracy = np.mean([r.is_correct for r in bin_recs])
            count = len(bin_recs)

            diff = mean_cal - accuracy

            status = "✓" if abs(diff) < 0.15 else "⚠️"

            print(f"  [{low:.1f}, {high:.1f}): n={count:3d}  cal_conf={mean_cal:.3f}  accuracy={accuracy:.3f}  diff={diff:+.3f} {status}")

    # Save results
    with open('/tmp/mechanism_conditional_results.pkl', 'wb') as f:
        pickle.dump({
            'records': weak_posterior_slice,
            'by_mechanism': dict(by_mechanism),
            'summary': results
        }, f)

    print(f"\nResults saved to /tmp/mechanism_conditional_results.pkl")


def main():
    """Run 60-seed mechanism-conditional test."""

    print("=" * 80)
    print("MECHANISM-CONDITIONAL CALIBRATION TEST")
    print("=" * 80)
    print("\nRunning 3 compounds × 20 seeds = 60 runs")
    print("Extracting belief states at multiple timesteps")
    print("Target slice: posterior ∈ [0.35, 0.50], nuisance ∈ [0.4, 0.6]")
    print("\nThis will take ~30-60 minutes with VM rollouts...")
    print("=" * 80)

    # Compounds (one per mechanism)
    compounds = {
        'test_C_clean': 'microtubule',  # paclitaxel
        'test_A_clean': 'er_stress',     # tunicamycin
        'test_B_clean': 'mitochondrial'  # cccp
    }

    all_records = []

    for compound_id, true_mech in compounds.items():
        print(f"\n### Running {compound_id} ({true_mech}) ###")
        records = run_compound_exploration(compound_id, n_seeds=20)
        all_records.extend(records)
        print(f"Collected {len(records)} belief states")

    print(f"\n\nTotal belief states collected: {len(all_records)}")

    # Analyze
    analyze_mechanism_bias(all_records)


if __name__ == "__main__":
    main()
