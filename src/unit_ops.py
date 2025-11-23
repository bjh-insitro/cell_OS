"""
unit_ops.py

Manages the library of Unit Operations (UOs) and defines Assay Recipes.
Calculates derived metrics (cost, time, risk) for assays based on their UO composition across 4 layers.
"""

import yaml
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Union

@dataclass
class Vessel:
    id: str
    name: str
    surface_area_cm2: float
    working_volume_ml: float
    coating_volume_ml: float
    max_volume_ml: float

class VesselLibrary:
    def __init__(self, yaml_path: str):
        self.vessels: Dict[str, Vessel] = {}
        self._load(yaml_path)

    def _load(self, path: str):
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        for v_id, v_data in data.get('vessels', {}).items():
            self.vessels[v_id] = Vessel(
                id=v_id,
                name=v_data.get('name', ''),
                surface_area_cm2=float(v_data.get('surface_area_cm2', 0.0)),
                working_volume_ml=float(v_data.get('working_volume_ml', 0.0)),
                coating_volume_ml=float(v_data.get('coating_volume_ml', 0.0)),
                max_volume_ml=float(v_data.get('max_volume_ml', 0.0))
            )

    def get(self, v_id: str) -> Vessel:
        if v_id not in self.vessels:
            raise KeyError(f"Vessel {v_id} not found.")
        return self.vessels[v_id]

@dataclass
class UnitOp:
    uo_id: str
    name: str
    layer: str
    category: str
    time_score: int
    cost_score: int
    automation_fit: int
    failure_risk: int
    staff_attention: int
    instrument: Optional[str]
    material_cost_usd: float = 0.0
    instrument_cost_usd: float = 0.0

class UnitOpLibrary:
    def __init__(self, csv_paths: List[str]):
        self.ops: Dict[str, UnitOp] = {}
        for path in csv_paths:
            self._load(path)

    def _load(self, csv_path: str):
        df = pd.read_csv(csv_path)
        # Handle missing columns if they don't exist yet in older CSVs
        if "material_cost_usd" not in df.columns:
            df["material_cost_usd"] = 0.0
        if "instrument_cost_usd" not in df.columns:
            df["instrument_cost_usd"] = 0.0

        for _, row in df.iterrows():
            self.ops[row["uo_id"]] = UnitOp(
                uo_id=row["uo_id"],
                name=row["name"],
                layer=row["layer"],
                category=row["category"],
                time_score=int(row["time_score"]),
                cost_score=int(row["cost_score"]),
                automation_fit=int(row["automation_fit"]),
                failure_risk=int(row["failure_risk"]),
                staff_attention=int(row["staff_attention"]),
                instrument=row["instrument"] if pd.notna(row["instrument"]) else None,
                material_cost_usd=float(row.get("material_cost_usd", 0.0)),
                instrument_cost_usd=float(row.get("instrument_cost_usd", 0.0))
            )

    def get(self, uo_id: str) -> UnitOp:
        if uo_id not in self.ops:
            raise KeyError(f"Unit Op {uo_id} not found in library.")
        return self.ops[uo_id]

class ParametricOps:
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv: 'Inventory'):
        self.vessels = vessel_lib
        self.inv = pricing_inv

    def op_thaw(self, vessel_id: str) -> UnitOp:
        v = self.vessels.get(vessel_id)
        # Calculate costs
        # Media: Working volume * price
        media_cost = v.working_volume_ml * self.inv.get_price("mtesr_plus_kit") # Defaulting to mTeSR
        # Coating: Coating volume * price
        coating_cost = v.coating_volume_ml * self.inv.get_price("laminin_521") # Defaulting to Laminin
        # Plastic
        plastic_cost = self.inv.get_price(vessel_id)
        
        total_mat = media_cost + coating_cost + plastic_cost
        
        return UnitOp(
            uo_id=f"Thaw_{vessel_id}",
            name=f"Thaw into {v.name}",
            layer="cell_prep",
            category="culture",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=2.8 # Hood time
        )

    def op_passage(self, vessel_id: str, ratio: int = 1) -> UnitOp:
        v = self.vessels.get(vessel_id)
        # Media
        media_cost = v.working_volume_ml * self.inv.get_price("mtesr_plus_kit")
        # Coating
        coating_cost = v.coating_volume_ml * self.inv.get_price("laminin_521")
        # Enzyme (Accutase) - estimate 0.5 mL per 10 cm2? Let's say 20% of working volume
        enzyme_vol = v.working_volume_ml * 0.2
        enzyme_cost = enzyme_vol * self.inv.get_price("accutase")
        # Plastic
        plastic_cost = self.inv.get_price(vessel_id)

        total_mat = media_cost + coating_cost + enzyme_cost + plastic_cost
        
        return UnitOp(
            uo_id=f"Passage_{vessel_id}",
            name=f"Passage to {v.name}",
            layer="cell_prep",
            category="culture",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=2.8
        )

    def op_feed(self, vessel_id: str) -> UnitOp:
        v = self.vessels.get(vessel_id)
        media_cost = v.working_volume_ml * self.inv.get_price("mtesr_plus_kit")
        return UnitOp(
            uo_id=f"Feed_{vessel_id}",
            name=f"Feed {v.name}",
            layer="cell_prep",
            category="culture",
            time_score=0,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Biosafety Cabinet",
            material_cost_usd=media_cost,
            instrument_cost_usd=0.5
        )

    def op_transduce(self, vessel_id: str, virus_vol_ul: float = 10.0) -> UnitOp:
        v = self.vessels.get(vessel_id)
        # Media + Polybrene (negligible cost for polybrene, but let's add a small buffer)
        media_cost = v.working_volume_ml * self.inv.get_price("mtesr_plus_kit") * 1.05 
        # Virus Cost? Usually we don't charge the assay for the virus if we are testing the virus, 
        # but we might want to track the consumption. 
        # For now, let's assume the virus is "free" inventory being tested, or add a small aliquot cost if tracked.
        
        return UnitOp(
            uo_id=f"Transduce_{vessel_id}",
            name=f"Transduce in {v.name}",
            layer="genetic_supply_chain", # Or cell_prep? It's delivering the payload.
            category="perturbation",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=2, # Transduction can vary
            staff_attention=2,
            instrument="Biosafety Cabinet",
            material_cost_usd=media_cost,
            instrument_cost_usd=2.8 # Hood time for careful addition
        )

    def op_selection_feed(self, vessel_id: str, agent: str = "puromycin") -> UnitOp:
        v = self.vessels.get(vessel_id)
        media_cost = v.working_volume_ml * self.inv.get_price("mtesr_plus_kit")
        
        # Agent Cost Calculation
        # Puromycin: $1.5/mg. Usage: 1 ug/mL = 0.001 mg/mL.
        # Cost = Vol(mL) * 0.001 (mg/mL) * Price($/mg)
        # We should probably look up the "working_conc" from a config, but for now hardcode 1 ug/mL for puro
        conc_mg_ml = 0.001 
        agent_price = self.inv.get_price(agent)
        agent_cost = v.working_volume_ml * conc_mg_ml * agent_price
        
        return UnitOp(
            uo_id=f"Select_{agent}_{vessel_id}",
            name=f"Feed {v.name} + {agent}",
            layer="cell_prep",
            category="selection",
            time_score=0,
            cost_score=0,
            automation_fit=1,
            failure_risk=1, # Selection stress
            staff_attention=0,
            instrument="Biosafety Cabinet",
            material_cost_usd=media_cost + agent_cost,
            instrument_cost_usd=0.5
        )

@dataclass
class LayerScore:
    layer_name: str
    cost_score: int = 0
    time_score: int = 0
    risk_sum: int = 0
    count: int = 0
    instruments: List[str] = field(default_factory=list)
    total_material_usd: float = 0.0
    total_instrument_usd: float = 0.0

    @property
    def avg_risk(self) -> float:
        return self.risk_sum / self.count if self.count > 0 else 0.0

@dataclass
class AssayScore:
    assay_name: str
    total_cost_score: int
    total_time_score: int
    total_usd: float
    layer_scores: Dict[str, LayerScore]
    bottleneck_instrument: str

    def __str__(self):
        s = f"Assay: {self.assay_name}\n"
        s += f"  Total Cost Score: {self.total_cost_score}\n"
        s += f"  Total Time Score: {self.total_time_score}\n"
        s += f"  Total USD: ${self.total_usd:.2f}\n"
        s += "  Breakdown by Layer:\n"
        for layer, score in self.layer_scores.items():
            s += f"    [{layer.upper()}] CostScore: {score.cost_score}, TimeScore: {score.time_score}, USD: ${score.total_material_usd + score.total_instrument_usd:.2f}, Avg Risk: {score.avg_risk:.2f}\n"
        s += f"  Bottleneck: {self.bottleneck_instrument}"
        return s

class AssayRecipe:
    def __init__(self, name: str, layers: Dict[str, List[Tuple[Union[str, UnitOp], int]]]):
        self.name = name
        self.layers = layers # Dict[layer_name, List[(uo_id_or_obj, count)]]

    def derive_score(self, library: UnitOpLibrary) -> AssayScore:
        total_cost_score = 0
        total_time_score = 0
        total_usd = 0.0
        layer_scores = {}
        all_instruments = []

        for layer_name, steps in self.layers.items():
            l_score = LayerScore(layer_name=layer_name)
            
            for item, count in steps:
                if isinstance(item, str):
                    uo = library.get(item)
                else:
                    uo = item
                
                # Scores
                l_score.cost_score += uo.cost_score * count
                l_score.time_score += uo.time_score * count
                l_score.risk_sum += uo.failure_risk * count
                l_score.count += count
                
                # Real USD
                mat_cost = uo.material_cost_usd * count
                inst_cost = uo.instrument_cost_usd * count
                l_score.total_material_usd += mat_cost
                l_score.total_instrument_usd += inst_cost
                
                if uo.instrument:
                    l_score.instruments.append(uo.instrument)
                    all_instruments.append(uo.instrument)
            
            layer_scores[layer_name] = l_score
            total_cost_score += l_score.cost_score
            total_time_score += l_score.time_score
            total_usd += (l_score.total_material_usd + l_score.total_instrument_usd)

        bottleneck = ", ".join(sorted(list(set(all_instruments)))) if all_instruments else "None"

        return AssayScore(
            assay_name=self.name,
            total_cost_score=total_cost_score,
            total_time_score=total_time_score,
            total_usd=total_usd,
            layer_scores=layer_scores,
            bottleneck_instrument=bottleneck
        )

# -------------------------------------------------------------------
# Recipes
# -------------------------------------------------------------------

def get_posh_full_stack_recipe() -> AssayRecipe:
    return AssayRecipe(
        name="POSH_CellPainting_FullStack",
        layers={
            "genetic_supply_chain": [], # Amortized, empty for run
            "cell_prep": [
                ("C7", 1), # Thaw_and_seed_for_assay
                ("C8", 1), # Dose_compounds_for_POSH
                ("C9", 1), # Incubate_perturbation_24h
            ],
            "phenotyping": [
                ("P1", 1), # Fix_cells
                ("P2", 1), # Permeabilize
                ("P3", 1), # Block
                ("P4", 1), # Stain_multiplex_dyes
                ("P6", 3), # Wash x3
                ("P7", 1), # High_content_imaging
            ],
            "compute": [
                ("D1", 1), # Image_transfer
                ("D2", 1), # Image_QC
                ("D3", 1), # Segmentation
                ("D4", 1), # Embedding
                ("D5", 1), # Aggregation
                ("D6", 1), # POSH_QC
                ("D7", 1), # Update_model
                ("D8", 1), # Planning
            ]
        }
    )

def get_perturb_seq_recipe() -> AssayRecipe:
    return AssayRecipe(
        name="Perturb_seq_FullStack",
        layers={
            "genetic_supply_chain": [], # Amortized
            "cell_prep": [
                ("C7", 1),  # Thaw_and_seed_for_assay
                ("C10", 1), # Dose_compounds_for_screen
                ("C9", 1),  # Incubate_perturbation_24h
            ],
            "phenotyping": [
                ("P10", 1), # Cell_capture_for_scRNA
                ("P11", 1), # Lysis_and_barcode_RT
                ("P12", 1), # cDNA_amplification
                ("P13", 1), # Library_prep_scRNA
                ("P14", 1), # Pooling_and_qc
                ("P15", 1), # Sequencing_run
            ],
            "compute": [
                ("D9", 1),  # Demultiplex_and_basecall
                ("D10", 1), # Alignment_and_count_matrix
                ("D11", 1), # Guide_assignment_and_QC
                ("D12", 1), # Single_cell_QC_filtering
                ("D13", 1), # scRNA_embedding
                ("D14", 1), # Perturbation_effect_inference
                ("D7", 1),  # Update_surrogate_model
                ("D8", 1),  # Acquisition_planning
            ]
        }
    )

def get_bulk_rna_qc_recipe() -> AssayRecipe:
    return AssayRecipe(
        name="Bulk_RNA_QC",
        layers={
            "genetic_supply_chain": [], # Not relevant
            "cell_prep": [
                ("C1", 1),  # Thaw_parental_cells
                ("C11", 1), # Run_differentiation_protocol
                ("C12", 1), # Harvest_cells_for_RNA
            ],
            "phenotyping": [
                ("P16", 1), # RNA_extraction_bulk
                ("P17", 1), # DNase_treatment
                ("P18", 1), # QC_RNA_integrity
                ("P19", 1), # Library_prep_bulk_RNA
                ("P20", 1), # Library_qc_and_pooling
                ("P21", 1), # Sequencing_run_bulk
            ],
            "compute": [
                ("D15", 1), # Demultiplex_bulk_reads
                ("D16", 1), # Alignment_and_gene_counts_bulk
                ("D17", 1), # Bulk_QC_metrics
                ("D18", 1), # Expression_embedding_bulk
            ]
        }
    )

def get_spin_up_immortalized_line_recipe(ops: 'ParametricOps', cell_line: str = "HepG2") -> AssayRecipe:
    buy_uo = "CC1a" if cell_line == "HepG2" else "CC1b"
    return AssayRecipe(
        name=f"Spin_Up_{cell_line}_Master_Bank",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (buy_uo, 1),             # Buy vial
                (ops.op_thaw("plate_6well"), 1),   # Thaw and seed
                (ops.op_passage("plate_6well"), 2), # Expand (approx 2 passages)
                ("Cell_Freeze_10vials", 1),# Keep generic freeze for now or implement op_freeze
                ("CC6", 1),              # Controlled rate freeze
                ("CC7", 1),              # Store in LN2
                ("CC8", 1),              # Mycoplasma test
            ],
            "phenotyping": [],
            "compute": []
        }
    )

def get_spin_up_ipsc_recipe(ops: 'ParametricOps') -> AssayRecipe:
    return AssayRecipe(
        name="Spin_Up_iPSC_Master_Bank",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                ("IC1", 1),              # Buy vial
                (ops.op_thaw("plate_6well"), 1),   # Thaw and seed
                (ops.op_passage("plate_6well"), 2), # Expand
                ("Cell_Freeze_10vials", 1),# Freeze
                ("IC6", 1),              # Store in LN2
                ("IC7", 1),              # Mycoplasma test
            ],
            "phenotyping": [],
            "compute": []
        }
    )

def get_ipsc_maintenance_recipe(ops: 'ParametricOps') -> AssayRecipe:
    return AssayRecipe(
        name="Weekly_Maintenance_iPSC_1_Line",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (ops.op_feed("plate_6well"), 6),    # Feed daily x6
                (ops.op_passage("plate_6well"), 1), # Passage x1
            ],
            "phenotyping": [],
            "compute": []
        }
    )

def get_mcb_to_wcb_recipe(ops: 'ParametricOps', cell_type: str = "immortalized") -> AssayRecipe:
    suffix = "_immortalized" if cell_type == "immortalized" else "_iPSC"
    return AssayRecipe(
        name=f"MCB_to_WCB_10x1e6_{cell_type}",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (f"W1{suffix}", 1),          # Thaw MCB (Keep specific for now as it tracks inventory)
                (ops.op_passage("plate_6well"), 3),   # Expand to WCB (approx 3 passages)
                ("Cell_Freeze_10vials", 1),  # Freeze 10 vials
                (f"W5{suffix}", 1),          # Store
                (f"W6{suffix}", 1),          # Mycoplasma test
            ],
            "phenotyping": [],
            "compute": []
        }
    )

def get_imicroglia_differentiation_recipe() -> AssayRecipe:
    return AssayRecipe(
        name="iMicroglia_Differentiation_9well_Variance",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                ("W1_iPSC", 1), # Thaw WCB vial (reuse W1 op)
                ("Diff1", 3),   # Coat 3 plates
                ("Diff2", 1),   # Seed 9 wells (1 op covers seeding event)
                ("Diff3", 9),   # Feed 9 wells for 15 days
                ("Diff4", 1),   # Harvest 9 wells (1 op covers harvest event)
            ],
            "phenotyping": [
                ("Diff5", 9),   # Bulk RNA-seq 9 samples
            ],
            "compute": [
                ("D15", 9),     # Demultiplex 9 samples
                ("D16", 9),     # Alignment 9 samples
                ("D17", 1),     # QC metrics
                ("D18", 1),     # Expression embedding
            ]
        }
    )

def get_ngn2_differentiation_recipe() -> AssayRecipe:
    return AssayRecipe(
        name="NGN2_Differentiation_9well_Variance",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                ("W1_iPSC", 1),         # Thaw WCB vial
                ("NGN2_Induction", 3*9),# Induction feeds (3 days * 9 wells)
                ("NGN2_Coat", 3),       # Coat 3 destination plates
                ("NGN2_Replate", 1),    # Harvest and replate
                ("NGN2_Maturation", 7*9)# Maturation feeds (7 feeds * 9 wells)
            ],
            "phenotyping": [
                ("Diff5", 9),           # Bulk RNA-seq 9 samples
            ],
            "compute": [
                ("D15", 9),
                ("D16", 9),
                ("D17", 1),
                ("D18", 1),
            ]
        }
    )

def get_imicroglia_phagocytosis_recipe() -> AssayRecipe:
    return AssayRecipe(
        name="iMicroglia_Phagocytosis_9well",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                ("W1_iPSC", 1), # Thaw WCB vial
                ("Diff1", 3),   # Coat 3 plates
                ("Diff2", 1),   # Seed 9 wells
                ("Diff3", 9),   # Feed 9 wells for 15 days
            ],
            "phenotyping": [
                ("Phago_Stain_Incubate", 9), # Add reagent to 9 wells
                ("Phago_Imaging", 3),        # Image 3 plates (batch)
            ],
            "compute": [
                ("D13", 9),     # Image analysis (using generic D13 for now)
            ]
        }
    )

def get_flow_live_condition_recipe() -> AssayRecipe:
    return AssayRecipe(
        name="Flow_Live_1_Condition_3_Reps",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                ("Flow_Prep_250k", 3), # 3 replicates
            ],
            "phenotyping": [
                ("Flow_Live_Stain", 3),
                ("Flow_Acquisition", 3),
            ],
            "compute": [
                ("D15", 3), # Process 3 files
            ]
        }
    )

def get_flow_fixed_condition_recipe() -> AssayRecipe:
    return AssayRecipe(
        name="Flow_Fixed_1_Condition_3_Reps",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                ("Flow_Prep_1M", 3), # 3 replicates of 1M cells
            ],
            "phenotyping": [
                ("Flow_Fixed_Stain", 3),
                ("Flow_Acquisition", 3),
            ],
            "compute": [
                ("D15", 3), # Process 3 files
            ]
        }
    )

def get_lv_functional_titer_recipe(ops: 'ParametricOps') -> AssayRecipe:
    # Functional Titer: 
    # 1. Seed target cells (e.g. 24-well plate, 6 wells for curve)
    # 2. Transduce with dilution series
    # 3. Incubate 72h
    # 4. Flow Cytometry
    return AssayRecipe(
        name="LV_Functional_Titer_24well",
        layers={
            "genetic_supply_chain": [
                (ops.op_transduce("plate_24well"), 6), # 6 points of titration
            ],
            "cell_prep": [
                (ops.op_thaw("plate_24well"), 1),      # Seed cells
                (ops.op_feed("plate_24well"), 6),      # Feed during incubation (3 days * 2 feeds?)
            ],
            "phenotyping": [
                ("Flow_Prep_250k", 6),   # Harvest 6 wells (using static op for now, or could be parametric passage)
                ("Flow_Acquisition", 6), # Run 6 samples
            ],
            "compute": [
                ("D15", 6), # Analyze 6 files
            ]
        }
    )

def get_lv_library_preparation_recipe(ops: 'ParametricOps', num_grnas: int = 1000, representation: int = 250) -> AssayRecipe:
    # Library Prep:
    # 1. Calculate Scale:
    #    Target Transduced Cells = num_grnas * representation
    #    Transduction Efficiency (MOI 0.3) ~= 30%
    #    Starting Cells = Target Transduced Cells / 0.30
    
    target_surviving_cells = num_grnas * representation
    transduction_efficiency = 0.30
    starting_cells = int(target_surviving_cells / transduction_efficiency)
    
    # 2. Select Vessel
    #    Assume ~150,000 cells/cm2 capacity
    #    T175 (175 cm2) ~ 26M cells
    #    T75 (75 cm2) ~ 11M cells
    #    6-well (9.5 cm2) ~ 1.4M cells
    
    # Simple selection logic (could be moved to a helper)
    if starting_cells > 11_000_000:
        vessel = "flask_t175"
    elif starting_cells > 1_400_000:
        vessel = "flask_t75"
    else:
        vessel = "plate_6well" # Default to 6-well for small libraries
        
    # Calculate number of vessels if > T175 capacity? 
    # For now assume single vessel or scale up count.
    # If starting_cells > 26M, we need multiple T175s.
    capacity_t175 = 26_000_000
    num_vessels = (starting_cells // capacity_t175) + 1
    
    return AssayRecipe(
        name=f"LV_LibPrep_{num_grnas}g_{representation}x_{vessel}",
        layers={
            "genetic_supply_chain": [
                (ops.op_transduce(vessel), num_vessels), 
            ],
            "cell_prep": [
                (ops.op_thaw(vessel), num_vessels),          
                (ops.op_feed(vessel), 2 * num_vessels),          
                (ops.op_selection_feed(vessel), 5 * num_vessels),
                (ops.op_passage(vessel), num_vessels),       
            ],
            "phenotyping": [
                ("Flow_Prep_250k", 2),   # QC checks (sample based, not vessel based)
                ("Flow_Acquisition", 2), 
            ],
            "compute": [
                ("D15", 2), 
            ]
        }
    )
    return AssayRecipe(
        name="LV_Production_Outsourced_Cloning",
        layers={
            "genetic_supply_chain": [
                ("Outsource_Oligo_Syn", 1),    # 1. Oligo Synthesis
                ("Outsource_Cloning", 1),      # 2. Cloning
                ("Outsource_NGS_QC", 1),       # 3. NGS Verification
                ("Outsource_Plasmid_Exp", 1),  # 4. Plasmid Expansion
                ("LV_Transfect", 1),           # 5. LV Prep (Transfect)
                ("LV_Harvest_Conc", 1),        #    LV Prep (Conc)
                ("LV_Titration", 1),           #    LV Prep (QC)
            ],
            "cell_prep": [],
            "phenotyping": [],
            "compute": []
        }
    )
