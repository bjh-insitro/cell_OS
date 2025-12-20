"""Quick demo: Real posterior vs threshold classifier."""

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.hardware.run_context import RunContext
from cell_os.hardware.mechanism_posterior import (
    compute_mechanism_posterior,
    compute_nuisance_inflation,
    Mechanism
)

# Setup
ctx = RunContext.sample(seed=42)
vm = BiologicalVirtualMachine(seed=42, run_context=ctx)
vm.seed_vessel("test", "A549", 1e6)

# Baseline
baseline = vm.cell_painting_assay("test")
baseline_actin = baseline['morphology_struct']['actin']
baseline_mito = baseline['morphology_struct']['mito']
baseline_er = baseline['morphology_struct']['er']

# Treat with nocodazole (microtubule)
vm.treat_with_compound("test", "nocodazole", dose_uM=0.3, potency_scalar=0.8, toxicity_scalar=0.3)
vm.advance_time(12.0)

# Measure
result = vm.cell_painting_assay("test", batch_id='batch_A', plate_id='P001')
vessel = vm.vessel_states["test"]

actin_fold = result['morphology_struct']['actin'] / baseline_actin
mito_fold = result['morphology_struct']['mito'] / baseline_mito
er_fold = result['morphology_struct']['er'] / baseline_er

print(f"Observed: actin={actin_fold:.3f}×, mito={mito_fold:.3f}×, er={er_fold:.3f}×\n")

# OLD: Threshold
print("OLD (Threshold): actin > 1.4 → ", end="")
if actin_fold >= 1.4:
    print("MICROTUBULE")
else:
    print("UNKNOWN")
old_conf = 0.80 * max(0, 1 - vessel.get_artifact_inflated_mixture_width('transport_dysfunction', vm.simulated_time) / 0.3)
print(f"Confidence (heuristic): {old_conf:.3f}\n")

# NEW: Bayesian posterior
transport_width = vessel.get_mixture_width('transport_dysfunction')
artifact_contrib = vessel.get_artifact_inflated_mixture_width('transport_dysfunction', vm.simulated_time) - transport_width

nuisance_inflation = compute_nuisance_inflation(
    artifact_width=artifact_contrib,
    heterogeneity_width=transport_width,
    context_width=0.15,
    pipeline_width=0.10
)

posterior = compute_mechanism_posterior(
    actin_fold=actin_fold,
    mito_fold=mito_fold,
    er_fold=er_fold,
    nuisance_inflation=nuisance_inflation
)

print("NEW (Bayesian Posterior):")
print(posterior.summary())

print(f"\nKEY DIFFERENCE:")
print(f"Old: Binary yes/no with heuristic confidence")
print(f"New: Full distribution with entropy-based confidence (proper probability)")
print(f"\nOld conf: {old_conf:.3f} (not calibrated)")
print(f"New conf: {posterior.confidence:.3f} (entropy-based, proper)")
