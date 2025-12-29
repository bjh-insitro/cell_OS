"""
Shared constants for biological simulation.

Feature flags and parameters used across BiologicalVirtualMachine and assay simulators.
"""

###############################################################################
# Mechanism feature flags (keep simple, no config plumbing needed yet)
###############################################################################
ENABLE_NUTRIENT_DEPLETION = True
ENABLE_MITOTIC_CATASTROPHE = True
ENABLE_ER_STRESS = True
ENABLE_MITO_DYSFUNCTION = True
ENABLE_TRANSPORT_DYSFUNCTION = True

# Nutrient defaults (DMEM-ish, intentionally coarse)
DEFAULT_MEDIA_GLUCOSE_mM = 25.0
DEFAULT_MEDIA_GLUTAMINE_mM = 4.0

# Nutrient stress thresholds (below these, stress begins)
GLUCOSE_STRESS_THRESHOLD_mM = 5.0
GLUTAMINE_STRESS_THRESHOLD_mM = 1.0

# Max starvation death intensity (per hour) at full depletion
MAX_STARVATION_RATE_PER_H = 0.05

# Mitosis model
DEFAULT_DOUBLING_TIME_H = 24.0

# Feeding costs (prevents "feed every hour" dominant strategy)
ENABLE_FEEDING_COSTS = True
FEEDING_TIME_COST_H = 0.25  # Operator time per feed operation
FEEDING_CONTAMINATION_RISK = 0.002  # 0.2% chance of introducing contamination

# Intervention costs (Phase 3: washout costs prevent free micro-cycling)
ENABLE_INTERVENTION_COSTS = True
WASHOUT_TIME_COST_H = 0.25  # Operator time per washout operation
WASHOUT_CONTAMINATION_RISK = 0.001  # 0.1% chance (lower than feeding)
WASHOUT_INTENSITY_PENALTY = 0.05  # 5% intensity drop for 12h (measurement artifact)
WASHOUT_INTENSITY_RECOVERY_H = 12.0  # Recovery time for intensity penalty

# ER stress dynamics (morphology-first, death-later mechanism)
ER_STRESS_K_ON = 0.25  # Induction rate constant (per hour)
ER_STRESS_K_OFF = 0.05  # Decay rate constant (per hour)
ER_STRESS_DEATH_THETA = 0.7  # Stress level for death onset
ER_STRESS_DEATH_WIDTH = 0.08  # Sigmoid width for death transition
ER_STRESS_H_MAX = 0.03  # Max death hazard (per hour) at full stress
ER_STRESS_MORPH_ALPHA = 0.5  # Morphology scaling factor (50% bump at S=1)

# Mito dysfunction dynamics (morphology-first, death-later mechanism)
MITO_DYSFUNCTION_K_ON = 0.25  # Induction rate constant (per hour)
MITO_DYSFUNCTION_K_OFF = 0.05  # Decay rate constant (per hour)
MITO_DYSFUNCTION_DEATH_THETA = 0.6  # Stress level for death onset (lower than ER)
MITO_DYSFUNCTION_DEATH_WIDTH = 0.1  # Sigmoid width for death transition
MITO_DYSFUNCTION_H_MAX = 0.05  # Max death hazard (per hour) at full stress (nastier than ER)
MITO_DYSFUNCTION_MORPH_ALPHA = 0.4  # Morphology scaling factor (40% loss at S=1)

# Transport dysfunction dynamics (morphology-first, no death hazard in v1)
TRANSPORT_DYSFUNCTION_K_ON = 0.35  # Induction rate constant (per hour) - faster than ER/mito
TRANSPORT_DYSFUNCTION_K_OFF = 0.08  # Decay rate constant (per hour) - faster recovery
TRANSPORT_DYSFUNCTION_MORPH_ALPHA = 0.6  # Morphology scaling factor (60% increase at S=1)

# Phase 4 Option 3: Cross-talk (transport → mito coupling)
# Prolonged transport dysfunction induces secondary mito dysfunction
ENABLE_TRANSPORT_MITO_COUPLING = True
TRANSPORT_MITO_COUPLING_DELAY_H = 18.0  # Delay before coupling activates
TRANSPORT_MITO_COUPLING_THRESHOLD = 0.6  # Transport dysfunction must exceed this
TRANSPORT_MITO_COUPLING_RATE = 0.02  # Mito dysfunction induction rate (per hour)

# Death accounting epsilon (for conservation law enforcement)
DEATH_EPS = 1e-9

# Tracked death fields (allowlist for _propose_hazard validation)
# These are the ONLY fields that contribute to death accounting
# Any typo or new field must be explicitly added here AND to conservation checks
TRACKED_DEATH_FIELDS = {
    "death_compound",
    "death_starvation",
    "death_mitotic_catastrophe",
    "death_er_stress",
    "death_mito_dysfunction",
    "death_confluence",
    "death_unknown",  # Known unknowns (seeding stress, contamination)
    "death_committed_er",  # Phase 2A.1: Stochastic ER commitment (post-commitment hazard)
    # death_unattributed is NOT in this list (it's computed, not proposed)
    # death_transport_dysfunction is NOT in this list (Phase 2 stub, no hazard in v1)
}
