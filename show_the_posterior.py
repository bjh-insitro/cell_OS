"""
Uncomfortable truth: show what "mechanism inference" actually is.

Current system:
- Binary threshold: actin_fold >= 1.4 → "microtubule"
- Confidence: variance-based heuristic (not a probability)
- No posterior over mechanisms (just nearest neighbor)

This will make it obvious whether we're doing inference or cosplay.
"""

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext
import numpy as np


def show_current_mechanism_inference():
    """Show what we actually do (threshold + variance, not posterior)."""

    print("=== Current 'Mechanism Inference' (Threshold Classifier) ===\n")

    # Setup
    ctx = RunContext.sample(seed=42)
    vm = BiologicalVirtualMachine(seed=42, run_context=ctx)
    vm.seed_vessel("test", "A549", 1e6)

    # Baseline
    baseline = vm.cell_painting_assay("test")
    baseline_actin = baseline['morphology_struct']['actin']
    baseline_mito = baseline['morphology_struct']['mito']
    baseline_er = baseline['morphology_struct']['er']

    print(f"Baseline (no compound):")
    print(f"  Actin: {baseline_actin:.1f}")
    print(f"  Mito: {baseline_mito:.1f}")
    print(f"  ER: {baseline_er:.1f}")

    # Treat with nocodazole (microtubule)
    vm.treat_with_compound("test", "nocodazole", dose_uM=0.3, potency_scalar=0.8, toxicity_scalar=0.3)
    vm.advance_time(12.0)

    # Measure at 12h
    result = vm.cell_painting_assay("test", batch_id='batch_A', plate_id='P001')
    vessel = vm.vessel_states["test"]

    actin_struct = result['morphology_struct']['actin']
    mito_struct = result['morphology_struct']['mito']
    er_struct = result['morphology_struct']['er']

    actin_fold = actin_struct / baseline_actin
    mito_fold = mito_struct / baseline_mito
    er_fold = er_struct / baseline_er

    print(f"\n@ 12h (after nocodazole):")
    print(f"  Actin: {actin_struct:.1f} ({actin_fold:.2f}× baseline)")
    print(f"  Mito: {mito_struct:.1f} ({mito_fold:.2f}× baseline)")
    print(f"  ER: {er_struct:.1f} ({er_fold:.2f}× baseline)")

    # Current "mechanism inference": binary threshold
    threshold = 1.4
    mechanism_hit = actin_fold >= threshold

    print(f"\n--- Current 'Inference' (Threshold Classifier) ---")
    print(f"Actin fold: {actin_fold:.3f}")
    print(f"Threshold: {threshold:.3f}")
    print(f"Mechanism hit: {mechanism_hit}")
    print(f"Classification: {'MICROTUBULE' if mechanism_hit else 'UNKNOWN'}")

    # Get mixture widths
    transport_width = vessel.get_mixture_width('transport_dysfunction')
    er_width = vessel.get_mixture_width('er_stress')
    mito_width = vessel.get_mixture_width('mito_dysfunction')

    print(f"\nMixture widths (biological heterogeneity):")
    print(f"  Transport dysfunction: {transport_width:.4f}")
    print(f"  ER stress: {er_width:.4f}")
    print(f"  Mito dysfunction: {mito_width:.4f}")

    # Current "confidence": variance-based heuristic
    inflated_width = vessel.get_artifact_inflated_mixture_width('transport_dysfunction', vm.simulated_time)
    confidence_heuristic = 0.80 * max(0, 1 - inflated_width / 0.3)

    print(f"\nCurrent 'Confidence' (Variance Heuristic):")
    print(f"  Total width (artifact-inflated): {inflated_width:.4f}")
    print(f"  Confidence: {confidence_heuristic:.3f}")
    print(f"  Formula: 0.80 * (1 - {inflated_width:.4f} / 0.3)")

    print(f"\n{'='*80}")
    print("WHAT'S MISSING:")
    print("="*80)
    print("1. No posterior over mechanisms [P(microtubule), P(ER), P(mito)]")
    print("2. No likelihood model: P(actin_fold | mechanism)")
    print("3. No marginalization over nuisance: P(mech | data, integrated over context)")
    print("4. Confidence is NOT a probability (not calibrated)")
    print("5. Just doing: 'is actin > 1.4? → yes/no'")

    print(f"\nThis is nearest-neighbor with variance awareness, not Bayesian inference.")

    return {
        'actin_fold': actin_fold,
        'mito_fold': mito_fold,
        'er_fold': er_fold,
        'mechanism_hit': mechanism_hit,
        'confidence_heuristic': confidence_heuristic,
        'transport_width': transport_width,
        'er_width': er_width,
        'mito_width': mito_width
    }


def show_what_real_posterior_needs():
    """Show what a proper mechanism posterior would look like."""

    print("\n\n" + "="*80)
    print("WHAT A REAL POSTERIOR LOOKS LIKE:")
    print("="*80)

    print("""
For 3 mechanisms (microtubule, ER, mito) and observed features:

1. Likelihood model (per mechanism):
   P(actin, mito, ER | mechanism, context, artifacts)

   This requires:
   - Expected signature per mechanism (mean response)
   - Variance model (biological + artifact + context)
   - Correlation structure (actin/mito coupling)

2. Prior over mechanisms:
   P(mechanism | compound_history, dose)

   This could be:
   - Uniform: P(mech) = 1/3 for each
   - Or informed: if compound known, prior=0.9 for true axis

3. Posterior via Bayes:
   P(mechanism | actin, mito, ER) ∝ P(actin, mito, ER | mechanism) * P(mechanism)

   Output:
   {
       'microtubule': 0.72,  # 72% posterior probability
       'er_stress': 0.18,    # 18%
       'mitochondrial': 0.10  # 10%
   }

4. Confidence as entropy:
   H = -Σ p_i log(p_i)

   Low entropy (peaked posterior) = high confidence
   High entropy (flat posterior) = low confidence

   This is a REAL probability measure.

5. Calibration test:
   - Sample 100 runs
   - When posterior says P(microtubule)=0.72, true mech is microtubule 72% of time
   - Plot calibration curve: predicted vs empirical
   - Compute ECE (expected calibration error)
   - Compute Brier score

Currently we have NONE of this.
    """)


if __name__ == "__main__":
    result = show_current_mechanism_inference()
    show_what_real_posterior_needs()

    print("\n\n" + "="*80)
    print("VERDICT: NEAREST-NEIGHBOR COSPLAY")
    print("="*80)
    print("We're doing threshold classification with variance awareness.")
    print("Not Bayesian inference.")
    print("\nTo fix: implement proper likelihood + posterior + calibration.")
