"""
Ground truth perimeter policy.

Defines forbidden keys and patterns that must never appear in agent-facing outputs.
This is an epistemic security boundary, not a biology constraint.

Split into:
- ALWAYS_FORBIDDEN: Hidden truth that should never leak (death labels, internal params)
- MODALITY_FORBIDDEN: Cross-modal privileged info (depends on assay type)
"""

import re
from typing import List, Dict, Any, Set, Tuple, Optional


# =============================================================================
# ALWAYS FORBIDDEN: Hidden truth that should never leak to agents
# =============================================================================

ALWAYS_FORBIDDEN_PATTERNS = [
    # Death attribution (ground truth labels)
    r"^death_mode$",
    r"^death_compound$",
    r"^death_confluence$",
    r"^death_unknown$",
    r"^death_.*",  # Catch future death_* fields

    # Latent stress states (should only be observable via morphology/readouts)
    r"^er_stress$",
    r"^mito_dysfunction$",
    r"^transport_dysfunction$",
    r"^stress_axis$",

    # Internal compound parameters (hidden from measurement)
    r"^ic50_uM$",
    r"^ec50_uM$",
    r"^hill_slope$",
    r"^potency_scalar$",
    r"^compound_meta$",
    r"^.*_meta$",  # Catch compound_meta, stress_meta, etc.

    # Internal exposure spine (use InjectionManager API instead)
    r"^compounds_uM$",  # Note: "compounds" dict at agent level might be OK
    r"^nutrients_mM$",  # Internal concentration tracking

    # Debug fields (unless explicitly in _debug_truth dict)
    r"^_debug_(?!truth$)",  # Blocks _debug_*, except _debug_truth

    # Bio random effects (latent heterogeneity parameters)
    r"^bio_random_effects$",
    r"^.*_shift_mult$",
]


# =============================================================================
# MODALITY FORBIDDEN: Cross-modal privileged info (context-dependent)
# =============================================================================

MODALITY_FORBIDDEN: Dict[str, List[str]] = {
    # Cell Painting cannot see cell count (cross-modal, use confluence proxy)
    "CellPaintingAssay": [
        r"^cell_count$",
        r"^capturable_cells$",  # scRNA-specific proxy
    ],

    # scRNA-seq cannot see raw cell count (use capturable_cells proxy)
    "scRNASeqAssay": [
        r"^cell_count$",
    ],

    # Add more modalities as needed
}


# =============================================================================
# ALLOWED (even though they look sensitive): Agent memory and choices
# =============================================================================

# These are NOT leaks because the agent chose them or should remember them:
# - dose_uM (agent-selected dose)
# - compounds (agent-selected treatments, at agent level not measurement level)
# - timepoint_h (agent-selected observation time)

# NOTE: Context matters. "compounds" in a measurement result dict is forbidden
# (treatment blinding), but "compounds" in an agent's action history is fine.


# =============================================================================
# Validation functions
# =============================================================================

def validate_no_ground_truth(
    obj: Any,
    patterns: List[str],
    path: str = "root",
    modality: Optional[str] = None,
) -> List[Tuple[str, str, type]]:
    """
    Recursively search for forbidden keys matching ground truth patterns.

    Args:
        obj: Object to validate (typically a measurement result dict)
        patterns: List of regex patterns to match against keys
        path: Current path for error reporting
        modality: Optional modality name (e.g., "CellPaintingAssay") for context-specific rules

    Returns:
        List of (key_path, matched_pattern, object_type) violations
    """
    violations = []

    # Combine always-forbidden with modality-specific patterns
    all_patterns = patterns.copy()
    if modality and modality in MODALITY_FORBIDDEN:
        all_patterns.extend(MODALITY_FORBIDDEN[modality])

    compiled_patterns = [re.compile(p) for p in all_patterns]

    def _recurse(obj: Any, path: str, inside_debug_truth: bool = False):
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}"

                # Exception: _debug_truth is allowed if it's a dict
                if key == "_debug_truth" and isinstance(value, dict):
                    # Recurse into it with exemption flag
                    _recurse(value, current_path, inside_debug_truth=True)
                    continue

                # Skip validation inside _debug_truth (intentionally contains ground truth)
                if inside_debug_truth:
                    _recurse(value, current_path, inside_debug_truth=True)
                    continue

                # Check if key matches any forbidden pattern
                for pattern in compiled_patterns:
                    if pattern.match(key):
                        violations.append((current_path, pattern.pattern, type(obj).__name__))
                        break  # One violation per key is enough

                # Recurse into value
                _recurse(value, current_path, inside_debug_truth)

        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                _recurse(item, f"{path}[{i}]")

    _recurse(obj, path)
    return violations


def format_violations(violations: List[Tuple[str, str, type]]) -> str:
    """Format violation list for error messages."""
    if not violations:
        return "No violations found."

    lines = ["Ground truth leaked in agent-facing output:"]
    for key_path, pattern, obj_type in violations:
        lines.append(f"  - {key_path} (matched pattern: {pattern}, container: {obj_type})")
    return "\n".join(lines)


def assert_no_ground_truth(
    obj: Any,
    patterns: Optional[List[str]] = None,
    modality: Optional[str] = None,
    message: str = ""
):
    """
    Assert that object contains no ground truth keys.

    Raises AssertionError if violations found.

    Args:
        obj: Object to validate
        patterns: Optional custom patterns (defaults to ALWAYS_FORBIDDEN_PATTERNS)
        modality: Optional modality name for context-specific rules
        message: Optional custom message prefix
    """
    if patterns is None:
        patterns = ALWAYS_FORBIDDEN_PATTERNS

    violations = validate_no_ground_truth(obj, patterns, modality=modality)

    if violations:
        error_msg = format_violations(violations)
        if message:
            error_msg = f"{message}\n{error_msg}"
        raise AssertionError(error_msg)
