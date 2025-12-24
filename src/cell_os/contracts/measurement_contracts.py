"""
Declarative measurement contracts for each assay type.

Defines allow-lists, forbidden reads, and output constraints for:
- Cell Painting (morphology imaging)
- LDH Viability (scalar readouts)
- scRNA-seq (transcriptomics)
"""

from .causal_contract import MeasurementContract

# Traversal mechanics that should be allowed across all contracts
TRAVERSAL = {
    "state.well_biology[*]",
    "state.well_position",
    "state.subpopulations.__iter__",
    "state.subpopulations.items",
    "state.subpopulations.keys",
    "state.subpopulations.values",
    "state.subpopulations.__len__",
    "state.subpopulations.get",
}

# Cell Painting: Morphology imaging assay
# Can read: viability, confluence, latent stress states, well biology
# Cannot read: cell_count (cross-modal), compounds (treatment blinding), death labels
CELL_PAINTING_CONTRACT = MeasurementContract(
    name="CellPaintingAssay",
    allowed_reads={
        # Observable biological state
        "state.viability",
        "state.confluence",

        # Latent stress states (morphology-first mechanisms)
        "state.er_stress",
        "state.mito_dysfunction",
        "state.transport_dysfunction",

        # Contact pressure (measurement confounder)
        "state.contact_pressure",

        # Subpopulation structure (for heterogeneity)
        "state.subpopulations[*][*]",

        # Persistent well biology
        "state.well_biology[*]",
        "state.well_position",

        # Temporal durations (NOT treatment identity)
        "state.time_since_last_perturbation_h",
        "state.time_since_last_feed_h",

        # Measurement artifacts
        "state.last_washout_time",
        "state.washout_artifact_until_time",
        "state.washout_artifact_magnitude",
        "state.plating_context",
        "state.plating_context[*]",
        "state.seed_time",

        # Debris and handling (for quality metrics)
        "state.debris_cells",
        "state.initial_cells",
        "state.cells_lost_to_handling",
        "state.edge_damage_score",

        # Well biology (persistent per-well latent factors)
        "state.well_biology",
        "state.well_biology[*].*",
        "state.well_biology.__iter__",
        "state.well_biology.__len__",

        # Metadata
        "state.vessel_id",
        "state.cell_line",
        "state.last_update_time",
    } | TRAVERSAL,

    forbidden_reads={
        "state.cell_count",  # Cross-modal independence
        "state.compounds",  # Treatment blinding
        "state.compound_meta",  # Treatment blinding
        "state.compound_start_time",  # Treatment blinding
        "state.death_mode",  # Ground truth label
        "state.death_compound",  # Ground truth label
        "state.death_confluence",  # Ground truth label
        "state.death_unknown",  # Ground truth label
    },

    forbidden_output_keys={
        "viability",  # Only structural morphology allowed
        "cell_count",  # Cross-modal
        "death_mode",  # Ground truth
        "death_compound",  # Ground truth
    },

    allow_debug_truth=False,  # Cell Painting is purely observational
)


# LDH Viability: Scalar biochemical assay
# Can read: cell_count (for scaling), viability, stress states
# Cannot read: compounds (treatment blinding), death labels (unless debug)
LDH_VIABILITY_CONTRACT = MeasurementContract(
    name="LDHViabilityAssay",
    allowed_reads={
        # Observable biological state
        "state.cell_count",  # LDH scales with biomass
        "state.viability",  # For signal scaling
        "state.confluence",

        # Latent stress states (for UPR/ATP/trafficking markers)
        "state.er_stress",
        "state.mito_dysfunction",
        "state.transport_dysfunction",

        # Measurement artifacts
        "state.last_washout_time",
        "state.washout_artifact_until_time",
        "state.washout_artifact_magnitude",

        # Death labels ONLY for debug truth output
        "state.death_mode",
        "state.death_compound",
        "state.death_confluence",
        "state.death_unknown",

        # Metadata
        "state.vessel_id",
        "state.cell_line",
    } | TRAVERSAL,

    forbidden_reads={
        "state.compounds",  # Treatment blinding
        "state.compound_meta",  # Treatment blinding
        "state.compound_start_time",  # Treatment blinding
    },

    forbidden_output_keys={
        # Ground truth only in _debug_truth
        "viability",
        "cell_count",
        "death_mode",
        "death_compound",
    },

    allow_debug_truth=True,  # LDH can output ground truth when debug enabled
)


# scRNA-seq: Transcriptomics assay
# Can read: capturable_cells (observable proxy), stress states
# Cannot read: cell_count (use capturable_cells), compounds, death labels
SCRNA_CONTRACT = MeasurementContract(
    name="scRNASeqAssay",
    allowed_reads={
        # Observable biological state
        "state.capturable_cells",  # Observable proxy (NOT cell_count)
        "state.viability",
        "state.confluence",

        # Subpopulation structure (for expression profiles)
        "state.subpopulations",
        "state.subpopulations[*][*]",

        # Latent stress states (for expression signatures)
        "state.er_stress",
        "state.mito_dysfunction",
        "state.transport_dysfunction",
        "state.contact_pressure",

        # Temporal durations
        "state.time_since_last_perturbation_h",

        # Measurement artifacts
        "state.last_washout_time",

        # Metadata
        "state.vessel_id",
        "state.cell_line",
    } | TRAVERSAL,

    forbidden_reads={
        "state.cell_count",  # Use capturable_cells proxy instead
        "state.compounds",  # Treatment blinding
        "state.compound_meta",  # Treatment blinding
        "state.compound_start_time",  # Treatment blinding
        "state.death_mode",  # Ground truth label
        "state.death_compound",  # Ground truth label
        "state.death_confluence",  # Ground truth label
        "state.death_unknown",  # Ground truth label
    },

    forbidden_output_keys={
        "cell_count",  # Use captured_cell_count instead
        "death_mode",
        "death_compound",
    },

    allow_debug_truth=False,  # scRNA is observational
)
