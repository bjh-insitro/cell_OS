"""
Reusable Hypothesis strategies for cell_OS property-based testing.

This module provides domain-specific strategies that generate realistic
test inputs for the biological simulation. Use these to write property-based
tests that explore edge cases automatically.

Usage:
    from tests.strategies import treatment_protocol, seed_strategy

    @given(protocol=treatment_protocol(), seed=seed_strategy)
    def test_my_property(protocol, seed):
        ...
"""

from typing import Dict, Any, List

from hypothesis import strategies as st
from hypothesis.strategies import composite, SearchStrategy


# =============================================================================
# Basic domain strategies
# =============================================================================

# Seeds for deterministic simulation
seed_strategy: SearchStrategy[int] = st.integers(min_value=0, max_value=2**32 - 1)

# Dose ranges (in µM)
low_dose: SearchStrategy[float] = st.floats(
    min_value=0.001, max_value=1.0, allow_nan=False
)
reasonable_dose: SearchStrategy[float] = st.floats(
    min_value=0.01, max_value=100.0, allow_nan=False
)
high_dose: SearchStrategy[float] = st.floats(
    min_value=50.0, max_value=1000.0, allow_nan=False
)
extreme_dose: SearchStrategy[float] = st.floats(
    min_value=100.0, max_value=10000.0, allow_nan=False
)

# Time ranges (in hours)
short_time: SearchStrategy[float] = st.floats(
    min_value=0.1, max_value=4.0, allow_nan=False
)
reasonable_time: SearchStrategy[float] = st.floats(
    min_value=0.5, max_value=72.0, allow_nan=False
)
long_time: SearchStrategy[float] = st.floats(
    min_value=24.0, max_value=168.0, allow_nan=False  # Up to 1 week
)

# Viability (0-1 fraction)
viability: SearchStrategy[float] = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False
)
partial_viability: SearchStrategy[float] = st.floats(
    min_value=0.3, max_value=0.95, allow_nan=False
)

# Cell counts
cell_count: SearchStrategy[int] = st.integers(min_value=1000, max_value=10_000_000)


# =============================================================================
# Compound and cell line strategies
# =============================================================================

# Compounds organized by mechanism of action
# Available in simulation: tBHQ, H2O2, tunicamycin, thapsigargin, etoposide,
# cccp/CCCP, oligomycin_a/oligomycin, rotenone, two_deoxy_d_glucose,
# mg132/MG132, nocodazole, paclitaxel, cisplatin, doxorubicin, staurosporine, tbhp

er_stress_compounds: SearchStrategy[str] = st.sampled_from([
    "tunicamycin", "thapsigargin", "tBHQ"
])

mito_dysfunction_compounds: SearchStrategy[str] = st.sampled_from([
    "rotenone", "oligomycin", "cccp"
])

oxidative_stress_compounds: SearchStrategy[str] = st.sampled_from([
    "H2O2", "tBHQ", "tbhp"
])

cytotoxic_compounds: SearchStrategy[str] = st.sampled_from([
    "staurosporine", "paclitaxel", "nocodazole", "cisplatin", "doxorubicin"
])

# All testable compounds (excluding DMSO control)
all_compounds: SearchStrategy[str] = st.sampled_from([
    "tBHQ", "H2O2", "tunicamycin", "thapsigargin",
    "rotenone", "staurosporine", "paclitaxel", "nocodazole",
    "oligomycin", "etoposide", "cisplatin"
])

# Cell lines
cell_lines: SearchStrategy[str] = st.sampled_from(["A549", "HepG2", "HEK293"])


# =============================================================================
# Composite strategies
# =============================================================================

@composite
def treatment_protocol(
    draw: st.DrawFn,
    compound_strategy: SearchStrategy[str] = all_compounds,
    dose_strategy: SearchStrategy[float] = reasonable_dose,
    time_strategy: SearchStrategy[float] = reasonable_time,
) -> Dict[str, Any]:
    """Generate a treatment protocol.

    Returns:
        Dict with keys: compound, dose_uM, time_hours
    """
    return {
        "compound": draw(compound_strategy),
        "dose_uM": draw(dose_strategy),
        "time_hours": draw(time_strategy),
    }


@composite
def treatment_sequence(
    draw: st.DrawFn,
    min_treatments: int = 1,
    max_treatments: int = 4,
) -> List[Dict[str, Any]]:
    """Generate a sequence of treatments.

    Useful for testing conservation under complex protocols.

    Returns:
        List of treatment protocols
    """
    n = draw(st.integers(min_value=min_treatments, max_value=max_treatments))
    return [draw(treatment_protocol()) for _ in range(n)]


@composite
def well_id(draw: st.DrawFn, plate_id: str = "P1") -> str:
    """Generate a valid well ID.

    Format: {plate_id}_{row}{col:02d}
    Example: P1_A01, P1_B12
    """
    row = draw(st.sampled_from("ABCDEFGH"))
    col = draw(st.integers(min_value=1, max_value=12))
    return f"{plate_id}_{row}{col:02d}"


@composite
def well_ids(
    draw: st.DrawFn,
    min_wells: int = 1,
    max_wells: int = 96,
    plate_id: str = "P1",
) -> List[str]:
    """Generate a list of unique well IDs."""
    n = draw(st.integers(min_value=min_wells, max_value=max_wells))
    # Generate unique wells
    wells = set()
    while len(wells) < n:
        wells.add(draw(well_id(plate_id=plate_id)))
    return sorted(wells)


@composite
def seeding_config(
    draw: st.DrawFn,
    cell_line_strategy: SearchStrategy[str] = cell_lines,
    viability_strategy: SearchStrategy[float] = partial_viability,
) -> Dict[str, Any]:
    """Generate a cell seeding configuration.

    Returns:
        Dict with keys: cell_line, cell_count, initial_viability
    """
    return {
        "cell_line": draw(cell_line_strategy),
        "cell_count": draw(cell_count),
        "initial_viability": draw(viability_strategy),
    }


# =============================================================================
# Stress-testing strategies (edge cases)
# =============================================================================

@composite
def boundary_viability(draw: st.DrawFn) -> float:
    """Generate viability at boundaries (0, 1, or very close)."""
    choice = draw(st.integers(min_value=0, max_value=4))
    if choice == 0:
        return 0.0
    elif choice == 1:
        return 1.0
    elif choice == 2:
        # Very close to 0
        return draw(st.floats(min_value=1e-9, max_value=1e-6))
    elif choice == 3:
        # Very close to 1
        return draw(st.floats(min_value=1.0 - 1e-6, max_value=1.0 - 1e-9))
    else:
        # Normal range
        return draw(viability)


@composite
def extreme_protocol(draw: st.DrawFn) -> Dict[str, Any]:
    """Generate an extreme treatment protocol for stress testing.

    High dose + potent compound + long time = near-total kill scenario.
    """
    return {
        "compound": draw(cytotoxic_compounds),
        "dose_uM": draw(extreme_dose),
        "time_hours": draw(long_time),
    }


# =============================================================================
# RNG testing strategies
# =============================================================================

@composite
def seed_pair(draw: st.DrawFn) -> tuple:
    """Generate a pair of seeds for determinism testing.

    Returns (seed1, seed2) where seed1 == seed2 (for identical results)
    or seed1 != seed2 (for different results).
    """
    seed1 = draw(seed_strategy)
    same = draw(st.booleans())
    if same:
        return (seed1, seed1)
    else:
        # Ensure different
        seed2 = draw(seed_strategy.filter(lambda x: x != seed1))
        return (seed1, seed2)


@composite
def rng_stream_config(draw: st.DrawFn) -> Dict[str, int]:
    """Generate RNG configuration with separate streams.

    Returns dict with keys: biology_seed, assay_seed, ops_seed
    """
    base = draw(seed_strategy)
    return {
        "biology_seed": base,
        "assay_seed": base + 1000000,  # Different stream
        "ops_seed": base + 2000000,    # Different stream
    }
