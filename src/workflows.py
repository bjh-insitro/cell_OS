from dataclasses import dataclass
from typing import List
from src.unit_ops import UnitOp, ParametricOps, AssayRecipe


@dataclass
class Process:
    name: str
    ops: List[UnitOp]


@dataclass
class Workflow:
    name: str
    processes: List[Process]

    @property
    def all_ops(self) -> List[UnitOp]:
        ops: List[UnitOp] = []
        for p in self.processes:
            ops.extend(p.ops)
        return ops


def workflow_from_assay_recipe(recipe: AssayRecipe) -> Workflow:
    """
    Adapt an AssayRecipe (layered ops with counts) into a canonical Workflow.

    - Each recipe layer becomes a Process.
    - Each (UnitOp, count) entry is expanded into `count` UnitOp instances
      in that Process's ops list.
    - Bare UnitOp entries (no count) are preserved as a single op.

    This gives optimizers / renderers one canonical interface, even if the
    underlying recipe schema evolves.
    """
    processes: List[Process] = []

    for layer_name, entries in recipe.layers.items():
        ops: List[UnitOp] = []

        for entry in entries:
            # Support both (UnitOp, count) and bare UnitOp
            if isinstance(entry, tuple) and len(entry) == 2:
                op, count = entry
                try:
                    n = int(count)
                except (TypeError, ValueError):
                    n = 1
                n = max(1, n)

                for _ in range(n):
                    ops.append(op)
            else:
                # Already a UnitOp, or something UnitOp-like
                ops.append(entry)

        processes.append(Process(name=layer_name, ops=ops))

    return Workflow(name=recipe.name, processes=processes)


class WorkflowBuilder:
    def __init__(self, ops_engine: ParametricOps):
        self.ops = ops_engine

    def build_zombie_posh(self) -> Workflow:
        """
        Defines the complete Zombie POSH Screening Workflow.
        Starts from gRNA library design through to phenotypic readout.
        """
        processes: List[Process] = []

        # Process 1: Library Construction
        # Gene Selection → gRNA Design → Cloning → NGS Verification → LV Production
        library_construction_ops: List[UnitOp] = []
        try:
            # 1. Select Genes to Target (Computational)
            # library_construction_ops.append(self.ops.op_select_genes(...))  # TODO: Implement

            # 2. Design gRNAs (Computational - uses existing op_design_guides)
            # Note: This requires a LibraryDesign object, skipping for now
            # library_construction_ops.append(self.ops.op_design_guides(...))  # TODO: Add proper params

            # 3. Clone Oligo Pools into LV Backbone
            # This encompasses: Oligo synthesis (outsourced) → Golden Gate → Transformation → Plasmid Prep
            library_construction_ops.append(
                self.ops.op_golden_gate_assembly("tube_15ml", num_reactions=96)
            )
            library_construction_ops.append(
                self.ops.op_transformation("tube_15ml", num_reactions=96)
            )
            library_construction_ops.append(
                self.ops.op_plasmid_prep("flask_t75", scale="maxi")
            )

            # 4. NGS Verification
            library_construction_ops.append(self.ops.op_ngs_verification("tube_15ml"))

            # 5. LV Particle Production
            library_construction_ops.append(
                self.ops.op_transfect_hek293t("flask_t175", vessel_type="flask_t175")
            )
            library_construction_ops.append(self.ops.op_harvest_virus("flask_t175"))
        except Exception as e:
            raise Exception(f"Failed in Library Construction: {e}")
        processes.append(Process("Library Construction", library_construction_ops))

        # Process 2: Cell Line Preparation
        # Thaw → Expand → Transduce → Select → Expand
        cell_prep_ops: List[UnitOp] = []
        try:
            cell_prep_ops.append(self.ops.op_thaw("flask_t75"))
            cell_prep_ops.append(self.ops.op_passage("flask_t75"))
            cell_prep_ops.append(
                self.ops.op_transduce("flask_t75", method="spinoculation")
            )
            cell_prep_ops.append(
                self.ops.op_feed("flask_t75", supplements=["puromycin"])
            )
            cell_prep_ops.append(self.ops.op_passage("flask_t75"))
        except Exception as e:
            raise Exception(f"Failed in Cell Line Preparation: {e}")
        processes.append(Process("Cell Line Preparation", cell_prep_ops))

        # Process 3: Phenotypic Screening
        # Plate → (Optional: Treat) → Fix → Stain → Image
        screening_ops: List[UnitOp] = []
        try:
            screening_ops.append(self.ops.op_passage("plate_96well"))  # Seeding
            screening_ops.append(self.ops.op_fix_cells("plate_96well"))
            screening_ops.append(self.ops.op_cell_painting("plate_96well"))
            screening_ops.append(self.ops.op_imaging("plate_96well"))
        except Exception as e:
            raise Exception(f"Failed in Phenotypic Screening: {e}")
        processes.append(Process("Phenotypic Screening", screening_ops))

        # Process 4: Data Analysis (Compute)
        # Image Processing → Feature Extraction → gRNA Assignment
        analysis_ops: List[UnitOp] = []
        try:
            analysis_ops.append(
                self.ops.op_compute_analysis("image_processing", num_samples=96)
            )
            analysis_ops.append(
                self.ops.op_compute_analysis("feature_extraction", num_samples=96)
            )
        except Exception as e:
            raise Exception(f"Failed in Data Analysis: {e}")
        processes.append(Process("Data Analysis", analysis_ops))

        # Name updated to satisfy tests
        return Workflow("Zombie POSH Screening", processes)

    def build_vanilla_posh(self) -> Workflow:
        """
        Defines the Vanilla POSH Screening Workflow.
        """
        processes: List[Process] = []

        # 1. Genetic Supply (Same)
        upstream_ops: List[UnitOp] = []
        upstream_ops.append(self.ops.op_transfect("flask_t175", method="pei"))
        processes.append(Process("1. Genetic Supply", upstream_ops))

        # 2. Screening Prep (Same)
        screen_ops: List[UnitOp] = []
        screen_ops.append(self.ops.op_thaw("flask_t75"))
        screen_ops.append(
            self.ops.op_transduce("flask_t75", method="passive")
        )  # Passive is standard
        screen_ops.append(
            self.ops.op_feed("flask_t75", supplements=["puromycin"])
        )
        screen_ops.append(self.ops.op_passage("plate_96well"))
        processes.append(Process("2. Screening Prep", screen_ops))

        # 3. Readout (Standard Cell Painting)
        readout_ops: List[UnitOp] = []
        readout_ops.append(self.ops.op_fix_cells("plate_96well"))
        readout_ops.append(self.ops.op_cell_painting("plate_96well"))
        readout_ops.append(self.ops.op_imaging("plate_96well"))
        processes.append(Process("3. Vanilla Readout", readout_ops))

        return Workflow("Vanilla POSH Screening", processes)
