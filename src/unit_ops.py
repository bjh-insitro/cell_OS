"""
unit_ops.py

Manages the library of Unit Operations (UOs) and defines Assay Recipes.
Calculates derived metrics (cost, time, risk) for assays based on their UO composition across 4 layers.
"""

import pandas as pd
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

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
    def __init__(self, name: str, layers: Dict[str, List[Tuple[str, int]]]):
        self.name = name
        self.layers = layers # Dict[layer_name, List[(uo_id, count)]]

    def derive_score(self, library: UnitOpLibrary) -> AssayScore:
        total_cost_score = 0
        total_time_score = 0
        total_usd = 0.0
        layer_scores = {}
        all_instruments = []

        for layer_name, steps in self.layers.items():
            l_score = LayerScore(layer_name=layer_name)
            
            for uo_id, count in steps:
                uo = library.get(uo_id)
                
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

def get_spin_up_immortalized_line_recipe(cell_line: str = "HepG2") -> AssayRecipe:
    buy_uo = "CC1a" if cell_line == "HepG2" else "CC1b"
    return AssayRecipe(
        name=f"Spin_Up_{cell_line}_Master_Bank",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (buy_uo, 1), # Buy vial
                ("CC2", 1),  # Thaw and seed
                ("CC3", 1),  # Expand to banking density
                ("CC4", 1),  # Harvest for freezing
                ("CC5", 1),  # Freeze 10 vials
                ("CC6", 1),  # Controlled rate freeze
                ("CC7", 1),  # Store in LN2
                ("CC8", 1),  # Mycoplasma test
            ],
            "phenotyping": [],
            "compute": []
        }
    )

def get_spin_up_ipsc_recipe() -> AssayRecipe:
    return AssayRecipe(
        name="Spin_Up_iPSC_Master_Bank",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                ("IC1", 1), # Buy vial
                ("IC2", 1), # Thaw and seed
                ("IC3", 1), # Expand to banking density
                ("IC4", 1), # Harvest for freezing
                ("IC5", 1), # Freeze 10 vials
                ("IC6", 1), # Store in LN2
                ("IC7", 1), # Mycoplasma test
            ],
            "phenotyping": [],
            "compute": []
        }
    )

def get_ipsc_maintenance_recipe() -> AssayRecipe:
    return AssayRecipe(
        name="Weekly_Maintenance_iPSC_1_Line",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                ("IC8", 6), # Feed daily x6
                ("IC9", 1), # Passage x1
            ],
            "phenotyping": [],
            "compute": []
        }
    )

def get_mcb_to_wcb_recipe(cell_type: str = "immortalized") -> AssayRecipe:
    suffix = "_immortalized" if cell_type == "immortalized" else "_iPSC"
    return AssayRecipe(
        name=f"MCB_to_WCB_10x1e6_{cell_type}",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (f"W1{suffix}", 1), # Thaw MCB
                (f"W2{suffix}", 1), # Expand to WCB
                (f"W3{suffix}", 1), # Harvest
                (f"W4{suffix}", 1), # Freeze 10 vials
                (f"W5{suffix}", 1), # Store
                (f"W6{suffix}", 1), # Mycoplasma test
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
