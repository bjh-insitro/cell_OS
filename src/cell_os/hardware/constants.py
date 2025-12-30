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

# Pedagogy flag: Continuous subthreshold cost (prevents threshold surfing)
ENABLE_CONTINUOUS_SUBTHRESHOLD_COST = True

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

# Subthreshold cost parameter (growth mode)
# Growth penalty at full stress (S=1.0): 1.0 - SUBTHRESHOLD_STRESS_GROWTH_PENALTY = 50% growth at S=1.0
# At S=0.65 (high subthreshold): ~67.5% growth rate
# At S=0.3 (mild): ~85% growth rate
SUBTHRESHOLD_STRESS_GROWTH_PENALTY = 0.50  # 50% growth reduction at S=1.0

# Stress dynamics numerical stability (dt-independence)
# Stress mechanisms substep internally to avoid forward Euler integration errors
# This prevents "coarse actions change physics" exploit after stress→growth coupling
INTERNAL_STRESS_TIMESTEP_H = 1.0  # Internal timestep for stress ODEs (hours)

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

# ER damage memory dynamics (adaptive history trace)
# Damage accumulates from stress and repairs slowly, creating persistent memory
# that makes rechallenge responses history-dependent (prevents "washout resets everything")
# FIX: Increased K_ACCUM 3× for reachability, convex boost (D²) for compulsory tracking
ER_DAMAGE_K_ACCUM = 0.06  # Accumulation rate (per hour): dD/dt += k_accum * S
ER_DAMAGE_K_REPAIR = 0.0289  # Repair rate (per hour): dD/dt -= k_repair * D  (24h half-life)
ER_DAMAGE_BOOST = 5.0  # Convex induction boost: k_on *= (1 + boost * D²), makes damage mechanistically compulsory
ER_DAMAGE_RECOVERY_SLOW = 1.0  # Recovery slowdown: k_off /= (1 + slow * D), damage visible in trajectory slopes

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

# Synergistic coupling (pedagogy: combinations are risky)
# Multiplicative hazard interaction when multiple stress axes are elevated
# Teaches "multi-target interventions create synergy, not just additive badness"
ENABLE_SYNERGISTIC_COUPLING = True
SYNERGY_GATE_S0 = 0.2  # Stress threshold below which synergy doesn't activate (suppresses noise)
SYNERGY_K_HAZARD = 0.035  # Synergy hazard coefficient (per hour): h = k * gate(S_er) * gate(S_mito)

# Death accounting epsilon (for conservation law enforcement)
DEATH_EPS = 1e-9

# Tracked death fields (allowlist for _propose_hazard validation)
# These are the ONLY fields that contribute to death accounting
# Any typo or new field must be explicitly added here AND to conservation checks
TRACKED_DEATH_FIELDS = frozenset({
    "death_compound",
    "death_starvation",
    "death_mitotic_catastrophe",
    "death_er_stress",
    "death_mito_dysfunction",
    "death_confluence",
    "death_contamination",  # Phase 2D.1: Operational events (bacterial/fungal contamination)
    "death_unknown",  # Known unknowns (seeding stress, handling mishaps)
    "death_committed_er",  # Phase 2A.1: Stochastic ER commitment (post-commitment hazard)
    "death_committed_mito",  # Phase 2A.2: Stochastic mito commitment (post-commitment hazard)
    # death_unattributed is NOT in this list (it's computed, not proposed)
    # death_transport_dysfunction is NOT in this list (Phase 2 stub, no hazard in v1)
})
