"""
Demo: Adversarial Noise Sources in Action

Shows segmentation failure and plate map errors creating "confidently wrong" scenarios.

Demonstrates:
1. Segmentation failure at high density (merges)
2. Segmentation failure at low density (splits)
3. QC gating creating survivorship bias
4. Plate map column shift breaking dose-response
5. Forensic detection methods
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Import our new modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cell_os.hardware.injections.segmentation_failure import (
    SegmentationFailureInjection,
    SegmentationFailureState
)
from src.cell_os.hardware.injections.plate_map_error import (
    PlateMapErrorInjection,
    PlateMapErrorState,
    PlateMapErrorType
)
from src.cell_os.hardware.injections.base import InjectionContext
from src.cell_os.hardware.run_context import RunContext


def demo_segmentation_failure():
    """Demo segmentation failure at different densities."""
    print("="*70)
    print("DEMO 1: Segmentation Failure")
    print("="*70)
    print()

    injection = SegmentationFailureInjection()
    rng = np.random.default_rng(42)
    run_context = RunContext.sample(42)
    ctx = InjectionContext(simulated_time=48.0, run_context=run_context)

    # Test scenarios
    scenarios = [
        ("Low density (20%)", 0.2, 0.0, 0.0, 1.0, 1000),
        ("Nominal density (50%)", 0.5, 0.0, 0.0, 1.0, 1000),
        ("High density (80%)", 0.8, 0.0, 0.0, 1.0, 1000),
        ("High density + debris", 0.8, 0.3, 0.0, 1.0, 1000),
        ("High density + defocus", 0.8, 0.0, 3.0, 1.0, 1000),
        ("High density + saturation", 0.8, 0.0, 0.0, 1.5, 1000),
        ("QC fail (all bad)", 0.85, 0.4, 5.0, 1.5, 1000),
    ]

    results = []
    for name, confluence, debris, focus_offset, stain_scale, true_count in scenarios:
        state = injection.initialize_state(ctx, rng)

        # Compute quality
        q = injection.compute_segmentation_quality(
            confluence=confluence,
            debris_level=debris,
            focus_offset_um=focus_offset,
            stain_scale=stain_scale,
            rng=rng
        )

        # Distort count
        obs_count, merges, splits = injection.distort_cell_count(
            true_count=true_count,
            segmentation_quality=q,
            confluence=confluence,
            rng=rng
        )

        # QC gating
        qc_passed, warnings = injection.apply_qc_gating(q, confluence, debris)

        results.append({
            'scenario': name,
            'quality': q,
            'true_count': true_count,
            'obs_count': obs_count,
            'count_error': (obs_count - true_count) / true_count * 100,
            'merges': merges,
            'splits': splits,
            'qc_passed': qc_passed,
            'warnings': len(warnings)
        })

        print(f"{name:30s} | q={q:.2f} | true={true_count:4d} → obs={obs_count:4d} "
              f"| error={results[-1]['count_error']:+6.1f}% | QC={'✓' if qc_passed else '✗'}")

        if merges > 0:
            print(f"  → {merges} merge events (undercounts)")
        if splits > 0:
            print(f"  → {splits} split events (overcounts)")
        if not qc_passed:
            print(f"  → ⚠️  QC FAILED: {len(warnings)} warnings")

    print()
    print("KEY INSIGHTS:")
    print("- High density → merges → undercounts (loses cells)")
    print("- Low density → splits → overcounts (phantom cells)")
    print("- Multiple stressors compound (quality degrades)")
    print("- QC gating filters worst wells (survivorship bias)")
    print()

    return results


def demo_plate_map_error():
    """Demo plate map execution errors."""
    print("="*70)
    print("DEMO 2: Plate Map Execution Errors")
    print("="*70)
    print()

    injection = PlateMapErrorInjection(config={'error_probability': 1.0})  # Force error
    rng = np.random.default_rng(123)
    run_context = RunContext.sample(123)
    ctx = InjectionContext(simulated_time=0.0, run_context=run_context, plate_id="TEST_PLATE")

    # Generate different error types
    error_types = [
        PlateMapErrorType.COLUMN_SHIFT,
        PlateMapErrorType.ROW_SWAP,
        PlateMapErrorType.REAGENT_SWAP,
        PlateMapErrorType.DILUTION_REVERSED
    ]

    for error_type in error_types:
        # Force specific error type
        injection.error_type_weights = {error_type: 1.0}
        state = injection.initialize_state(ctx, rng)

        print(f"\nError Type: {error_type.value.upper()}")
        print(f"Description: {state.error_parameters.get('description', 'N/A')}")
        print(f"Forensic Signature: {state.forensic_signature}")

        # Show example transformations
        if error_type == PlateMapErrorType.COLUMN_SHIFT:
            shift = state.error_parameters['shift_amount']
            examples = [
                ("A5", "Anchor (Nocodazole)", {"compound": "Nocodazole", "dose_uM": 1.0}),
                ("D12", "Mid-dose", {"compound": "Compound_X", "dose_uM": 0.5}),
                ("H24", "Vehicle", {"compound": "DMSO", "dose_uM": 0.0}),
            ]
            print(f"\nColumn shift by {shift}:")
            for well_id, label, treatment in examples:
                actual_well, actual_treatment = injection.transform_well_assignment(
                    state, well_id, treatment
                )
                print(f"  {well_id} ({label}) → {actual_well} (shifted)")

        elif error_type == PlateMapErrorType.ROW_SWAP:
            row1 = state.error_parameters['row1']
            row2 = state.error_parameters['row2']
            print(f"\nRow swap: {row1} ↔ {row2}")
            print(f"  {row1}1 (HepG2) → {row2}1 (A549)")
            print(f"  {row2}1 (A549) → {row1}1 (HepG2)")
            print("  → Cell line assignment broken!")

        # Forensic report
        forensics = injection.generate_forensic_report(state)
        print(f"\nDetection Methods:")
        for method in forensics.get('detection_methods', []):
            print(f"  - {method}")

    print()
    print("KEY INSIGHTS:")
    print("- Errors are systematic (whole plate affected)")
    print("- Detectable with anchors + sentinels")
    print("- Agent MUST have sanity checks")
    print("- Without checks → confidently wrong conclusions")
    print()


def demo_combined_failure():
    """Demo combined segmentation + plate map error (nightmare scenario)."""
    print("="*70)
    print("DEMO 3: Combined Failures (Nightmare Scenario)")
    print("="*70)
    print()

    seg_injection = SegmentationFailureInjection()
    map_injection = PlateMapErrorInjection(config={'error_probability': 1.0})

    rng = np.random.default_rng(456)
    run_context = RunContext.sample(456)
    ctx = InjectionContext(simulated_time=48.0, run_context=run_context, plate_id="CURSED")

    # Segmentation failure
    seg_state = seg_injection.initialize_state(ctx, rng)
    q = seg_injection.compute_segmentation_quality(
        confluence=0.85,  # High
        debris_level=0.2,
        focus_offset_um=2.0,
        stain_scale=1.3,
        rng=rng
    )

    true_count = 1000
    obs_count, merges, splits = seg_injection.distort_cell_count(
        true_count, q, 0.85, rng
    )

    # Plate map error
    map_injection.error_type_weights = {PlateMapErrorType.COLUMN_SHIFT: 1.0}
    map_state = map_injection.initialize_state(ctx, rng)

    print("Scenario: High-density plate with column shift")
    print()
    print(f"Segmentation failure:")
    print(f"  Quality: q={q:.2f}")
    print(f"  Count: {true_count} → {obs_count} ({(obs_count-true_count)/true_count*100:+.1f}%)")
    print(f"  Merges: {merges}")
    print()
    print(f"Plate map error:")
    print(f"  Type: Column shift by {map_state.error_parameters['shift_amount']}")
    print(f"  Effect: Dose-response spatially shifted")
    print()
    print("Combined Effect:")
    print("  1. Agent sees wrong cell counts (segmentation)")
    print("  2. Agent looks at wrong wells (column shift)")
    print("  3. Anchors appear in wrong place")
    print("  4. Dose-response curve is broken")
    print("  5. Agent becomes CONFIDENTLY WRONG")
    print()
    print("Required Defenses:")
    print("  - Orthogonal count validation (confluence, ATP)")
    print("  - Anchor phenotype verification")
    print("  - Cross-plate consistency checks")
    print("  - Sentinel replicate clustering")
    print()


def visualize_segmentation_distortion(results):
    """Plot segmentation failure impact."""
    import pandas as pd

    df = pd.DataFrame(results)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # 1. Count error by quality
    ax = axes[0]
    scatter = ax.scatter(df['quality'], df['count_error'],
                        c=df['qc_passed'].map({True: 'green', False: 'red'}),
                        s=100, alpha=0.7)
    ax.axhline(0, color='black', linestyle='--', alpha=0.3)
    ax.set_xlabel('Segmentation Quality (q)', fontsize=12)
    ax.set_ylabel('Count Error (%)', fontsize=12)
    ax.set_title('Count Distortion vs Quality', fontsize=13, fontweight='bold')
    ax.grid(alpha=0.3)

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='green', alpha=0.7, label='QC Passed'),
        Patch(facecolor='red', alpha=0.7, label='QC Failed')
    ]
    ax.legend(handles=legend_elements, loc='upper left')

    # 2. Count bias direction
    ax = axes[1]
    colors = ['red' if e < 0 else 'blue' for e in df['count_error']]
    ax.barh(df['scenario'], df['count_error'], color=colors, alpha=0.7)
    ax.axvline(0, color='black', linestyle='-', linewidth=2)
    ax.set_xlabel('Count Error (%)', fontsize=12)
    ax.set_title('Bias Direction: Undercount vs Overcount', fontsize=13, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)

    # Add text annotations
    for i, (scenario, error) in enumerate(zip(df['scenario'], df['count_error'])):
        ax.text(error, i, f'{error:+.1f}%',
               ha='left' if error > 0 else 'right',
               va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig('segmentation_failure_demo.png', dpi=300, bbox_inches='tight')
    print("✓ Saved: segmentation_failure_demo.png")
    plt.show()


if __name__ == "__main__":
    print("\n")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*15 + "ADVERSARIAL NOISE SOURCES DEMO" + " "*23 + "║")
    print("║" + " "*68 + "║")
    print("║  Demonstrates how segmentation failure and plate map errors    ║")
    print("║  create 'confidently wrong' scenarios for epistemic agents     ║")
    print("╚" + "═"*68 + "╝")
    print()

    # Run demos
    seg_results = demo_segmentation_failure()
    demo_plate_map_error()
    demo_combined_failure()

    # Visualize
    print("Generating visualization...")
    visualize_segmentation_distortion(seg_results)

    print()
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print()
    print("These modules are NOT noise - they're adversarial measurement layers.")
    print()
    print("Segmentation Failure:")
    print("  - Changes sufficient statistics (count, features)")
    print("  - Creates survivorship bias via QC gating")
    print("  - Requires orthogonal validation to detect")
    print()
    print("Plate Map Errors:")
    print("  - Rare (2%) but catastrophic")
    print("  - Systematic (whole plate affected)")
    print("  - Detectable with anchors + sentinels")
    print()
    print("Combined:")
    print("  - Agent becomes confidently wrong")
    print("  - Tests if agent has sanity checks")
    print("  - Pedagogically essential")
    print()
