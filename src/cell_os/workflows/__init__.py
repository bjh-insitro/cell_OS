from dataclasses import dataclass
from typing import List
from cell_os.unit_ops import UnitOp, ParametricOps, AssayRecipe
from .zombie_posh_shopping_list import ZombiePOSHShoppingList


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

    # --- NEW: PROCESS BLOCK METHODS (Tier 2) ---
    def build_master_cell_bank(
        self,
        flask_size: str = "flask_t75",
        cell_line: str = "U2OS",
        target_vials: int = 10,
        cells_per_vial: int = 1_000_000,
        include_qc: bool = True,
    ) -> Workflow:
        """
        Master Cell Bank (MCB) Production.

        Biology intent:
          - Thaw one vendor MCB vial
          - Seed 1e6 cells into a T75
          - Grow to confluence
          - Harvest and freeze `target_vials` vials at `cells_per_vial` each
          - Perform QC tests (mycoplasma, sterility) if include_qc=True
          - Discard remaining cells
        """
        process_ops: List[UnitOp] = []

        # 1. Thaw and seed from vendor vial (handles coating logic internally)
        process_ops.append(self.ops.op_thaw(flask_size, cell_line=cell_line))

        # 2. Count cells after thaw for QC / bookkeeping
        process_ops.append(self.ops.op_count(flask_size, method="nc202"))

        # 3. Final Harvest and Freeze
        use_resolver = False
        if hasattr(self.ops, 'resolver') and self.ops.resolver:
            try:
                # Infer vessel type
                parts = flask_size.split('_')
                if len(parts) > 1 and parts[0] == "flask":
                     vessel_type = parts[1].upper()
                else:
                     vessel_type = parts[-1].upper()
                
                ops = self.ops.resolver.resolve_passage_protocol(cell_line, vessel_type)
                process_ops.extend(ops)
                use_resolver = True
            except Exception:
                pass
        
        if not use_resolver:
            # Legacy fallback
            dissociation = "accutase" if cell_line.lower() == "ipsc" else "trypsin"
            process_ops.append(
                self.ops.op_harvest(flask_size, dissociation_method=dissociation)
            )

        # Freeze the master bank vials
        process_ops.append(self.ops.op_freeze(num_vials=target_vials))

        # 4. QC Tests (if enabled)
        if include_qc:
            # Mycoplasma test (PCR-based, 3 hours)
            process_ops.append(self.ops.op_mycoplasma_test(f"{flask_size}_sample", method="pcr"))
            
            # Sterility test (7 days)
            process_ops.append(self.ops.op_sterility_test(f"{flask_size}_sample", duration_days=7))
            
            # Karyotype for stem cells
            if cell_line.lower() in ["ipsc", "hesc"]:
                process_ops.append(self.ops.op_karyotype(f"{flask_size}_sample", method="g_banding"))

        return Workflow("Master Cell Bank (MCB) Production", [
            Process("Cell Banking & Expansion", process_ops)
        ])

    def build_working_cell_bank(
        self,
        flask_size: str = "flask_t75",
        cell_line: str = "U2OS",
        target_vials: int = 10,
        cells_per_vial: int = 1_000_000,
        starting_passage: int = 3,
        include_qc: bool = True,
    ) -> Workflow:
        """
        Working Cell Bank (WCB) Production.

        Biology intent:
          - Thaw one MCB vial (Passage P)
          - Expand (P -> P+1 or P+2)
          - Harvest and freeze `target_vials`
          - Perform QC
        """
        process_ops: List[UnitOp] = []

        # 1. Thaw MCB vial
        process_ops.append(self.ops.op_thaw(flask_size, cell_line=cell_line))
        
        # 2. Expansion
        # For 1->10 vials, we likely just need to grow the thawed flask to confluence
        # and maybe one passage if yield isn't enough.
        # A T75 yields ~10e6 cells. 10 vials @ 1e6 = 10e6 cells.
        # So one T75 is enough. We just feed it until confluent.
        
        # We add a feed step to simulate maintenance during growth
        process_ops.append(self.ops.op_feed(flask_size, cell_line=cell_line))

        # 3. Harvest
        process_ops.append(self.ops.op_harvest(flask_size))

        # 4. Freeze
        process_ops.append(self.ops.op_freeze(num_vials=target_vials))
        
        # 5. QC
        if include_qc:
            process_ops.append(self.ops.op_mycoplasma_test(f"{flask_size}_sample"))
            process_ops.append(self.ops.op_sterility_test(f"{flask_size}_sample"))

        return Workflow("Working Cell Bank (WCB) Production", [
            Process("WCB Expansion", process_ops)
        ])

    def build_viral_titer(self, plate_size="plate_96well_tc") -> Workflow:
        """
        Defines the Viral Titer Measurement Process Block.
        Plate cells -> Transduce with serial LV dilutions -> Readout.
        """
        process_ops: List[UnitOp] = []
        
        # 1. Seeding Cells (Assumes passage to 96-well format)
        process_ops.append(self.ops.op_passage(plate_size, ratio=1))
        
        # 2. Transduction (Passive transduction with LV)
        process_ops.append(self.ops.op_transduce(plate_size, virus_vol_ul=10.0, method="passive"))
        
        # 3. Readout (Flow cytometry or Imaging for BFP expression)
        # Assumes a flow cytometry op exists for quantification
        process_ops.append(self.ops.op_flow_cytometry(plate_size, num_samples=96)) 
        
        return Workflow("Viral Titer Measurement", [
            Process("LV Titer Assay Protocol", process_ops)
        ])
    
    # --- END NEW PROCESS BLOCK METHODS ---

    # --- CAMPAIGN WORKFLOW METHODS (Tier 1) ---
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
            screening_ops.append(self.ops.op_passage("plate_96well_tc"))  # Seeding
            screening_ops.append(self.ops.op_fix_cells("plate_96well_tc"))
            screening_ops.append(self.ops.op_cell_painting("plate_96well_tc"))
            screening_ops.append(self.ops.op_imaging("plate_96well_tc"))
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
        screen_ops.append(self.ops.op_passage("plate_96well_tc"))
        processes.append(Process("2. Screening Prep", screen_ops))

        # 3. Readout (Standard Cell Painting)
        readout_ops: List[UnitOp] = []
        readout_ops.append(self.ops.op_fix_cells("plate_96well_tc"))
        readout_ops.append(self.ops.op_cell_painting("plate_96well_tc"))
        readout_ops.append(self.ops.op_imaging("plate_96well_tc"))
        processes.append(Process("3. Vanilla Readout", readout_ops))

        return Workflow("Vanilla POSH Screening", processes)