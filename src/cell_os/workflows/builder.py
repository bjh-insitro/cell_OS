from typing import List
import numpy as np
from cell_os.unit_ops import UnitOp, ParametricOps
from .base import Workflow, Process
from .helpers import resolve_coating, resolve_dissociation_method, infer_vessel_type
from .zombie_posh_shopping_list import ZombiePOSHShoppingList


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

        # 1. Coat flask if needed (Day -1, 24hr before thaw)
        coating_needed, coating_agent = resolve_coating(cell_line)
        if coating_needed:
            process_ops.append(self.ops.op_coat(flask_size, agents=[coating_agent]))

        # 2. Thaw and seed from vendor vial (coating already done)
        process_ops.append(self.ops.op_thaw(flask_size, cell_line=cell_line, skip_coating=True))

        # 3. Feed (only iPSC/hESC require daily feeding during expansion)
        if cell_line and cell_line.lower() in ["ipsc", "hesc"]:
            process_ops.append(self.ops.op_feed(flask_size, cell_line=cell_line))

        # 4. Final Harvest and Freeze
        use_resolver = False
        if hasattr(self.ops, "resolver") and self.ops.resolver:
            try:
                vessel_type = infer_vessel_type(flask_size)
                ops = self.ops.resolver.resolve_passage_protocol(cell_line, vessel_type)
                process_ops.extend(ops)
                use_resolver = True
            except Exception:
                pass
        
        if not use_resolver:
            dissociation = resolve_dissociation_method(cell_line)
            process_ops.append(
                self.ops.op_harvest(flask_size, dissociation_method=dissociation, cell_line=cell_line)
            )

        # Freeze the master bank vials
        process_ops.append(self.ops.op_freeze(num_vials=target_vials, cell_line=cell_line))

        return Workflow("Master Cell Bank (MCB) Production", [
            Process("Cell Banking & Expansion", process_ops)
        ])

    def build_working_cell_bank(
        self,
        flask_size: str = "flask_t75",
        cell_line: str = "U2OS",
        target_vials: int = 100,
        cells_per_vial: int = 1_000_000,
    ) -> Workflow:
        """
        Working Cell Bank (WCB) Production.
        
        Biology intent:
          - Thaw one MCB vial
          - Expand to N flasks
          - Harvest and freeze `target_vials` vials
        """
        process_ops = []
        
        # 1. Thaw MCB
        process_ops.append(self.ops.op_thaw(flask_size, cell_line=cell_line))
        
        # 2. Expand (simplified - assume 1 passage for now)
        # In reality, might need multiple passages to reach 100 vials
        # Only iPSC/hESC require daily feeding
        if cell_line and cell_line.lower() in ["ipsc", "hesc"]:
            process_ops.append(self.ops.op_feed(flask_size, cell_line=cell_line))
        process_ops.append(self.ops.op_passage(flask_size, ratio=5, cell_line=cell_line))
        if cell_line and cell_line.lower() in ["ipsc", "hesc"]:
            process_ops.append(self.ops.op_feed(flask_size, cell_line=cell_line))
        
        # 3. Harvest
        dissociation = resolve_dissociation_method(cell_line)
        process_ops.append(self.ops.op_harvest(flask_size, dissociation_method=dissociation, cell_line=cell_line))

        # 4. Freeze
        process_ops.append(self.ops.op_freeze(num_vials=target_vials, cell_line=cell_line))
        
        return Workflow("Working Cell Bank (WCB) Production", [
            Process("WCB Expansion", process_ops)
        ])

    def build_titration_workflow(self, cell_line: str = "U2OS", num_conditions: int = 8, replicates: int = 2) -> Workflow:
        """
        LV Titration Experiment Workflow.
        
        Simplified workflow:
        1. Thaw WCB into T75 (coat only if iPSC)
        2. Passage into 6-well plates (coat only if iPSC)
        3. Add virus
        4. Feed plates (24h post-transduction to remove virus)
        5. Harvest & Flow Cytometry
        """
        process_ops = []
        
        # Check if coating needed (only iPSC/hESC)
        coating_needed, coating_agent = resolve_coating(cell_line)

        # 1. Thaw WCB into T75
        if coating_needed:
            process_ops.append(self.ops.op_coat("flask_t75", agents=[coating_agent]))
            
        process_ops.append(self.ops.op_thaw("flask_t75", cell_line=cell_line, skip_coating=True))
        
        # 2. Passage T75 into 6-well plates
        # Calculate how many plates needed (8 conditions * 2 reps = 16 wells = 3 plates)
        num_wells = num_conditions * replicates
        num_plates = (num_wells + 5) // 6
        
        # Coat plates if needed
        if coating_needed:
            # Single op for coating all plates
            process_ops.append(self.ops.op_coat("plate_6well", agents=[coating_agent], num_vessels=num_plates))
        
        # Harvest T75 and seed into plates (consolidated)
        process_ops.append(self.ops.op_harvest("flask_t75", cell_line=cell_line))
        
        # Seed plates with detailed atomic steps
        process_ops.append(self.ops.op_seed_plate(
            "plate_6well",
            num_wells=num_wells,
            volume_per_well_ml=2.0,
            cell_line=cell_line,
            name=f"Seed {num_wells} wells across {num_plates} plates"
        ))

        # 3. Prepare virus dilutions & transduce
        # Prepare dilutions (one tube per condition)
        for i in range(num_conditions):
            process_ops.append(self.ops.op_dispense("tube_15ml", volume_ml=1.0, liquid_name="media", name=f"Prep Dilution {i+1} (Media)"))
            process_ops.append(self.ops.op_dispense("tube_15ml", volume_ml=0.01, liquid_name="virus", name=f"Prep Dilution {i+1} (Virus)"))
            
        # Add virus to wells (consolidated into single op)
        total_virus_vol = 0.1 * num_wells
        process_ops.append(self.ops.op_dispense(
            "plate_6well", 
            volume_ml=total_virus_vol, 
            liquid_name="virus_mix", 
            name=f"Transduce {num_wells} wells"
        ))
            
        # 4. Feed plates (24h post-transduction)
        # This removes virus and provides fresh media
        # Create individual feed operations for each plate to properly account for media
        for plate_idx in range(num_plates):
            process_ops.append(self.ops.op_feed(
                "plate_6well", 
                cell_line=cell_line, 
                name=f"Media change plate {plate_idx+1}/{num_plates} (remove virus)"
            ))
        
        # 5. Harvest & Flow Cytometry (48h later)
        # Consolidated harvest operation for all plates
        process_ops.append(self.ops.op_harvest(
            "plate_6well", 
            cell_line=cell_line,
            name=f"Harvest {num_wells} wells for analysis"
        ))
        
        # Flow cytometry (includes sample prep and analysis)
        process_ops.append(self.ops.op_flow_cytometry(
            "plate_96well_u", 
            num_samples=num_wells,
            name=f"Flow Cytometry Analysis ({num_wells} samples)"
        ))
            
        return Workflow("LV Titration Experiment", [
            Process("Titration Execution", process_ops)
        ])

    def build_library_banking_workflow(
        self, 
        cell_line: str = "U2OS", 
        library_size: int = 1000,
        representation: int = 1000
    ) -> Workflow:
        """
        Library Transduction and Banking Workflow.
        
        Creates a bank of library-transduced cells for POSH screens.
        
        Workflow:
        1. Thaw WCB vials
        2. Expand to transduction scale
        3. Transduce with gRNA library (spinoculation)
        4. Puromycin selection (5-7 days)
        5. Expand for banking
        6. Freeze into vials for 4 screens
        
        Args:
            cell_line: Cell line name
            library_size: Number of gRNAs in library
            representation: Coverage for transduction (cells per gRNA)
        """
        process_ops = []
        
        # Calculate scale
        transduction_cells_needed = library_size * representation
        
        # Check if coating needed
        coating_needed, coating_agent = resolve_coating(cell_line)
        
        # 1. Thaw WCB vials into T75 flasks
        # Estimate vials needed: ~1M cells/vial, need transduction_cells_needed
        # Add 50% buffer for expansion
        vials_to_thaw = max(1, int((transduction_cells_needed * 1.5) / 1e6))
        
        for i in range(min(vials_to_thaw, 5)):  # Cap at 5 for workflow display
            if coating_needed:
                process_ops.append(self.ops.op_coat("flask_t75", agents=[coating_agent]))
            process_ops.append(self.ops.op_thaw("flask_t75", cell_line=cell_line, skip_coating=True))
        
        # 2. Expand to transduction scale (2-3 passages)
        # Only iPSC/hESC require daily feeding
        if cell_line and cell_line.lower() in ["ipsc", "hesc"]:
            process_ops.append(self.ops.op_feed("flask_t75", cell_line=cell_line))
        process_ops.append(self.ops.op_passage("flask_t75", cell_line=cell_line))
        if cell_line and cell_line.lower() in ["ipsc", "hesc"]:
            process_ops.append(self.ops.op_feed("flask_t75", cell_line=cell_line))
        
        # 3. Harvest and seed into transduction flasks
        process_ops.append(self.ops.op_harvest("flask_t75", cell_line=cell_line))
        
        # Calculate transduction flasks needed
        # Seed at low density for transduction (~2M cells per T75)
        cells_per_flask_transduction = 2000000
        transduction_flasks = int(np.ceil(transduction_cells_needed / cells_per_flask_transduction))
        
        # Coat flasks if needed
        if coating_needed:
            process_ops.append(self.ops.op_coat("flask_t75", agents=[coating_agent], num_vessels=transduction_flasks))
        
        # Seed transduction flasks
        process_ops.append(self.ops.op_seed(
            "flask_t75",
            num_cells=transduction_cells_needed,
            cell_line=cell_line,
            name=f"Seed {transduction_flasks} flasks for transduction"
        ))
        
        # 4. Transduce with library (passive)
        process_ops.append(self.ops.op_transduce(
            "flask_t75",
            method="passive",
            virus_vol_ul=100.0
        ))
        
        # 5. Puromycin selection (5-7 days)
        for day in range(5):
            process_ops.append(self.ops.op_feed(
                "flask_t75",
                cell_line=cell_line,
                supplements=["puromycin"],
                name=f"Selection Day {day+1} (Puromycin)"
            ))
        
        # 6. Expand for banking
        # Passage 2-3 times to reach banking scale
        for passage_num in range(3):
            process_ops.append(self.ops.op_passage(
                "flask_t75",
                cell_line=cell_line
            ))
            # Only iPSC/hESC require daily feeding between passages
            if cell_line and cell_line.lower() in ["ipsc", "hesc"]:
                process_ops.append(self.ops.op_feed("flask_t75", cell_line=cell_line))
        
        # 7. Harvest and freeze for banking
        process_ops.append(self.ops.op_harvest("flask_t75", cell_line=cell_line))
        
        # Calculate vials needed for 4 screens
        # Assume 5M cells/vial, need ~750 cells/gRNA per screen
        cells_per_screen = int((library_size * 750 / 0.6) * 1.2)  # Adjust for barcode efficiency + buffer
        cells_per_vial = 5e6
        vials_per_screen = int(np.ceil(cells_per_screen / cells_per_vial))
        total_vials = vials_per_screen * 4
        
        process_ops.append(self.ops.op_freeze(
            num_vials=total_vials,
            cell_line=cell_line,
            freezing_media="cryostor_cs10"
        ))
        
        return Workflow("Library Transduction & Banking", [
            Process("Library Banking", process_ops)
        ])


    def build_bank_release_qc(self, cell_line: str = "U2OS", sample_source: str = "flask_sample") -> Workflow:
        """
        Release QC Panel for Cell Banks.
        
        Includes:
        - Mycoplasma (PCR)
        - Sterility (7-day culture)
        - Karyotype (G-banding) for stem cells
        """
        qc_ops = []
        
        # Mycoplasma test (PCR-based, 3 hours)
        qc_ops.append(self.ops.op_mycoplasma_test(sample_source, method="pcr"))
        
        # Sterility test (7 days)
        qc_ops.append(self.ops.op_sterility_test(sample_source, duration_days=7))
        
        # Karyotype for stem cells
        if cell_line.lower() in ["ipsc", "hesc"]:
            qc_ops.append(self.ops.op_karyotype(sample_source, method="g_banding"))
            
        return Workflow("Bank Release QC", [
            Process("Quality Control Assays", qc_ops)
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
    
    def build_posh_screen_from_bank(
        self,
        cell_line: str = "A549",
        treatment: str = "tBHP",
        dose_uM: float = 100.0,
        num_replicates: int = 3,
        library_size: int = 1000,
        coverage: int = 500
    ) -> Workflow:
        """
        POSH Screen Execution from Bank.
        
        Workflow:
        1. Thaw Library Bank Vials
        2. Expand to screening scale
        3. Seed 96-well plates
        4. Treat with compound
        5. Fix, Stain, Image
        """
        process_ops = []
        
        # 1. Thaw Library Bank
        # Calculate cells needed: library_size * coverage * replicates
        cells_needed = library_size * coverage * num_replicates
        # Assume 5M cells/vial bank
        vials_to_thaw = max(1, int(np.ceil(cells_needed / 5e6)))
        
        coating_needed, coating_agent = resolve_coating(cell_line)
        
        for i in range(vials_to_thaw):
            if coating_needed:
                process_ops.append(self.ops.op_coat("flask_t75", agents=[coating_agent]))
            process_ops.append(self.ops.op_thaw("flask_t75", cell_line=cell_line, skip_coating=True))
            
        # 2. Expand (1 passage to recover)
        if cell_line.lower() in ["ipsc", "hesc"]:
            process_ops.append(self.ops.op_feed("flask_t75", cell_line=cell_line))
            
        process_ops.append(self.ops.op_passage("flask_t75", cell_line=cell_line))
        
        # 3. Seed Plates
        # Calculate plates needed (96-well)
        # Cells per well ~10k
        cells_per_well = 10000
        wells_needed = int(np.ceil(cells_needed / cells_per_well))
        plates_needed = int(np.ceil(wells_needed / 96))
        
        if coating_needed:
            process_ops.append(self.ops.op_coat("plate_96well_tc", agents=[coating_agent], num_vessels=plates_needed))
            
        process_ops.append(self.ops.op_seed_plate(
            "plate_96well_tc",
            num_wells=wells_needed,
            volume_per_well_ml=0.1,
            cell_line=cell_line,
            name=f"Seed {plates_needed} plates for screen"
        ))
        
        # 4. Treat
        process_ops.append(self.ops.op_dispense(
            "plate_96well_tc",
            volume_ml=0.001, # 1uL spike
            liquid_name=treatment,
            name=f"Treat with {treatment} ({dose_uM}uM)"
        ))
        
        # 5. Readout
        process_ops.append(self.ops.op_fix_cells("plate_96well_tc"))
        process_ops.append(self.ops.op_cell_painting("plate_96well_tc"))
        process_ops.append(self.ops.op_imaging("plate_96well_tc"))
        
        return Workflow("POSH Screen Execution", [
            Process("Screening", process_ops)
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
