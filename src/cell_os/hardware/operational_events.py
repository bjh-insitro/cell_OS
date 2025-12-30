"""
Phase 2D.1: Operational Event Infrastructure

Provides order-independent, deterministic RNG substreams for operational events
(contamination, pipetting errors, instrument drift).

Key properties:
- Per-vessel outcomes keyed by lineage_id + domain (not creation order)
- RNG isolation from biology (rng_growth, rng_biology) and assays (rng_assay)
- Enabling/disabling events does not perturb other RNG streams
"""

import numpy as np
from typing import Optional


def get_operational_rng(run_seed: int, lineage_id: str, domain: str = "contamination") -> np.random.Generator:
    """
    Create order-independent RNG substream for operational events.

    Args:
        run_seed: Base seed for the run
        lineage_id: Unique vessel identifier (e.g., "Plate1_A01")
        domain: Event domain ("contamination", "pipetting", "instrument_drift")

    Returns:
        numpy Generator for this specific vessel + domain

    Design:
        Uses SeedSequence with spawn to create independent substreams.
        Each (lineage_id, domain) pair gets a deterministic substream that
        does not depend on vessel creation order or enabling/disabling other events.
    """
    # Hash lineage_id and domain to integers for seeding
    # Use FNV-1a hash (simple, deterministic, good distribution)
    def fnv1a_hash(s: str) -> int:
        hash_val = 2166136261  # FNV offset basis
        for byte in s.encode('utf-8'):
            hash_val ^= byte
            hash_val = (hash_val * 16777619) & 0xffffffff  # FNV prime, keep 32-bit
        return hash_val

    lineage_hash = fnv1a_hash(lineage_id)
    domain_hash = fnv1a_hash(domain)

    # Create SeedSequence with run_seed as parent
    # Spawn child with (lineage_hash, domain_hash) as entropy
    seed_seq = np.random.SeedSequence(run_seed, spawn_key=(lineage_hash, domain_hash))

    return np.random.default_rng(seed_seq)


def maybe_trigger_contamination(
    vessel,
    t_h: float,
    dt_h: float,
    run_seed: int,
    config: dict
) -> None:
    """
    Maybe trigger contamination event for this vessel in this timestep.

    Uses Poisson process in continuous time (not quantized to step boundaries).

    Args:
        vessel: VesselState object
        t_h: Current simulated time (hours)
        dt_h: Timestep duration (hours)
        run_seed: Base seed for the run
        config: contamination config dict

    Modifies:
        vessel.contaminated (bool)
        vessel.contamination_type (str)
        vessel.contamination_onset_h (float)
        vessel.contamination_severity (float)
        vessel.contamination_phase (str)
    """
    # Already contaminated - no retriggering
    if vessel.contaminated:
        return

    # Get config params
    rate_per_day = config.get('baseline_rate_per_vessel_day', 0.005)
    multiplier = config.get('rate_multiplier', 1.0)  # For stress-test regimes

    rate_per_h = (rate_per_day / 24.0) * multiplier

    # Poisson probability for this timestep
    p_event = 1.0 - np.exp(-rate_per_h * dt_h)

    # Get order-independent RNG for this vessel + timestep
    # CRITICAL: Include timestep in domain so each timestep gets independent draws
    # Without this, the RNG recreates with the same seed and produces identical draws!
    domain = f"contamination_t{int(t_h)}"
    rng = get_operational_rng(run_seed, vessel.vessel_id, domain=domain)

    # Draw trigger
    u_trigger = rng.uniform(0.0, 1.0)

    if u_trigger >= p_event:
        return  # No event this step

    # Event triggered - sample onset time within [t_h, t_h + dt_h)
    u_onset = rng.uniform(0.0, 1.0)
    onset_h = t_h + u_onset * dt_h

    # Sample contamination type
    type_probs = config.get('type_probs', {'bacterial': 0.5, 'fungal': 0.2, 'mycoplasma': 0.3})
    types = list(type_probs.keys())
    probs = np.array([type_probs[t] for t in types])
    probs = probs / probs.sum()  # Normalize

    contam_type = rng.choice(types, p=probs)

    # Sample severity (lognormal, mean=1.0)
    severity_cv = config.get('severity_lognormal_cv', 0.5)
    min_severity = config.get('min_severity', 0.25)
    max_severity = config.get('max_severity', 3.0)

    if severity_cv > 0:
        sigma = np.sqrt(np.log(1 + severity_cv**2))
        mu = -0.5 * sigma**2  # Mean of lognormal = exp(mu + sigma^2/2) = 1.0
        severity = float(rng.lognormal(mean=mu, sigma=sigma))
        severity = np.clip(severity, min_severity, max_severity)
    else:
        severity = 1.0

    # Set vessel state
    vessel.contaminated = True
    vessel.contamination_type = contam_type
    vessel.contamination_onset_h = float(onset_h)
    vessel.contamination_severity = float(severity)
    vessel.contamination_phase = "latent"  # Will progress in update_contamination_phase


def update_contamination_phase(vessel, t_h: float, config: dict) -> None:
    """
    Update contamination phase based on time since onset.

    Phases:
    - "latent": No effect yet (before latent_h)
    - "arrest": Growth arrested (between latent_h and latent_h + arrest_h)
    - "death": Progressive cell kill (after latent_h + arrest_h)

    Args:
        vessel: VesselState object
        t_h: Current simulated time (hours)
        config: contamination config dict

    Modifies:
        vessel.contamination_phase
    """
    if not vessel.contaminated:
        return

    tau = t_h - vessel.contamination_onset_h

    if tau < 0:
        # Shouldn't happen (onset in future), but handle gracefully
        vessel.contamination_phase = "latent"
        return

    # Get type-specific phase params
    phase_params = config.get('phase_params', {}).get(vessel.contamination_type, {})
    latent_h = phase_params.get('latent_h', 12.0)
    arrest_h = phase_params.get('arrest_h', 12.0)

    if tau < latent_h:
        vessel.contamination_phase = "latent"
    elif tau < latent_h + arrest_h:
        vessel.contamination_phase = "arrest"
    else:
        vessel.contamination_phase = "death"


def get_contamination_growth_multiplier(vessel, config: dict) -> float:
    """
    Get growth rate multiplier due to contamination.

    Returns:
        Multiplier for growth rate (1.0 = no effect, 0.05 = severe arrest)
    """
    if not vessel.contaminated:
        return 1.0

    phase = vessel.contamination_phase

    if phase == "latent":
        return 1.0  # No effect during latent phase

    # Arrest or death phase - apply growth arrest
    growth_arrest_multiplier = config.get('growth_arrest_multiplier', 0.05)

    # Optionally scale by severity
    severity = vessel.contamination_severity
    return float(growth_arrest_multiplier * severity) if severity < 1.0 else growth_arrest_multiplier


def get_contamination_death_hazard(vessel, config: dict) -> float:
    """
    Get death hazard rate (per hour) due to contamination.

    Returns:
        Hazard rate in per-hour units (0.0 if not in death phase)
    """
    if not vessel.contaminated:
        return 0.0

    phase = vessel.contamination_phase

    if phase != "death":
        return 0.0  # No death hazard until death phase

    # Get type-specific death rate
    phase_params = config.get('phase_params', {}).get(vessel.contamination_type, {})
    death_rate_per_h = phase_params.get('death_rate_per_h', 0.1)

    # Scale by severity
    severity = vessel.contamination_severity

    return float(death_rate_per_h * severity)


def get_contamination_morphology_shift(vessel, config: dict) -> float:
    """
    Get morphology shift magnitude due to contamination.

    Returns magnitude multiplier for channel-specific shifts.
    Shift is zero during latent phase, scales with severity afterward.

    Returns:
        Shift magnitude (0.0 if latent, severity-scaled otherwise)
    """
    if not vessel.contaminated:
        return 0.0

    phase = vessel.contamination_phase

    if phase == "latent":
        return 0.0  # No morphology shift during latent phase

    # Base shift strength from config
    base_strength = config.get('morphology_signature_strength', 1.0)

    # Scale by severity
    severity = vessel.contamination_severity

    return float(base_strength * severity)


# Contamination type-specific morphology signatures (channel shifts)
# Positive = signal increase, negative = signal decrease
# These are deterministic, no RNG (detectable patterns for diagnosis)
CONTAMINATION_MORPHOLOGY_SIGNATURES = {
    'bacterial': {
        'er': 0.3,        # Moderate ER stress (protein synthesis disruption)
        'mito': 0.5,      # Moderate mito signal (metabolic stress)
        'nucleus': -0.2,  # Nuclear condensation
        'actin': -0.4,    # Cytoskeleton disruption
        'rna': 0.6,       # High RNA signal (bacteria visible in well)
    },
    'fungal': {
        'er': 0.2,        # Mild ER stress
        'mito': 0.3,      # Mild mito stress
        'nucleus': -0.1,  # Slight nuclear condensation
        'actin': 0.8,     # Strong actin signal (fungal hyphae)
        'rna': 0.4,       # Moderate RNA signal (fungi visible)
    },
    'mycoplasma': {
        'er': 0.1,        # Subtle ER stress
        'mito': 0.2,      # Subtle mito stress
        'nucleus': 0.0,   # No nuclear change
        'actin': -0.1,    # Mild cytoskeleton disruption
        'rna': 0.2,       # Subtle RNA signal (mycoplasma cryptic)
    },
}
