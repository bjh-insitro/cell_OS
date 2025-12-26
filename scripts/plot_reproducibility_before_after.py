#!/usr/bin/env PYTHONPATH=/Users/bjh/cell_OS:$PYTHONPATH python3
"""
Reproducibility Visualization: Before vs After Biology Variability Patch

USAGE:
  # Single mode: plot current HEAD
  python scripts/plot_reproducibility_before_after.py

  # Compare mode: compare two git SHAs
  python scripts/plot_reproducibility_before_after.py --mode=compare --before=11fb78f --after=<new_sha>

OUTPUTS:
  Single mode: artifacts/repro_plots/<git_sha>/
  Compare mode: artifacts/repro_plots/compare_<before>_vs_<after>/

FIGURES:
  FIG1: Multi-run viability overlay
  FIG2: Time-to-threshold distributions (KDE + rug) at 0.7/0.5/0.3
  FIG3: Within-run correlation matrix
  FIG4: Washout recovery variability
  FIG5: Variance decomposition (within-run vs between-run)
  FIG6: Correlation structure (within vs across runs)

ANTI-CHEAT GUARDS:
  - Warns if CV increases but within-run correlation stays >0.95 (global jitter)
  - Warns if washout half-life varies but curves identical up to scale (cosmetic)
"""

import sys
import json
import subprocess
import argparse
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

sys.path.insert(0, str(Path(__file__).parents[1]))

from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from src.cell_os.database.repositories.compound_repository import get_compound_ic50


def get_git_sha():
    """Get current git SHA."""
    result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                          capture_output=True, text=True, cwd=Path(__file__).parents[1])
    return result.stdout.strip()


def ensure_output_dir(path):
    """Create output directory."""
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)


def run_multi_run_multi_vessel(n_runs=8, n_vessels=8, cell_line="A549",
                                compound="tunicamycin", dose_multiplier=4.0,
                                treatment_start_h=24.0, total_duration_h=72.0,
                                sample_interval_h=3.0):
    """
    Run K runs × N vessels protocol for variance decomposition.
    Returns: {run_results, metadata}
    """
    ic50_uM = get_compound_ic50(compound, cell_line)
    dose_uM = ic50_uM * dose_multiplier

    run_results = []
    for run_idx in range(n_runs):
        seed = 1000 + run_idx
        vm = BiologicalVirtualMachine(seed=seed)

        vessel_results = []
        for v_idx in range(n_vessels):
            vid = f"v{v_idx:02d}"
            vm.seed_vessel(vid, cell_line, initial_count=1e6)

        # Protocol
        vm.advance_time(treatment_start_h)
        for v_idx in range(n_vessels):
            vid = f"v{v_idx:02d}"
            vm.treat_with_compound(vid, compound, dose_uM=dose_uM)

        # Sample timeseries for each vessel
        for v_idx in range(n_vessels):
            vid = f"v{v_idx:02d}"
            times, viabs, er_stress = [], [], []

            vm_temp = BiologicalVirtualMachine(seed=seed)
            vm_temp.seed_vessel(vid, cell_line, initial_count=1e6)

            t = 0.0
            while t <= total_duration_h:
                vessel = vm_temp.vessel_states[vid]
                times.append(t)
                viabs.append(vessel.viability)
                er_stress.append(vessel.er_stress)

                if abs(t - treatment_start_h) < 1e-6:
                    vm_temp.treat_with_compound(vid, compound, dose_uM=dose_uM)

                vm_temp.advance_time(sample_interval_h)
                t += sample_interval_h

            vessel_results.append({
                'vessel_id': vid,
                'times': np.array(times),
                'viability': np.array(viabs),
                'er_stress': np.array(er_stress)
            })

        run_results.append({
            'run_idx': run_idx,
            'seed': seed,
            'vessels': vessel_results
        })

    metadata = {
        'compound': compound, 'dose_uM': dose_uM, 'ic50_uM': ic50_uM,
        'cell_line': cell_line, 'treatment_start_h': treatment_start_h,
        'n_runs': n_runs, 'n_vessels': n_vessels
    }

    return run_results, metadata


def compute_time_to_threshold_interpolated(
    viability_series,
    times,
    threshold: float,
    *,
    require_crossing: bool = True,
    eps: float = 1e-12,
):
    """
    Linear-interpolated threshold crossing time.

    Hardened against:
    - Plateaus (v_next == v_curr) → no division by zero
    - Numerical noise → clamp alpha to [0, 1]
    - Edge cases → handle already-below, no-crossing, empty arrays

    Args:
        viability_series: Array of viability values (typically decreasing)
        times: Array of corresponding timepoints
        threshold: Threshold value to detect crossing
        require_crossing: If True, return np.nan if no crossing found
        eps: Numerical tolerance for zero-division check

    Returns:
        Interpolated time of threshold crossing, or np.nan if no crossing
    """
    v = np.asarray(viability_series, dtype=float)
    t = np.asarray(times, dtype=float)

    if v.size == 0 or t.size == 0 or v.size != t.size:
        return np.nan

    # Already below at start
    if v[0] < threshold:
        return float(t[0])

    # Find first interval that crosses from >= threshold to < threshold
    for i in range(v.size - 1):
        v0 = float(v[i])
        v1 = float(v[i + 1])
        t0 = float(t[i])
        t1 = float(t[i + 1])

        # Skip degenerate or non-forward time
        if t1 <= t0:
            continue

        if v0 >= threshold and v1 < threshold:
            dv = v1 - v0
            dt = t1 - t0

            # If dv is ~0 (plateau), we cannot interpolate; fall back to right endpoint
            if abs(dv) < eps:
                return float(t1)

            alpha = (threshold - v0) / dv  # dv is negative for decreasing series
            # Clamp for numerical stability (should be in [0,1] but guard anyway)
            alpha = float(np.clip(alpha, 0.0, 1.0))
            return float(t0 + alpha * dt)

    if require_crossing:
        return np.nan

    # If caller prefers "first time below" fallback when no crossing
    idx = np.where(v < threshold)[0]
    return float(t[idx[0]]) if idx.size > 0 else np.nan


def _cv(x):
    """Helper: compute coefficient of variation, robust to small N."""
    x = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    if x.size < 3:
        return np.nan
    mu = float(np.mean(x))
    if abs(mu) < 1e-12:
        return np.nan
    return float(np.std(x) / mu)


def plot_fig1_overlay(run_results, metadata, out_dir, git_sha):
    """FIG1: Multi-run multi-vessel viability overlay."""
    fig, ax = plt.subplots(figsize=(10, 6))

    for run in run_results:
        for vessel in run['vessels']:
            ax.plot(vessel['times'], vessel['viability'], 'b-', alpha=0.15, linewidth=0.5)

    # Mean across all
    all_viabs = [v['viability'] for run in run_results for v in run['vessels']]
    mean_viab = np.mean(all_viabs, axis=0)
    ax.plot(run_results[0]['vessels'][0]['times'], mean_viab, 'r-', linewidth=2.5, label='Grand Mean')

    ax.axvline(metadata['treatment_start_h'], color='gray', linestyle='--', alpha=0.5)
    ax.set_xlabel('Time (h)', fontsize=12)
    ax.set_ylabel('Viability', fontsize=12)
    ax.set_title(f"FIG1: Multi-Run Multi-Vessel Overlay ({git_sha})\n"
                 f"{metadata['n_runs']}runs × {metadata['n_vessels']}vessels, "
                 f"{metadata['compound']} @ {metadata['dose_uM']/metadata['ic50_uM']:.1f}× IC50",
                 fontsize=10)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_dir / "fig1_multirun_overlay.png", dpi=150)
    plt.close(fig)

    final_viabs = [v['viability'][-1] for run in run_results for v in run['vessels']]
    return {'cv_final_viability': np.std(final_viabs)/np.mean(final_viabs)}


def plot_fig2_thresholds_kde(run_results, metadata, out_dir, git_sha):
    """FIG2: Time-to-threshold KDE + rug for 0.7/0.5/0.3."""
    thresholds = [0.7, 0.5, 0.3]
    fig, axes = plt.subplots(3, 1, figsize=(10, 12))

    metrics = {}
    for thresh, ax in zip(thresholds, axes):
        times_to_thresh = []
        for run in run_results:
            for vessel in run['vessels']:
                t = compute_time_to_threshold_interpolated(vessel['viability'], vessel['times'], thresh)
                if not np.isnan(t):
                    times_to_thresh.append(t)

        if len(times_to_thresh) > 2:
            # Check if all values identical (perfect reproducibility)
            if np.std(times_to_thresh) < 1e-6:
                # Skip KDE, show spike instead
                ax.axvline(np.mean(times_to_thresh), color='blue', linewidth=3,
                          label=f'All identical at {np.mean(times_to_thresh):.1f}h')
            else:
                # KDE
                from scipy.stats import gaussian_kde
                kde = gaussian_kde(times_to_thresh)
                x_range = np.linspace(min(times_to_thresh)-5, max(times_to_thresh)+5, 200)
                ax.plot(x_range, kde(x_range), 'b-', linewidth=2, label='KDE')
                ax.fill_between(x_range, kde(x_range), alpha=0.3)

            # Rug
            ax.plot(times_to_thresh, np.zeros_like(times_to_thresh), '|', color='red',
                   markersize=10, markeredgewidth=1.5, label='Observations')

            mean_t = np.mean(times_to_thresh)
            std_t = np.std(times_to_thresh)
            cv_t = _cv(times_to_thresh)

            ax.axvline(mean_t, color='green', linestyle='--', linewidth=2, label=f'Mean={mean_t:.1f}h')
            ax.text(0.02, 0.98, f'CV = {cv_t:.4f}\n±σ = {std_t:.2f}h',
                   transform=ax.transAxes, va='top', fontsize=10,
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))

            metrics[f'thresh_{thresh}'] = {'cv': cv_t, 'mean': mean_t, 'std': std_t}
        else:
            ax.text(0.5, 0.5, f'Insufficient data for threshold {thresh}',
                   ha='center', va='center', transform=ax.transAxes)
            metrics[f'thresh_{thresh}'] = {'cv': 0, 'mean': None, 'std': 0}

        ax.set_xlabel('Time (h)', fontsize=11)
        ax.set_ylabel('Density', fontsize=11)
        ax.set_title(f'Threshold = {thresh}', fontsize=10)
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)

    fig.suptitle(f"FIG2: Time-to-Threshold Distributions ({git_sha})", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_dir / "fig2_threshold_kde.png", dpi=150)
    plt.close(fig)

    return metrics


def plot_fig3_correlation_matrix(run_results, metadata, out_dir, git_sha):
    """FIG3: Within-run correlation (one representative run)."""
    # Use first run
    run = run_results[0]
    viab_matrix = np.array([v['viability'] for v in run['vessels']])
    corr = np.corrcoef(viab_matrix)

    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1)
    n_v = len(run['vessels'])
    ax.set_xticks(range(n_v))
    ax.set_yticks(range(n_v))
    ax.set_xticklabels([f"V{i}" for i in range(n_v)], fontsize=8)
    ax.set_yticklabels([f"V{i}" for i in range(n_v)], fontsize=8)
    ax.set_title(f"FIG3: Within-Run Correlation Matrix ({git_sha})\n"
                 f"Run 0 (seed={run['seed']}), {n_v} vessels", fontsize=10)
    plt.colorbar(im, ax=ax, label='Correlation')
    fig.tight_layout()
    fig.savefig(out_dir / "fig3_within_run_corr.png", dpi=150)
    plt.close(fig)

    off_diag = corr[~np.eye(n_v, dtype=bool)]
    return {'mean_pairwise_correlation': np.mean(off_diag)}


def plot_fig5_variance_decomposition(run_results, metadata, out_dir, git_sha):
    """FIG5: Within-run vs between-run variance decomposition."""
    # Extract final viability for each vessel in each run
    run_means = []
    within_run_vars = []

    for run in run_results:
        final_viabs = [v['viability'][-1] for v in run['vessels']]
        run_means.append(np.mean(final_viabs))
        within_run_vars.append(np.var(final_viabs))

    between_run_var = np.var(run_means)
    mean_within_run_var = np.mean(within_run_vars)

    fig, ax = plt.subplots(figsize=(8, 6))

    categories = ['Within-Run\nVariance', 'Between-Run\nVariance']
    values = [mean_within_run_var, between_run_var]
    colors = ['steelblue', 'darkorange']

    bars = ax.bar(categories, values, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
    ax.set_ylabel('Variance', fontsize=12)
    ax.set_title(f"FIG5: Variance Decomposition ({git_sha})\n"
                 f"Final Viability: {metadata['n_runs']} runs × {metadata['n_vessels']} vessels",
                 fontsize=10)
    ax.grid(axis='y', alpha=0.3)

    # Annotate values
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height*1.02, f'{val:.6f}',
               ha='center', va='bottom', fontsize=10, fontweight='bold')

    fig.tight_layout()
    fig.savefig(out_dir / "fig5_variance_decomp.png", dpi=150)
    plt.close(fig)

    return {'within_run_var': mean_within_run_var, 'between_run_var': between_run_var}


def plot_fig6_correlation_structure(run_results, metadata, out_dir, git_sha):
    """FIG6: Within-run vs across-run correlation structure."""
    # Compute within-run correlations (average over all runs)
    within_run_corrs = []
    for run in run_results:
        viab_matrix = np.array([v['viability'] for v in run['vessels']])
        corr = np.corrcoef(viab_matrix)
        off_diag = corr[~np.eye(len(run['vessels']), dtype=bool)]
        within_run_corrs.extend(off_diag)

    # Compute across-run correlations (pairs from different runs)
    across_run_corrs = []
    for i, run_i in enumerate(run_results):
        for j, run_j in enumerate(run_results):
            if i >= j:
                continue
            # Correlate first vessel from each run
            viab_i = run_i['vessels'][0]['viability']
            viab_j = run_j['vessels'][0]['viability']
            corr_ij = np.corrcoef(viab_i, viab_j)[0, 1]
            across_run_corrs.append(corr_ij)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Panel A: Within-run
    ax = axes[0]
    if np.std(within_run_corrs) < 1e-6:
        # All identical - show as vertical line
        ax.axvline(np.mean(within_run_corrs), color='steelblue', linewidth=4,
                  label=f'All identical: {np.mean(within_run_corrs):.4f}')
        ax.set_xlim([np.mean(within_run_corrs)-0.1, np.mean(within_run_corrs)+0.1])
    else:
        ax.hist(within_run_corrs, bins=20, color='steelblue', alpha=0.7, edgecolor='black')
        ax.axvline(np.mean(within_run_corrs), color='red', linestyle='--', linewidth=2,
                  label=f'Mean={np.mean(within_run_corrs):.4f}')
    ax.set_xlabel('Correlation', fontsize=11)
    ax.set_ylabel('Count', fontsize=11)
    ax.set_title('Within-Run Vessel Correlations', fontsize=10)
    ax.legend()
    ax.grid(alpha=0.3)

    # Panel B: Across-run
    ax = axes[1]
    if np.std(across_run_corrs) < 1e-6:
        # All identical - show as vertical line
        ax.axvline(np.mean(across_run_corrs), color='darkorange', linewidth=4,
                  label=f'All identical: {np.mean(across_run_corrs):.4f}')
        ax.set_xlim([np.mean(across_run_corrs)-0.1, np.mean(across_run_corrs)+0.1])
    else:
        ax.hist(across_run_corrs, bins=20, color='darkorange', alpha=0.7, edgecolor='black')
        ax.axvline(np.mean(across_run_corrs), color='red', linestyle='--', linewidth=2,
                  label=f'Mean={np.mean(across_run_corrs):.4f}')
    ax.set_xlabel('Correlation', fontsize=11)
    ax.set_ylabel('Count', fontsize=11)
    ax.set_title('Across-Run Correlations', fontsize=10)
    ax.legend()
    ax.grid(alpha=0.3)

    fig.suptitle(f"FIG6: Correlation Structure ({git_sha})", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_dir / "fig6_correlation_structure.png", dpi=150)
    plt.close(fig)

    return {
        'mean_within_run_corr': np.mean(within_run_corrs),
        'mean_across_run_corr': np.mean(across_run_corrs)
    }


def run_washout_protocol(n_runs=8, cell_line="A549", compound="staurosporine", dose_multiplier=2.0):
    """FIG4: Washout recovery protocol."""
    ic50_uM = get_compound_ic50(compound, cell_line)
    dose_uM = ic50_uM * dose_multiplier

    results = []
    for seed in range(2000, 2000 + n_runs):
        vm = BiologicalVirtualMachine(seed=seed)
        vm.seed_vessel("test", cell_line, initial_count=1e6)
        vm.advance_time(12.0)
        vm.treat_with_compound("test", compound, dose_uM=dose_uM)
        vm.advance_time(12.0)
        vm.washout_compound("test")

        times_post, viabs, eff_doses = [], [], []
        for t in range(0, 49, 6):
            vessel = vm.vessel_states["test"]
            times_post.append(t)
            viabs.append(vessel.viability)
            eff_dose = vm._get_effective_dose_uM(vessel, compound, vm.simulated_time)
            eff_doses.append(eff_dose)
            vm.advance_time(6.0)

        results.append({
            'seed': seed,
            'times_post': np.array(times_post),
            'viability': np.array(viabs),
            'effective_dose': np.array(eff_doses)
        })

    return results, {'compound': compound, 'dose_uM': dose_uM, 'ic50_uM': ic50_uM, 'cell_line': cell_line}


def plot_fig4_washout(results, metadata, out_dir, git_sha):
    """FIG4: Washout recovery with anti-cheat guard."""
    fig, axes = plt.subplots(2, 1, figsize=(10, 10))

    # Panel A: Effective dose
    ax = axes[0]
    for r in results:
        ax.plot(r['times_post'], r['effective_dose'], 'b-', alpha=0.3, linewidth=0.8)
    mean_dose = np.mean([r['effective_dose'] for r in results], axis=0)
    ax.plot(results[0]['times_post'], mean_dose, 'r-', linewidth=2.5, label='Mean')
    ax.set_ylabel('Effective Dose (µM)', fontsize=12)
    ax.set_title(f"FIG4A: Washout - Effective Dose Decay ({git_sha})", fontsize=10)
    ax.legend()
    ax.grid(alpha=0.3)

    # Panel B: Viability
    ax = axes[1]
    for r in results:
        ax.plot(r['times_post'], r['viability'], 'g-', alpha=0.3, linewidth=0.8)
    mean_viab = np.mean([r['viability'] for r in results], axis=0)
    ax.plot(results[0]['times_post'], mean_viab, 'r-', linewidth=2.5, label='Mean')
    ax.set_xlabel('Time post-washout (h)', fontsize=12)
    ax.set_ylabel('Viability', fontsize=12)
    ax.set_title(f"FIG4B: Washout - Viability Recovery", fontsize=10)
    ax.legend()
    ax.grid(alpha=0.3)

    fig.suptitle(f"N={len(results)} runs, {metadata['compound']}", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_dir / "fig4_washout.png", dpi=150)
    plt.close(fig)

    # Compute half-lives
    half_lives = []
    for r in results:
        if r['effective_dose'][0] > 0:
            half = r['effective_dose'][0] / 2
            idx = np.where(r['effective_dose'] < half)[0]
            if len(idx) > 0:
                half_lives.append(r['times_post'][idx[0]])

    cv_hl = np.std(half_lives)/np.mean(half_lives) if len(half_lives) > 0 and np.mean(half_lives) > 0 else 0

    # ANTI-CHEAT: Check if curves are identical up to scale
    dose_curves = [r['effective_dose'] for r in results]
    normalized_curves = [c / c[0] if c[0] > 0 else c for c in dose_curves]
    curve_cv = np.std(normalized_curves, axis=0).mean()
    cosmetic_warning = (cv_hl > 0.05 and curve_cv < 0.01)

    return {
        'cv_half_life': cv_hl,
        'mean_half_life': np.mean(half_lives) if len(half_lives) > 0 else None,
        'cosmetic_warning': cosmetic_warning
    }


def check_anti_cheat_guards(metrics):
    """Check for fake variance (global jitter or cosmetic scaling)."""
    warnings = []

    # Guard 1: High CV but still perfectly correlated
    within_corr = metrics.get('fig6', {}).get('mean_within_run_corr', 0)
    cv_thresh = metrics.get('fig2', {}).get('thresh_0.5', {}).get('cv', 0)

    if cv_thresh > 0.05 and within_corr > 0.95:
        warnings.append({
            'type': 'global_jitter',
            'message': f"Variance increased (CV={cv_thresh:.3f}) but within-run correlation={within_corr:.4f} >0.95. "
                      f"Likely global jitter, not biological heterogeneity."
        })

    # Guard 2: Washout half-life cosmetic
    if metrics.get('fig4', {}).get('cosmetic_warning', False):
        warnings.append({
            'type': 'cosmetic_washout',
            'message': f"Washout half-life varies but dose curves identical up to scale. Cosmetic variance."
        })

    return warnings


def main():
    parser = argparse.ArgumentParser(description='Reproducibility visualization')
    parser.add_argument('--mode', default='single', choices=['single', 'compare'])
    parser.add_argument('--before', help='Before SHA for compare mode')
    parser.add_argument('--after', help='After SHA for compare mode')
    args = parser.parse_args()

    if args.mode == 'single':
        # Single mode: run on current HEAD
        git_sha = get_git_sha()
        out_dir = ensure_output_dir(Path(__file__).parents[1] / "artifacts" / "repro_plots" / git_sha)

        print(f"Running single mode: {git_sha}")
        print(f"Output: {out_dir}")

        # Run protocols
        print("Running multi-run multi-vessel protocol...")
        run_results, metadata = run_multi_run_multi_vessel(n_runs=8, n_vessels=8)

        print("Generating figures...")
        metrics = {}
        metrics['fig1'] = plot_fig1_overlay(run_results, metadata, out_dir, git_sha)
        metrics['fig2'] = plot_fig2_thresholds_kde(run_results, metadata, out_dir, git_sha)
        metrics['fig3'] = plot_fig3_correlation_matrix(run_results, metadata, out_dir, git_sha)
        metrics['fig5'] = plot_fig5_variance_decomposition(run_results, metadata, out_dir, git_sha)
        metrics['fig6'] = plot_fig6_correlation_structure(run_results, metadata, out_dir, git_sha)

        print("Running washout protocol...")
        washout_results, washout_meta = run_washout_protocol(n_runs=8)
        metrics['fig4'] = plot_fig4_washout(washout_results, washout_meta, out_dir, git_sha)

        # Anti-cheat guards
        warnings = check_anti_cheat_guards(metrics)

        summary = {
            'git_sha': git_sha,
            'metrics': metrics,
            'warnings': warnings
        }

        # Convert numpy types for JSON serialization
        def convert_to_native(obj):
            if isinstance(obj, np.generic):
                return obj.item()
            elif isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(v) for v in obj]
            return obj

        with open(out_dir / "summary.json", 'w') as f:
            json.dump(convert_to_native(summary), f, indent=2)

        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"CV(final viability): {metrics['fig1']['cv_final_viability']:.4f}")
        print(f"CV(time-to-0.5): {metrics['fig2']['thresh_0.5']['cv']:.4f}")
        print(f"Mean within-run correlation: {metrics['fig6']['mean_within_run_corr']:.4f}")
        print(f"Mean across-run correlation: {metrics['fig6']['mean_across_run_corr']:.4f}")
        print(f"Between/Within variance ratio: {metrics['fig5']['between_run_var']/metrics['fig5']['within_run_var']:.2f}")

        if warnings:
            print("\nWARNINGS:")
            for w in warnings:
                print(f"  [{w['type']}] {w['message']}")

    elif args.mode == 'compare':
        print("Compare mode not yet implemented - run single mode on both SHAs first")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
