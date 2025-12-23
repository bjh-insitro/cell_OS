"""
Calibration plate constants for Cycle 0 instrument shape learning.

FROZEN DECISION (2025-12-22):
The canonical calibration plate for Cycle 0 is CAL_384_RULES_WORLD_v4.

This plate was selected because:
- Sparse checkerboard pattern enables detection of local spatial confounding
- CV islands provide replicate precision estimates
- Edge vs center coverage characterizes spatial bias
- Designed for "learning the shape of the instrument" not biology

If this changes, it's a versioned architectural decision.
"""

# PLATE CLASS CONSTANTS
# These define the two fundamental plate types
CALIBRATION_PLATE = "CAL_384_RULES_WORLD_v4"  # For earning instrument trust
SCREENING_PLATE = "CAL_384_RULES_WORLD_v3"     # For biology (requires trust first)

# CYCLE 0 CANONICAL PLATE
# The agent MUST run this plate before any biology
CYCLE0_PLATE_ID = CALIBRATION_PLATE

# TRUST THRESHOLDS
# Thresholds for earning noise gate from instrument shape summary
# These are config, not vibes.
NOISE_SIGMA_THRESHOLD = 0.15        # Max acceptable noise level (CV)
EDGE_EFFECT_THRESHOLD = 0.10        # Max acceptable edge bias (relative)
SPATIAL_RESIDUAL_THRESHOLD = 0.06   # Moran's I effect size floor (with p < 0.01)
REPLICATE_PRECISION_THRESHOLD = 0.85 # Min acceptable replicate agreement (correlation)
CHANNEL_COUPLING_THRESHOLD = 0.20   # Max acceptable spurious channel correlation

# GATE STATUS VALUES
GATE_LOST = "lost"
GATE_EARNED = "earned"
GATE_DEGRADED = "degraded"
