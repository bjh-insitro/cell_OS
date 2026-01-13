"""
Ablation Harness: Measure Which Noise Sources Cause Calibration Failure

NOT just "does entropy increase" - but "does the agent become confidently wrong?"

Test Protocol:
1. Run same plate design with each noise source toggled on/off
2. Measure calibration error: P(confident and wrong)
3. Identify which sources cause **epistemic discipline failure**

Metrics:
- Mechanism posterior calibration (ECE-style)
- False discovery rate on controls (DMSO should not trigger mechanism)
- Signature detectability (can agent detect edge effects, run shifts?)
- Design quality (does agent choose confounded experiments?)

Output:
- Rank noise sources by "harm to calibration"
- Identify which sources are pedagogically useful vs decorative
- Measure pipetting correlation structure impact (iid vs correlated)
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import matplotlib.pyplot as plt
import seaborn as sns


@dataclass
class AblationCondition:
    """Single ablation condition: which noise sources are active."""
    name: str
    description: str
    active_injections: List[str]
    run_context_enabled: bool
    measurement_noise_enabled: bool


@dataclass
class CalibrationMetrics:
    """Metrics for epistemic calibration."""
    # Calibration
    expected_calibration_error: float  # ECE across confidence bins
    overconfidence_rate: float  # P(conf>0.9 and wrong)
    underconfidence_rate: float  # P(conf<0.5 and correct)

    # False discovery
    dmso_false_positive_rate: float  # P(DMSO flagged as mechanism)
    anchor_false_negative_rate: float  # P(Anchor missed)

    # Signature detection
    edge_effect_detection_accuracy: float  # Can agent detect evaporation?
    run_shift_detection_accuracy: float  # Can agent detect cursed day?

    # Design quality
    confounded_design_rate: float  # P(agent proposes bad experiment)
    self_sabotage_rate: float  # P(agent ignores known confounds)


@dataclass
class AblationResult:
    """Result from single ablation run."""
    condition: AblationCondition
    metrics: CalibrationMetrics
    raw_data: Dict[str, Any]
    forensic_notes: List[str]


class AblationHarness:
    """
    Ablation harness for noise source testing.

    Tests which noise sources cause **calibration failure**, not just variance.
    """

    def __init__(self, plate_design_path: Path, output_dir: Path):
        self.plate_design_path = plate_design_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: List[AblationResult] = []

    def define_ablation_conditions(self) -> List[AblationCondition]:
        """
        Define ablation conditions to test.

        Start with:
        1. Baseline (no noise)
        2. Each major noise source alone
        3. All noise sources together
        4. Pipetting variance: iid vs correlated
        """
        conditions = [
            # Baseline
            AblationCondition(
                name="baseline",
                description="No noise sources active (perfect measurements)",
                active_injections=[],
                run_context_enabled=False,
                measurement_noise_enabled=False
            ),

            # Run-level
            AblationCondition(
                name="run_context_only",
                description="Correlated cursed day effects only",
                active_injections=[],
                run_context_enabled=True,
                measurement_noise_enabled=False
            ),

            # Plate-level
            AblationCondition(
                name="evaporation_only",
                description="Volume evaporation (spatial structure)",
                active_injections=["volume_evaporation"],
                run_context_enabled=False,
                measurement_noise_enabled=False
            ),

            AblationCondition(
                name="cursed_plate_only",
                description="Rare catastrophic failures",
                active_injections=["cursed_plate"],
                run_context_enabled=False,
                measurement_noise_enabled=False
            ),

            AblationCondition(
                name="segmentation_failure_only",
                description="Adversarial measurement layer (count distortion)",
                active_injections=["segmentation_failure"],
                run_context_enabled=False,
                measurement_noise_enabled=False
            ),

            AblationCondition(
                name="plate_map_error_only",
                description="Execution errors (column shift, reagent swap)",
                active_injections=["plate_map_error"],
                run_context_enabled=False,
                measurement_noise_enabled=False
            ),

            # Well-level
            AblationCondition(
                name="pipetting_iid",
                description="Pipetting variance (iid, uncorrelated)",
                active_injections=["pipetting_variance"],
                run_context_enabled=False,
                measurement_noise_enabled=False
            ),

            # TODO: Add pipetting_correlated (row, tip-box patterns)

            # Measurement provocations
            AblationCondition(
                name="measurement_provocations",
                description="Stain/focus/fixation offsets",
                active_injections=[],
                run_context_enabled=False,
                measurement_noise_enabled=True
            ),

            # Full realism
            AblationCondition(
                name="full_realism",
                description="All noise sources active",
                active_injections=[
                    "volume_evaporation",
                    "cursed_plate",
                    "coating_quality",
                    "pipetting_variance",
                    "segmentation_failure",
                    "plate_map_error"
                ],
                run_context_enabled=True,
                measurement_noise_enabled=True
            ),
        ]

        return conditions

    def run_ablation(self, condition: AblationCondition, seed: int = 42) -> AblationResult:
        """
        Run simulation under one ablation condition.

        TODO: This is a placeholder. Actual implementation needs:
        1. Configure VM with specific injection set
        2. Run plate executor
        3. Collect agent decisions (if agent is hooked up)
        4. Compute calibration metrics
        """
        print(f"Running ablation: {condition.name}")
        print(f"  Description: {condition.description}")
        print(f"  Active injections: {condition.active_injections}")

        # Placeholder: would run actual simulation here
        # For now, generate mock metrics
        metrics = self._compute_mock_metrics(condition)

        result = AblationResult(
            condition=condition,
            metrics=metrics,
            raw_data={},
            forensic_notes=[]
        )

        self.results.append(result)
        return result

    def _compute_mock_metrics(self, condition: AblationCondition) -> CalibrationMetrics:
        """
        Compute calibration metrics from simulation results.

        TODO: Replace with real analysis once agent is hooked up.
        """
        # Mock: baseline has perfect calibration
        if condition.name == "baseline":
            return CalibrationMetrics(
                expected_calibration_error=0.01,
                overconfidence_rate=0.02,
                underconfidence_rate=0.05,
                dmso_false_positive_rate=0.01,
                anchor_false_negative_rate=0.00,
                edge_effect_detection_accuracy=1.00,
                run_shift_detection_accuracy=1.00,
                confounded_design_rate=0.00,
                self_sabotage_rate=0.00
            )

        # Mock: noise sources degrade calibration
        base_ece = 0.01
        base_overconf = 0.02

        # Estimate impact (hand-tuned for illustration)
        if "segmentation" in condition.name:
            # Segmentation failure is NASTY (changes sufficient statistics)
            return CalibrationMetrics(
                expected_calibration_error=0.25,  # High miscalibration
                overconfidence_rate=0.35,  # Very overconfident
                underconfidence_rate=0.05,
                dmso_false_positive_rate=0.15,  # False positives
                anchor_false_negative_rate=0.10,
                edge_effect_detection_accuracy=0.80,
                run_shift_detection_accuracy=0.70,
                confounded_design_rate=0.20,
                self_sabotage_rate=0.15
            )

        elif "plate_map" in condition.name:
            # Plate map errors are catastrophic
            return CalibrationMetrics(
                expected_calibration_error=0.40,  # Very miscalibrated
                overconfidence_rate=0.50,  # Extremely overconfident (wrong but sure)
                underconfidence_rate=0.05,
                dmso_false_positive_rate=0.30,
                anchor_false_negative_rate=0.40,  # Anchors in wrong place
                edge_effect_detection_accuracy=0.50,
                run_shift_detection_accuracy=0.50,
                confounded_design_rate=0.30,
                self_sabotage_rate=0.25
            )

        elif "run_context" in condition.name:
            # Run context is learnable but confusing
            return CalibrationMetrics(
                expected_calibration_error=0.12,
                overconfidence_rate=0.15,
                underconfidence_rate=0.10,
                dmso_false_positive_rate=0.08,
                anchor_false_negative_rate=0.05,
                edge_effect_detection_accuracy=0.85,
                run_shift_detection_accuracy=0.60,  # Hard to detect
                confounded_design_rate=0.12,
                self_sabotage_rate=0.08
            )

        else:
            # Other noise sources: moderate impact
            return CalibrationMetrics(
                expected_calibration_error=0.08,
                overconfidence_rate=0.10,
                underconfidence_rate=0.08,
                dmso_false_positive_rate=0.05,
                anchor_false_negative_rate=0.03,
                edge_effect_detection_accuracy=0.90,
                run_shift_detection_accuracy=0.85,
                confounded_design_rate=0.08,
                self_sabotage_rate=0.05
            )

    def run_all_ablations(self, seeds: List[int] = [42, 123, 456]) -> None:
        """Run all ablation conditions across multiple seeds."""
        conditions = self.define_ablation_conditions()

        for condition in conditions:
            for seed in seeds:
                self.run_ablation(condition, seed=seed)

    def analyze_results(self) -> pd.DataFrame:
        """
        Analyze ablation results to rank noise sources by harm.

        Returns DataFrame with metrics per condition.
        """
        data = []
        for result in self.results:
            row = {
                'condition': result.condition.name,
                'description': result.condition.description,
                **asdict(result.metrics)
            }
            data.append(row)

        df = pd.DataFrame(data)

        # Aggregate across seeds
        df_agg = df.groupby(['condition', 'description']).mean().reset_index()

        # Rank by overconfidence rate (key failure mode)
        df_agg = df_agg.sort_values('overconfidence_rate', ascending=False)

        return df_agg

    def plot_calibration_comparison(self, save_path: Optional[Path] = None):
        """
        Visualize calibration metrics across conditions.

        Focus on overconfidence rate (confidently wrong).
        """
        df = self.analyze_results()

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # 1. Overconfidence rate (key metric)
        ax = axes[0, 0]
        sns.barplot(data=df, y='condition', x='overconfidence_rate', ax=ax, palette='Reds_r')
        ax.set_xlabel('Overconfidence Rate\nP(conf>0.9 and wrong)', fontsize=11)
        ax.set_ylabel('')
        ax.set_title('Epistemic Failure: Confidently Wrong', fontsize=12, fontweight='bold')
        ax.axvline(0.05, color='green', linestyle='--', alpha=0.5, label='Acceptable')
        ax.legend()

        # 2. Expected Calibration Error
        ax = axes[0, 1]
        sns.barplot(data=df, y='condition', x='expected_calibration_error', ax=ax, palette='Blues_r')
        ax.set_xlabel('Expected Calibration Error (ECE)', fontsize=11)
        ax.set_ylabel('')
        ax.set_title('Overall Calibration Quality', fontsize=12, fontweight='bold')

        # 3. False Discovery Rate
        ax = axes[1, 0]
        sns.barplot(data=df, y='condition', x='dmso_false_positive_rate', ax=ax, palette='Oranges_r')
        ax.set_xlabel('False Positive Rate on DMSO', fontsize=11)
        ax.set_ylabel('')
        ax.set_title('Hallucinated Mechanisms', fontsize=12, fontweight='bold')

        # 4. Design Quality
        ax = axes[1, 1]
        sns.barplot(data=df, y='condition', x='confounded_design_rate', ax=ax, palette='Purples_r')
        ax.set_xlabel('Confounded Design Rate', fontsize=11)
        ax.set_ylabel('')
        ax.set_title('Agent Proposes Bad Experiments', fontsize=12, fontweight='bold')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✓ Saved: {save_path}")

        plt.show()

    def generate_report(self) -> str:
        """Generate text report ranking noise sources."""
        df = self.analyze_results()

        report = ["=" * 70]
        report.append("ABLATION HARNESS RESULTS")
        report.append("=" * 70)
        report.append("")
        report.append("Noise sources ranked by **overconfidence rate** (confidently wrong):")
        report.append("")

        for idx, row in df.iterrows():
            report.append(f"{idx+1}. {row['condition']}")
            report.append(f"   {row['description']}")
            report.append(f"   Overconfidence rate: {row['overconfidence_rate']:.2%}")
            report.append(f"   ECE: {row['expected_calibration_error']:.3f}")
            report.append(f"   DMSO false positives: {row['dmso_false_positive_rate']:.2%}")
            report.append("")

        report.append("=" * 70)
        report.append("INTERPRETATION:")
        report.append("=" * 70)
        report.append("")
        report.append("Top 3 sources are **pedagogically essential**:")
        report.append("- These cause calibration failure (confidently wrong)")
        report.append("- Agent must learn to defend against these")
        report.append("")
        report.append("Bottom 3 sources are **decorative**:")
        report.append("- Add variance but don't break calibration")
        report.append("- Could remove without harming training")
        report.append("")

        return "\n".join(report)

    def save_results(self):
        """Save ablation results to disk."""
        df = self.analyze_results()

        # Save CSV
        csv_path = self.output_dir / "ablation_results.csv"
        df.to_csv(csv_path, index=False)
        print(f"✓ Saved: {csv_path}")

        # Save text report
        report_path = self.output_dir / "ablation_report.txt"
        with open(report_path, 'w') as f:
            f.write(self.generate_report())
        print(f"✓ Saved: {report_path}")

        # Save plot
        plot_path = self.output_dir / "ablation_calibration_comparison.png"
        self.plot_calibration_comparison(save_path=plot_path)


if __name__ == "__main__":
    # Example usage
    plate_design = Path("validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v2.json")
    output_dir = Path("results/ablation_harness")

    harness = AblationHarness(plate_design, output_dir)

    print("Running ablation harness...")
    harness.run_all_ablations(seeds=[42, 123, 456])

    print("\nAnalyzing results...")
    harness.save_results()

    print("\n" + harness.generate_report())
