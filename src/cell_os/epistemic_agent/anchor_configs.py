"""
Anchor Configurations for Execution Integrity Checks.

This module defines expected anchor positions and dose directions per template.
Start narrow: only add templates you're actively using and compounds you KNOW are monotone.

Template names are extracted from design_id by convention:
- design_id = "baseline_replicates_cycle_5" → template_name = "baseline"
- design_id = "edge_test_abc123" → template_name = "edge"

Anchor specs enable detection of:
- Column shifts (all columns offset by N)
- Row swaps (two rows systematically swapped)
- Reagent swaps (compound identities in wrong wells)

Dose direction specs enable detection of:
- Dilution ladder reversed (high↔low doses swapped)
- Dose labels swapped
"""

from .integrity_checker import AnchorSpec


# =============================================================================
# Anchor Specifications (Expected Well Positions)
# =============================================================================

TEMPLATE_ANCHORS = {
    # Baseline replicates template: DMSO controls in center wells
    "baseline": {
        "DMSO": AnchorSpec(
            code="DMSO",
            expected_wells=(
                # Center wells (avoid edge effects)
                "C6", "C7", "D6", "D7",  # Center-left block
                "E6", "E7", "F6", "F7",  # Center-right block
            ),
            compound="DMSO",
            dose_uM=0.0,
            extra={"position": "center", "purpose": "negative control"},
        ),
    },

    # Edge test template: DMSO in both edge and center for comparison
    "edge": {
        "DMSO_center": AnchorSpec(
            code="DMSO_center",
            expected_wells=("C6", "D6", "E6", "F6"),
            compound="DMSO",
            dose_uM=0.0,
            extra={"position": "center"},
        ),
        "DMSO_edge": AnchorSpec(
            code="DMSO_edge",
            expected_wells=("A1", "A12", "H1", "H12"),  # Corners
            compound="DMSO",
            dose_uM=0.0,
            extra={"position": "edge"},
        ),
    },

    # TODO: Add more templates as needed
    # "dose": {...},  # Dose ladder template
    # "ldh": {...},   # LDH calibration template
    # "cp": {...},    # Cell Painting calibration template
}


# =============================================================================
# Dose Direction Specifications (Monotonicity Expectations)
# =============================================================================

# CONSERVATIVE: Only include compounds where monotonicity is EXPECTED for
# the chosen projection (viability-like scalars). Do NOT add compounds with
# complex dose-response curves or biphasic responses.

TEMPLATE_DOSE_DIRECTIONS = {
    # Baseline template: typically no dose ladders
    "baseline": {},

    # Edge template: typically no dose ladders
    "edge": {},

    # Dose ladder template: expect monotone stress responses
    # "dose": {
    #     "tBHQ": "decreasing",      # tBHQ reduces viability (oxidative stress)
    #     "CCCP": "decreasing",      # CCCP reduces viability (mitochondrial uncoupler)
    #     "rotenone": "decreasing",  # Rotenone reduces viability (complex I inhibitor)
    # },

    # TODO: Add more templates with known monotone compounds
}


# =============================================================================
# Helper: Get Anchor Config for Template
# =============================================================================

def get_anchor_config(template_name: str) -> dict:
    """
    Get anchor specifications for a template.

    Args:
        template_name: Template identifier (extracted from design_id)

    Returns:
        Dict of anchor specs, or empty dict if template not configured
    """
    return TEMPLATE_ANCHORS.get(template_name, {})


def get_dose_direction_config(template_name: str) -> dict:
    """
    Get dose direction specifications for a template.

    Args:
        template_name: Template identifier (extracted from design_id)

    Returns:
        Dict of dose directions, or empty dict if template not configured
    """
    return TEMPLATE_DOSE_DIRECTIONS.get(template_name, {})
