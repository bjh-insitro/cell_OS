"""
Runner for identifiability suite.

Executes 3-regime design and produces tidy datasets:
- observations.csv (long-format time series)
- events.csv (commitment events)
- truth.json (ground truth parameters)
- metadata.json (run info)
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from .identifiability_design import IdentifiabilityDesign, RegimePlan


class IdentifiabilityRunner:
    """Executes identifiability design and saves tidy datasets."""

    def __init__(self, design: IdentifiabilityDesign, output_dir: Path, run_id: Optional[str] = None):
        """
        Initialize runner.

        Args:
            design: Loaded IdentifiabilityDesign
            output_dir: Base output directory (e.g., artifacts/identifiability/)
            run_id: Optional run identifier (defaults to timestamp)
        """
        self.design = design
        self.output_dir = Path(output_dir)

        if run_id is None:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = run_id

        self.run_dir = self.output_dir / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Storage for observations and events
        self.observations_records = []
        self.events_records = []

    def run(self) -> Dict[str, Path]:
        """
        Execute full identifiability suite.

        Returns:
            Dict of artifact paths: {'observations', 'events', 'truth', 'metadata'}
        """
        # Save design config
        import shutil
        # Note: design doesn't store original path, so we reconstruct or skip
        # For now, just save truth/metadata

        # Get bio_noise_config from design
        bio_noise_config = self.design.get_bio_noise_config()
        seed = self.design.global_config['seed']

        # Execute each regime with independent VM (each regime is a separate plate/experiment)
        regime_plans = self.design.build_all_regimes()
        for i, regime_plan in enumerate(regime_plans):
            # Create fresh VM for each regime to avoid time conflicts
            vm = BiologicalVirtualMachine(
                seed=seed + i,  # Different seed per regime for independent noise
                bio_noise_config=bio_noise_config
            )
            self._execute_regime(vm, regime_plan)

        # Save artifacts
        artifacts = self._save_artifacts()

        print(f"✅ Identifiability suite complete: {self.run_dir}")
        return artifacts

    def _execute_regime(self, vm: BiologicalVirtualMachine, regime_plan: RegimePlan):
        """
        Execute one regime (seed wells, treat, advance time, record observations).

        Args:
            vm: Shared BiologicalVirtualMachine instance
            regime_plan: RegimePlan with actions and timepoints
        """
        regime_name = regime_plan.regime_name
        print(f"▶ Executing regime: {regime_name}")

        # Execute actions (seed + treat)
        vessel_ids = []
        for action in regime_plan.actions:
            if action.action_type == "seed":
                vessel_ids.append(action.vessel_id)
                vm.seed_vessel(
                    vessel_id=action.vessel_id,
                    cell_line=action.params['cell_line'],
                    initial_count=action.params['initial_count']
                    # Note: working_volume_ml and confluence are handled internally by VM
                )

            elif action.action_type == "treat":
                vm.treat_with_compound(
                    vessel_id=action.vessel_id,
                    compound=action.params['compound'],
                    dose_uM=action.params['dose_uM']
                )

        # Record observations at each timepoint
        for timepoint_h in regime_plan.timepoints:
            # Advance to timepoint
            current_time = vm.simulated_time
            dt = timepoint_h - current_time
            if dt > 0:
                vm.advance_time(dt)

            # Record observations for all wells in this regime
            for vessel_id in vessel_ids:
                vessel = vm.vessel_states[vessel_id]
                self._record_observation(regime_name, vessel_id, vessel, timepoint_h, regime_plan.metrics)

        # Record commitment events for all wells in this regime
        for vessel_id in vessel_ids:
            vessel = vm.vessel_states[vessel_id]
            self._record_event(regime_name, vessel_id, vessel)

        print(f"  ✓ Recorded {len(vessel_ids)} wells × {len(regime_plan.timepoints)} timepoints")

    def _record_observation(
        self,
        regime_name: str,
        vessel_id: str,
        vessel,
        time_h: float,
        metrics: List[str]
    ):
        """Record observation for one well at one timepoint."""
        # Extract plate_id from vessel_id (format: "PlateA1_A01")
        plate_id = vessel_id.split('_')[0] if '_' in vessel_id else vessel_id

        for metric_name in metrics:
            # Get metric value from vessel state
            if hasattr(vessel, metric_name):
                value = getattr(vessel, metric_name)
            else:
                # Skip metrics not available
                continue

            self.observations_records.append({
                'run_id': self.run_id,
                'regime': regime_name,
                'plate_id': plate_id,
                'well_id': vessel_id,
                'time_h': time_h,
                'metric_name': metric_name,
                'value': float(value) if value is not None else None,
            })

    def _record_event(self, regime_name: str, vessel_id: str, vessel):
        """Record commitment event for one well."""
        plate_id = vessel_id.split('_')[0] if '_' in vessel_id else vessel_id

        committed = vessel.death_committed if hasattr(vessel, 'death_committed') else False
        commitment_time_h = vessel.death_committed_at_h if hasattr(vessel, 'death_committed_at_h') else None
        mechanism = vessel.death_commitment_mechanism if hasattr(vessel, 'death_commitment_mechanism') else None

        self.events_records.append({
            'run_id': self.run_id,
            'regime': regime_name,
            'plate_id': plate_id,
            'well_id': vessel_id,
            'committed': committed,
            'commitment_time_h': float(commitment_time_h) if commitment_time_h is not None else None,
            'mechanism': mechanism if mechanism is not None else None,
        })

    def _save_artifacts(self) -> Dict[str, Path]:
        """Save all artifacts to disk."""
        artifacts = {}

        # Observations CSV
        obs_df = pd.DataFrame(self.observations_records)
        obs_path = self.run_dir / "observations.csv"
        obs_df.to_csv(obs_path, index=False)
        artifacts['observations'] = obs_path
        print(f"  Saved: {obs_path} ({len(obs_df)} rows)")

        # Events CSV
        events_df = pd.DataFrame(self.events_records)
        events_path = self.run_dir / "events.csv"
        events_df.to_csv(events_path, index=False)
        artifacts['events'] = events_path
        print(f"  Saved: {events_path} ({len(events_df)} rows)")

        # Truth JSON
        truth_path = self.run_dir / "truth.json"
        with open(truth_path, 'w') as f:
            json.dump(self.design.truth, f, indent=2)
        artifacts['truth'] = truth_path
        print(f"  Saved: {truth_path}")

        # Metadata JSON
        metadata = {
            'run_id': self.run_id,
            'timestamp': datetime.now().isoformat(),
            'seed': self.design.global_config['seed'],
            'cell_line': self.design.global_config['cell_line'],
            'n_regimes': 3,
            'n_wells_total': len(set(r['well_id'] for r in self.events_records)),
            'n_timepoints': len(self.design.timepoints),
            'metrics': self.design.metrics,
        }
        metadata_path = self.run_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        artifacts['metadata'] = metadata_path
        print(f"  Saved: {metadata_path}")

        return artifacts


def run_identifiability_suite(config_path: str, output_dir: str, run_id: Optional[str] = None) -> Path:
    """
    Convenience function to run full suite.

    Args:
        config_path: Path to identifiability_2c1.yaml
        output_dir: Output directory for artifacts
        run_id: Optional run identifier

    Returns:
        Path to run directory
    """
    design = IdentifiabilityDesign(config_path)
    runner = IdentifiabilityRunner(design, Path(output_dir), run_id=run_id)
    runner.run()
    return runner.run_dir


def run_dose_scout(
    config_path: str,
    output_dir: str,
    compound: str,
    dose_range: tuple[float, float],
    n_doses: int,
    n_wells_per_dose: int,
    run_id: Optional[str] = None
) -> Path:
    """
    Run dose ladder scout to empirically find commitment-producing doses.

    Args:
        config_path: Path to identifiability_2c1.yaml
        output_dir: Output directory for scout artifacts
        compound: Compound to test (e.g., "tunicamycin")
        dose_range: (min_uM, max_uM) for log-spaced ladder
        n_doses: Number of dose levels
        n_wells_per_dose: Replicates per dose
        run_id: Optional run identifier

    Returns:
        Path to scout directory
    """
    design = IdentifiabilityDesign(config_path)

    if run_id is None:
        run_id = f"scout_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Build scout regime
    scout_regime = design.build_scout_regime(
        compound=compound,
        dose_range=dose_range,
        n_doses=n_doses,
        n_wells_per_dose=n_wells_per_dose
    )

    # Initialize VM
    bio_noise_config = design.get_bio_noise_config()
    seed = design.global_config['seed']
    vm = BiologicalVirtualMachine(seed=seed, bio_noise_config=bio_noise_config)

    # Execute scout regime
    print(f"▶ Executing dose scout: {compound} {dose_range[0]:.3f}-{dose_range[1]:.1f} µM")
    observations_records = []
    events_records = []

    # Execute actions
    vessel_ids = []
    doses_uM_per_well = {}

    for action in scout_regime.actions:
        if action.action_type == "seed":
            vessel_ids.append(action.vessel_id)
            vm.seed_vessel(
                vessel_id=action.vessel_id,
                cell_line=action.params['cell_line'],
                initial_count=action.params['initial_count']
            )
        elif action.action_type == "treat":
            vm.treat_with_compound(
                vessel_id=action.vessel_id,
                compound=action.params['compound'],
                dose_uM=action.params['dose_uM']
            )
            doses_uM_per_well[action.vessel_id] = action.params['dose_uM']

    # Advance time and record observations
    for timepoint_h in scout_regime.timepoints:
        current_time = vm.simulated_time
        dt = timepoint_h - current_time
        if dt > 0:
            vm.advance_time(dt)

        for vessel_id in vessel_ids:
            vessel = vm.vessel_states[vessel_id]
            for metric_name in scout_regime.metrics:
                if hasattr(vessel, metric_name):
                    value = getattr(vessel, metric_name)
                    observations_records.append({
                        'well_id': vessel_id,
                        'dose_uM': doses_uM_per_well[vessel_id],
                        'time_h': timepoint_h,
                        'metric_name': metric_name,
                        'value': float(value) if value is not None else None,
                    })

    # Record events
    for vessel_id in vessel_ids:
        vessel = vm.vessel_states[vessel_id]
        committed = vessel.death_committed if hasattr(vessel, 'death_committed') else False
        commitment_time_h = vessel.death_committed_at_h if hasattr(vessel, 'death_committed_at_h') else None
        mechanism = vessel.death_commitment_mechanism if hasattr(vessel, 'death_commitment_mechanism') else None

        events_records.append({
            'well_id': vessel_id,
            'dose_uM': doses_uM_per_well[vessel_id],
            'committed': committed,
            'commitment_time_h': float(commitment_time_h) if commitment_time_h is not None else None,
            'mechanism': mechanism,
        })

    # Save observations and events
    obs_df = pd.DataFrame(observations_records)
    events_df = pd.DataFrame(events_records)

    obs_df.to_csv(run_dir / "observations.csv", index=False)
    events_df.to_csv(run_dir / "events.csv", index=False)

    print(f"  ✓ Recorded {len(vessel_ids)} wells across {n_doses} doses")

    # Analyze commitment fractions per dose
    dose_analysis = []
    unique_doses = sorted(events_df['dose_uM'].unique())

    for dose_uM in unique_doses:
        dose_events = events_df[events_df['dose_uM'] == dose_uM]
        n_wells = len(dose_events)
        n_committed = dose_events['committed'].sum()
        fraction_committed = n_committed / n_wells if n_wells > 0 else 0

        # Compute mean commitment time for those that committed
        committed_events = dose_events[dose_events['committed']]
        mean_commitment_time = (
            committed_events['commitment_time_h'].mean()
            if len(committed_events) > 0
            else None
        )

        dose_analysis.append({
            'dose_uM': dose_uM,
            'n_wells': n_wells,
            'n_committed': n_committed,
            'fraction_committed': fraction_committed,
            'mean_commitment_time_h': mean_commitment_time,
        })

    dose_analysis_df = pd.DataFrame(dose_analysis)
    dose_analysis_df.to_csv(run_dir / "dose_analysis.csv", index=False)

    # Generate scout report with dose suggestions
    report = _render_scout_report(
        compound=compound,
        dose_range=dose_range,
        dose_analysis_df=dose_analysis_df,
        timepoints=scout_regime.timepoints
    )

    report_path = run_dir / "scout_report.md"
    with open(report_path, 'w') as f:
        f.write(report)

    print(f"\n✓ Scout report: {report_path}\n")
    print(report)

    return run_dir


def _render_scout_report(
    compound: str,
    dose_range: tuple[float, float],
    dose_analysis_df: pd.DataFrame,
    timepoints: List[float]
) -> str:
    """Render scout report with dose suggestions."""
    # Find doses for B (10-40% commitment) and C (40-80% commitment)
    target_B_range = (0.10, 0.40)
    target_C_range = (0.40, 0.80)

    B_candidates = dose_analysis_df[
        (dose_analysis_df['fraction_committed'] >= target_B_range[0]) &
        (dose_analysis_df['fraction_committed'] <= target_B_range[1])
    ]
    C_candidates = dose_analysis_df[
        (dose_analysis_df['fraction_committed'] >= target_C_range[0]) &
        (dose_analysis_df['fraction_committed'] <= target_C_range[1])
    ]

    # Suggest doses
    suggested_B = B_candidates['dose_uM'].median() if len(B_candidates) > 0 else None
    suggested_C_low = C_candidates['dose_uM'].quantile(0.33) if len(C_candidates) > 0 else None
    suggested_C_mid = C_candidates['dose_uM'].median() if len(C_candidates) > 0 else None
    suggested_C_high = C_candidates['dose_uM'].quantile(0.67) if len(C_candidates) > 0 else None

    # If no candidates in range, fallback to closest
    if suggested_B is None:
        closest_to_25pct = (dose_analysis_df['fraction_committed'] - 0.25).abs().idxmin()
        suggested_B = dose_analysis_df.loc[closest_to_25pct, 'dose_uM']

    if suggested_C_mid is None:
        closest_to_60pct = (dose_analysis_df['fraction_committed'] - 0.60).abs().idxmin()
        suggested_C_mid = dose_analysis_df.loc[closest_to_60pct, 'dose_uM']

    report = f"""# Dose Scout Report

**Compound:** {compound}
**Dose Range:** {dose_range[0]:.3f}–{dose_range[1]:.1f} µM (log-spaced)
**Observation Window:** {timepoints[0]:.1f}–{timepoints[-1]:.1f} h

---

## Commitment Fraction by Dose

| Dose (µM) | Wells | Committed | Fraction | Mean Time (h) |
|-----------|-------|-----------|----------|---------------|
"""

    for _, row in dose_analysis_df.iterrows():
        mean_time_str = f"{row['mean_commitment_time_h']:.1f}" if pd.notna(row['mean_commitment_time_h']) else "—"
        report += f"| {row['dose_uM']:.3f} | {row['n_wells']} | {row['n_committed']} | {row['fraction_committed']:.3f} | {mean_time_str} |\n"

    report += f"""
---

## Dose Suggestions for Identifiability Suite

### Regime B (Mid Stress, Held-Out Prediction)
**Target:** 10–40% commitment
"""

    if len(B_candidates) > 0:
        report += f"**Suggested dose:** {suggested_B:.3f} µM ✅\n"
        report += f"*({len(B_candidates)} doses in target range)*\n"
    else:
        report += f"**Fallback dose:** {suggested_B:.3f} µM ⚠️\n"
        report += f"*(No doses in target range, using closest to 25%)*\n"

    report += f"""
### Regime C (High Stress, Parameter Recovery)
**Target:** 40–80% commitment (need variation for identifiability)
"""

    if len(C_candidates) >= 2:
        report += f"**Suggested doses:**\n"
        if suggested_C_low and suggested_C_low != suggested_C_mid:
            report += f"- C1: {suggested_C_low:.3f} µM\n"
        report += f"- C2: {suggested_C_mid:.3f} µM\n"
        if suggested_C_high and suggested_C_high != suggested_C_mid:
            report += f"- C3: {suggested_C_high:.3f} µM ✅\n"
        report += f"*({len(C_candidates)} doses in target range)*\n"
    elif suggested_C_mid:
        report += f"**Fallback dose:** {suggested_C_mid:.3f} µM ⚠️\n"
        report += f"*(Insufficient doses in target range, consider wider range or higher doses)*\n"
    else:
        report += f"**WARNING:** No suitable doses found. Consider:\n"
        report += f"- Increase dose range upper bound\n"
        report += f"- Increase observation window\n"
        report += f"- Check stress mechanism configuration\n"

    report += """
---

## Next Steps

1. Update `configs/calibration/identifiability_2c1.yaml` with suggested doses:
   - Set `regimes.mid_stress_mixed.dose_uM` to Regime B dose
   - Set `regimes.high_stress_event_rich.doses` to Regime C doses
2. Rerun full suite: `python scripts/run_identifiability_suite.py --config ... --out ...`
3. If results are still insufficient, adjust:
   - Hazard parameters in truth block
   - Observation window
   - Number of replicates

---

*Scout report generated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "*\n"

    return report
