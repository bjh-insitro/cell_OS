"""
unit_ops.py

Manages the library of Unit Operations (UOs) and defines Assay Recipes.
Calculates derived metrics (cost, time, risk) for assays based on their UO composition across 4 layers.
"""

import yaml
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Union

# Import cell line database for automatic method selection
try:
    from src.cell_line_database import get_cell_line_profile, get_optimal_methods
    CELL_LINE_DB_AVAILABLE = True
except ImportError:
    CELL_LINE_DB_AVAILABLE = False

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
    sub_steps: List['UnitOp'] = field(default_factory=list)

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

    def get_cell_line_defaults(self, cell_line: str) -> Dict[str, str]:
        """
        Get optimal method defaults for a specific cell line.
        
        Args:
            cell_line: Cell line identifier (e.g., "HEK293", "iPSC")
            
        Returns:
            Dictionary with optimal method selections
            
        Raises:
            ValueError: If cell line database is not available or cell line not found
        """
        if not CELL_LINE_DB_AVAILABLE:
            raise ValueError("Cell line database not available. Install cell_line_database module.")
        
        return get_optimal_methods(cell_line)

    def op_thaw(self, vessel_id: str, cell_line: Optional[str] = None) -> UnitOp:
        v = self.vessels.get(vessel_id)
        
        # Define the granular steps
        steps = []
        
        # 1. Coat vessel (Dispense coating + Incubate + Aspirate)
        steps.append(self.op_dispense(vessel_id, v.coating_volume_ml, "laminin_521"))
        steps.append(self.op_incubate(vessel_id, 60))  # 1 hour coating
        steps.append(self.op_aspirate(vessel_id, v.coating_volume_ml))
        
        # 2. Pre-warm media (Dispense into vessel)
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
        
        # 3. Thaw vial (water bath - modeled as incubate)
        steps.append(self.op_incubate("vial", 2, 37.0))  # 2 min in 37C water bath
        
        # 4. Transfer cells to vessel (Dispense)
        # Vial contains ~1mL, we dispense it into the vessel
        steps.append(self.op_dispense(vessel_id, 1.0, "cell_suspension"))  # Mock liquid name
        
        # 5. Incubate overnight
        steps.append(self.op_incubate(vessel_id, 960))  # 16 hours
        
        # Calculate total costs from steps
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Add vessel cost (not captured in atomic ops)
        vessel_cost = self.inv.get_price(vessel_id)
        
        return UnitOp(
            uo_id=f"Thaw_{vessel_id}",
            name=f"Thaw into {v.name} (Granular)",
            layer="cell_prep",
            category="culture",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat + vessel_cost,
            instrument_cost_usd=total_inst + 2.8,  # Add base hood time
            sub_steps=steps
        )

    def op_passage(self, vessel_id: str, ratio: int = 1, dissociation_method: str = "accutase") -> UnitOp:
        """
        Passage cells using various dissociation methods.
        
        Args:
            vessel_id: Vessel to passage
            ratio: Split ratio (not used in cost calc, handled by recipe count)
            dissociation_method: "accutase", "tryple", "trypsin", "versene", "scraping"
        """
        v = self.vessels.get(vessel_id)
        
        steps = []
        
        # 1. Aspirate old media
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
        
        if dissociation_method == "scraping":
            # Manual scraping (no enzyme)
            # 2. Add PBS
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs"))
            
            # 3. Scrape (modeled as manual step with high staff attention)
            steps.append(UnitOp(
                uo_id="Scrape_Cells",
                name="Scrape Cells",
                layer="atomic",
                category="liquid_handling",
                time_score=1,
                cost_score=0,
                automation_fit=0,  # Manual only
                failure_risk=1,
                staff_attention=3,  # High attention
                instrument="Cell Scraper",
                material_cost_usd=self.inv.get_price("cell_scraper"),
                instrument_cost_usd=2.0
            ))
            
            # 4. Collect cells
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            
            incubation_time = 0  # No incubation
            needs_quench = False
            
        elif dissociation_method == "versene":
            # EDTA only (very gentle, no enzyme)
            # 2. Wash with PBS
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs"))
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            
            # 3. Add Versene (EDTA)
            enzyme_vol = v.working_volume_ml * 0.2
            steps.append(self.op_dispense(vessel_id, enzyme_vol, "versene_edta"))
            
            # 4. Incubate (longer than enzymatic)
            incubation_time = 10  # 10 minutes
            steps.append(self.op_incubate(vessel_id, incubation_time))
            
            needs_quench = False  # EDTA doesn't need quenching
            
        else:
            # Enzymatic dissociation (accutase, tryple, trypsin)
            # 2. Wash with PBS
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs"))
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            
            # 3. Add enzyme
            enzyme_vol = v.working_volume_ml * 0.2
            
            if dissociation_method == "accutase":
                enzyme_name = "accutase"
                incubation_time = 5
            elif dissociation_method == "tryple":
                enzyme_name = "tryple_express"
                incubation_time = 5
            elif dissociation_method == "trypsin":
                enzyme_name = "trypsin_edta"
                incubation_time = 3  # Faster but harsher
            else:
                raise ValueError(f"Unknown dissociation method: {dissociation_method}")
            
            steps.append(self.op_dispense(vessel_id, enzyme_vol, enzyme_name))
            
            # 4. Incubate
            steps.append(self.op_incubate(vessel_id, incubation_time))
            
            needs_quench = True
        
        # Common steps after dissociation
        if needs_quench:
            # 5. Quench with Media
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
            
            # 6. Collect (Aspirate everything)
            total_vol = enzyme_vol + v.working_volume_ml
            steps.append(self.op_aspirate(vessel_id, total_vol))
        else:
            # Just collect
            if dissociation_method != "scraping":
                steps.append(self.op_aspirate(vessel_id, enzyme_vol))
        
        # 7. Centrifuge
        steps.append(self.op_centrifuge(vessel_id, 5))
        
        # 8. Aspirate Supernatant
        if needs_quench:
            steps.append(self.op_aspirate(vessel_id, total_vol))
        else:
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
        
        # 9. Resuspend
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
        
        # 10. Count
        steps.append(self.op_count(vessel_id))
        
        # 11. Seed into new vessel
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
        
        # Calculate total costs from steps
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Adjust cost score based on method
        cost_score = 1
        if dissociation_method in ["accutase"]:
            cost_score = 2  # Expensive enzyme
        
        return UnitOp(
            uo_id=f"Passage_{dissociation_method}_{vessel_id}",
            name=f"Passage {v.name} ({dissociation_method}) (Granular)",
            layer="cell_prep",
            category="culture",
            time_score=1,
            cost_score=cost_score,
            automation_fit=1 if dissociation_method != "scraping" else 0,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 2.8,
            sub_steps=steps
        )

    def op_feed(self, vessel_id: str, media: str = "mtesr_plus_kit", supplements: List[str] = None) -> UnitOp:
        v = self.vessels.get(vessel_id)
        
        steps = []
        
        # 1. Aspirate old media
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
        
        # 2. Dispense fresh media
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, media))
        
        # 3. Add supplements (if any)
        if supplements:
            for supp in supplements:
                # Estimate dilution factors
                dilution = 0.001  # Default 1:1000
                if "supp" in supp or "b27" in supp or "n2" in supp: dilution = 0.01  # 1:100
                if "glutamax" in supp: dilution = 0.01
                
                supp_vol = v.working_volume_ml * dilution
                steps.append(self.op_dispense(vessel_id, supp_vol, supp))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Feed_{vessel_id}_{media}",
            name=f"Feed {v.name} ({media}) (Granular)",
            layer="cell_prep",
            category="culture",
            time_score=0,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 0.5,
            sub_steps=steps
        )

    def op_transduce(self, vessel_id: str, virus_vol_ul: float = 10.0, method: str = "passive") -> UnitOp:
        """
        Transduce cells with lentivirus using various methods.
        
        Args:
            vessel_id: Vessel to transduce
            virus_vol_ul: Volume of virus in microliters
            method: Transduction method - "passive" or "spinoculation"
        """
        v = self.vessels.get(vessel_id)
        
        steps = []
        
        if method == "passive":
            # Passive Transduction (standard)
            # 1. Aspirate old media
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            
            # 2. Dispense fresh media (with polybrene)
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
            
            # 3. Add virus
            virus_vol_ml = virus_vol_ul / 1000.0
            steps.append(self.op_dispense(vessel_id, virus_vol_ml, "lentivirus"))
            
            # 4. Incubate overnight
            steps.append(self.op_incubate(vessel_id, 960))  # 16 hours
            
        elif method == "spinoculation":
            # Spinoculation (centrifuge-enhanced transduction)
            # 1. Aspirate old media
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            
            # 2. Dispense fresh media (with polybrene)
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "mtesr_plus_kit"))
            
            # 3. Add virus
            virus_vol_ml = virus_vol_ul / 1000.0
            steps.append(self.op_dispense(vessel_id, virus_vol_ml, "lentivirus"))
            
            # 4. Centrifuge (spinoculation)
            steps.append(self.op_centrifuge(vessel_id, 90, 1000))  # 90 min at 1000g
            
            # 5. Incubate (shorter than passive)
            steps.append(self.op_incubate(vessel_id, 240))  # 4 hours
            
        else:
            raise ValueError(f"Unknown transduction method: {method}")
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Transduce_{method}_{vessel_id}",
            name=f"Transduce in {v.name} ({method}) (Granular)",
            layer="genetic_supply_chain",
            category="perturbation",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=2,
            staff_attention=2,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 2.8,
            sub_steps=steps
        )

    def op_coat(self, vessel_id: str, agents: List[str] = None) -> UnitOp:
        if agents is None: agents = ["laminin_521"]
        v = self.vessels.get(vessel_id)
        
        steps = []
        
        # 1. Prepare coating solution (Dispense buffer + agents)
        steps.append(self.op_dispense(vessel_id, v.coating_volume_ml, "dpbs"))
        
        for agent in agents:
            # Estimate concentration based on agent type
            conc = 0.01  # Default 10 ug/mL (Laminin)
            if agent == "plo": conc = 0.1  # 100 ug/mL
            
            # Add coating agent (volume is negligible, cost is in the agent itself)
            agent_vol = v.coating_volume_ml * conc * 0.001  # Convert ug/mL to mL
            steps.append(self.op_dispense(vessel_id, agent_vol, agent))
        
        # 2. Incubate
        steps.append(self.op_incubate(vessel_id, 60))  # 1 hour
        
        # 3. Aspirate coating solution
        steps.append(self.op_aspirate(vessel_id, v.coating_volume_ml))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Coat_{vessel_id}_{'_'.join(agents)}",
            name=f"Coat {v.name} with {', '.join(agents)} (Granular)",
            layer="cell_prep",
            category="culture",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=0,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 2.8,
            sub_steps=steps
        )

    def op_transfect(self, vessel_id: str, method: str = "pei") -> UnitOp:
        """
        Transfect cells using various methods.
        
        Args:
            vessel_id: Vessel to transfect
            method: Transfection method - "pei", "lipofectamine", "fugene", "calcium_phosphate"
        """
        v = self.vessels.get(vessel_id)
        
        steps = []
        
        # Method-specific protocols
        if method == "pei":
            # PEI Protocol (cheap, for HEK293)
            # 1. Prepare transfection media (DMEM + FBS)
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dmem_high_glucose"))
            fbs_vol = v.working_volume_ml * 0.1
            steps.append(self.op_dispense(vessel_id, fbs_vol, "fbs"))
            
            # 2. Prepare DNA-PEI complex
            pei_vol = 0.0001  # 100ug ~ 0.1mL at typical concentration
            steps.append(self.op_dispense(vessel_id, pei_vol, "pei_transfection"))
            
            # 3. Incubate (complex formation)
            steps.append(self.op_incubate("tube", 15))  # 15 min
            
            # 4. Incubate overnight
            steps.append(self.op_incubate(vessel_id, 960))  # 16 hours
            
        elif method == "lipofectamine":
            # Lipofectamine Protocol (expensive, high efficiency)
            # 1. Prepare Opti-MEM media
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "optimem"))
            
            # 2. Add Lipofectamine (more expensive)
            lipo_vol = v.working_volume_ml * 0.001  # ~1uL per mL media
            steps.append(self.op_dispense(vessel_id, lipo_vol, "lipofectamine_3000"))
            
            # 3. Incubate (complex formation)
            steps.append(self.op_incubate("tube", 10))  # 10 min
            
            # 4. Incubate (shorter than PEI)
            steps.append(self.op_incubate(vessel_id, 240))  # 4 hours
            
            # 5. Replace with complete media
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dmem_high_glucose"))
            fbs_vol = v.working_volume_ml * 0.1
            steps.append(self.op_dispense(vessel_id, fbs_vol, "fbs"))
            
        elif method == "fugene":
            # FuGENE Protocol (gentle, for sensitive cells)
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "optimem"))
            fugene_vol = v.working_volume_ml * 0.003  # 3uL per mL
            steps.append(self.op_dispense(vessel_id, fugene_vol, "fugene_hd"))
            steps.append(self.op_incubate("tube", 15))
            steps.append(self.op_incubate(vessel_id, 480))  # 8 hours
            
        elif method == "calcium_phosphate":
            # Calcium Phosphate (old school, cheap)
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dmem_high_glucose"))
            # Add CaCl2 and phosphate buffer
            cacl2_vol = v.working_volume_ml * 0.01
            steps.append(self.op_dispense(vessel_id, cacl2_vol, "calcium_chloride"))
            steps.append(self.op_dispense(vessel_id, cacl2_vol, "hepes_buffered_saline"))
            steps.append(self.op_incubate(vessel_id, 960))  # Overnight
            
        elif method == "nucleofection":
            # Nucleofection/Electroporation (physical method, best for hard-to-transfect cells)
            # 1. Harvest cells first
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            enzyme_vol = v.working_volume_ml * 0.2
            steps.append(self.op_dispense(vessel_id, enzyme_vol, "accutase"))
            steps.append(self.op_incubate(vessel_id, 5))
            
            # 2. Centrifuge
            steps.append(self.op_centrifuge("tube", 5))
            steps.append(self.op_aspirate("tube", enzyme_vol))
            
            # 3. Resuspend in nucleofection buffer
            nuc_buffer_vol = 0.1  # 100uL per reaction
            steps.append(self.op_dispense("tube", nuc_buffer_vol, "nucleofection_buffer"))
            
            # 4. Electroporation (special instrument cost)
            # This is modeled as a special "incubation" with high instrument cost
            electroporation_cost = 5.0  # Per reaction
            steps.append(UnitOp(
                uo_id="Electroporate",
                name="Electroporate",
                layer="atomic",
                category="perturbation",
                time_score=0,
                cost_score=1,
                automation_fit=0,  # Manual
                failure_risk=1,
                staff_attention=2,
                instrument="Nucleofector",
                material_cost_usd=0.0,
                instrument_cost_usd=electroporation_cost
            ))
            
            # 5. Recovery in complete media
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dmem_high_glucose"))
            fbs_vol = v.working_volume_ml * 0.1
            steps.append(self.op_dispense(vessel_id, fbs_vol, "fbs"))
            steps.append(self.op_incubate(vessel_id, 240))  # 4 hour recovery
            
        else:
            raise ValueError(f"Unknown transfection method: {method}")
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Transfect_{method}_{vessel_id}",
            name=f"Transfect {v.name} ({method}) (Granular)",
            layer="genetic_supply_chain",
            category="perturbation",
            time_score=1,
            cost_score=1 if method in ["pei", "calcium_phosphate"] else 2,  # Lipofectamine is expensive
            automation_fit=1,
            failure_risk=2,
            staff_attention=2,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 3.0,
            sub_steps=steps
        )

    def op_harvest(self, vessel_id: str, dissociation_method: str = "accutase") -> UnitOp:
        """
        Harvest cells using various dissociation methods.
        
        Args:
            vessel_id: Vessel to harvest from
            dissociation_method: "accutase", "tryple", "trypsin", "versene", "scraping"
        """
        v = self.vessels.get(vessel_id)
        
        steps = []
        
        # 1. Aspirate media
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
        
        if dissociation_method == "scraping":
            # Manual scraping
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs"))
            steps.append(UnitOp(
                uo_id="Scrape_Cells",
                name="Scrape Cells",
                layer="atomic",
                category="liquid_handling",
                time_score=1,
                cost_score=0,
                automation_fit=0,
                failure_risk=1,
                staff_attention=3,
                instrument="Cell Scraper",
                material_cost_usd=self.inv.get_price("cell_scraper"),
                instrument_cost_usd=2.0
            ))
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            
        else:
            # Enzymatic or EDTA dissociation
            enzyme_vol = v.working_volume_ml * 0.2
            
            if dissociation_method == "accutase":
                enzyme_name = "accutase"
                incubation_time = 5
            elif dissociation_method == "tryple":
                enzyme_name = "tryple_express"
                incubation_time = 5
            elif dissociation_method == "trypsin":
                enzyme_name = "trypsin_edta"
                incubation_time = 3
            elif dissociation_method == "versene":
                enzyme_name = "versene_edta"
                incubation_time = 10
            else:
                raise ValueError(f"Unknown dissociation method: {dissociation_method}")
            
            # 2. Add enzyme
            steps.append(self.op_dispense(vessel_id, enzyme_vol, enzyme_name))
            
            # 3. Incubate
            steps.append(self.op_incubate(vessel_id, incubation_time))
            
            # 4. Collect cells
            steps.append(self.op_aspirate(vessel_id, enzyme_vol))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        cost_score = 1
        if dissociation_method == "accutase":
            cost_score = 2
        
        return UnitOp(
            uo_id=f"Harvest_{dissociation_method}_{vessel_id}",
            name=f"Harvest from {v.name} ({dissociation_method}) (Granular)",
            layer="cell_prep",
            category="culture",
            time_score=1,
            cost_score=cost_score,
            automation_fit=1 if dissociation_method != "scraping" else 0,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 2.0,
            sub_steps=steps
        )

    def op_freeze(self, num_vials: int = 10, freezing_media: str = "cryostor") -> UnitOp:
        """
        Freeze cells using various freezing media.
        
        Args:
            num_vials: Number of vials to freeze
            freezing_media: "cryostor", "fbs_dmso", "bambanker", "mfresr"
        """
        steps = []
        
        # 1. Harvest cells (simplified - in reality would be a full harvest protocol)
        steps.append(self.op_aspirate("source_vessel", 10.0))  # Remove media
        steps.append(self.op_dispense("source_vessel", 2.0, "accutase"))  # Add enzyme
        steps.append(self.op_incubate("source_vessel", 5))  # Incubate
        steps.append(self.op_dispense("source_vessel", 10.0, "mtesr_plus_kit"))  # Quench
        
        # 2. Centrifuge
        steps.append(self.op_centrifuge("tube", 5))
        
        # 3. Aspirate supernatant
        steps.append(self.op_aspirate("tube", 12.0))
        
        # 4. Count cells
        steps.append(self.op_count("tube"))
        
        # 5. Resuspend in freezing media (1mL per vial)
        total_freeze_media = num_vials * 1.0
        
        if freezing_media == "cryostor":
            # CryoStor CS10 (DMSO-free, expensive)
            steps.append(self.op_dispense("tube", total_freeze_media, "cryostor_cs10"))
            cost_score = 2
            
        elif freezing_media == "fbs_dmso":
            # Classic: 90% FBS + 10% DMSO (cheap)
            fbs_vol = total_freeze_media * 0.9
            dmso_vol = total_freeze_media * 0.1
            steps.append(self.op_dispense("tube", fbs_vol, "fbs"))
            steps.append(self.op_dispense("tube", dmso_vol, "dmso"))
            cost_score = 1
            
        elif freezing_media == "bambanker":
            # Bambanker (serum-free, expensive)
            steps.append(self.op_dispense("tube", total_freeze_media, "bambanker"))
            cost_score = 2
            
        elif freezing_media == "mfresr":
            # mFreSR (for stem cells, expensive)
            steps.append(self.op_dispense("tube", total_freeze_media, "mfresr"))
            cost_score = 2
            
        else:
            raise ValueError(f"Unknown freezing media: {freezing_media}")
        
        # 6. Aliquot into vials (Dispense 1mL per vial)
        for i in range(num_vials):
            steps.append(self.op_dispense(f"vial_{i}", 1.0, "cell_suspension"))
        
        # 7. Controlled rate freeze (modeled as special incubation)
        steps.append(self.op_incubate("freezer", 120, -80.0))  # 2 hours in -80C
        
        # Calculate total costs from steps
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Add vial cost (not captured in atomic dispense ops)
        vial_cost = num_vials * self.inv.get_price("micronic_tube")
        
        return UnitOp(
            uo_id=f"Freeze_{freezing_media}_{num_vials}_vials",
            name=f"Freeze {num_vials} vials ({freezing_media}) (Granular)",
            layer="cell_prep",
            category="banking",
            time_score=1,
            cost_score=cost_score,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat + vial_cost,
            instrument_cost_usd=total_inst + 2.8,  # Add base hood time
            sub_steps=steps
        )

    def op_bulk_rna_seq(self, num_samples: int = 1) -> UnitOp:
        # Service cost per sample
        service_cost = num_samples * self.inv.get_price("bulk_rna_seq")
        
        return UnitOp(
            uo_id=f"Bulk_RNA_Seq_{num_samples}_samples",
            name=f"Bulk RNA-seq ({num_samples} samples)",
            layer="phenotyping",
            category="sequencing",
            time_score=0,
            cost_score=2,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument=None,
            material_cost_usd=service_cost,
            instrument_cost_usd=0.0
        )

    def op_flow_stain(self, num_samples: int = 1, stain_type: str = "live") -> UnitOp:
        # Reagents per sample
        # Plate (1/96)
        plate_cost = (num_samples / 96.0) * self.inv.get_price("plate_96_v_bottom")
        
        reagent_cost = 0.0
        if stain_type == "live":
            # Live: DPBS wash, BSA buffer, DAPI, Antibody
            reagent_cost += num_samples * 20.0 * self.inv.get_price("dpbs") # 20 mL wash? Seems high per sample, maybe per plate? 
            # Original YAML said 20mL for 250k cells (batch?). Let's assume 0.5 mL per sample wash x 3 = 1.5 mL
            reagent_cost += num_samples * 1.5 * self.inv.get_price("dpbs")
            reagent_cost += num_samples * 0.001 * self.inv.get_price("dapi")
            reagent_cost += num_samples * 0.5 * self.inv.get_price("flow_antibody_generic")
            hood_time = 5.0 # Fixed overhead? Or scales? Let's say 5.0 base + 0.1 per sample
        else:
            # Fixed: DPBS, PFA, Triton, Zombie, Antibody
            reagent_cost += num_samples * 2.0 * self.inv.get_price("dpbs")
            reagent_cost += num_samples * 0.5 * self.inv.get_price("pfa_4pct")
            reagent_cost += num_samples * 0.5 * self.inv.get_price("triton_x100")
            reagent_cost += num_samples * 1.0 * self.inv.get_price("viability_dye_zombie")
            reagent_cost += num_samples * 2.0 * self.inv.get_price("flow_antibody_generic")
            hood_time = 8.0
            
        return UnitOp(
            uo_id=f"Flow_Stain_{stain_type}_{num_samples}x",
            name=f"Flow Stain {stain_type} ({num_samples} samples)",
            layer="phenotyping",
            category="assay",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=2,
            instrument="Biosafety Cabinet",
            material_cost_usd=plate_cost + reagent_cost,
            instrument_cost_usd=hood_time
        )

    def op_flow_acquisition(self, num_samples: int = 1) -> UnitOp:
        # Instrument usage
        # $5.00 per sample
        inst_cost = num_samples * 5.0
        
        return UnitOp(
            uo_id=f"Flow_Acq_{num_samples}x",
            name=f"Flow Acquisition ({num_samples} samples)",
            layer="phenotyping",
            category="assay",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=0,
            staff_attention=1,
            instrument="Flow Cytometer",
            material_cost_usd=0.0,
            instrument_cost_usd=inst_cost
        )

    def op_p24_elisa(self, num_samples: int = 1) -> UnitOp:
        # Kit cost per sample (96 tests per kit)
        # 1/96 of kit + overhead
        kit_cost = (num_samples / 96.0) * self.inv.get_price("p24_elisa_kit")
        
        return UnitOp(
            uo_id=f"p24_ELISA_{num_samples}x",
            name=f"p24 ELISA ({num_samples} samples)",
            layer="genetic_supply_chain",
            category="qc",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=0,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=kit_cost,
            instrument_cost_usd=1.0 # Fixed overhead?
        )

    def op_compute_demux(self, num_samples: int = 1) -> UnitOp:
        # Compute cost
        # $2.00 per sample?
        cost = num_samples * 2.0
        
        return UnitOp(
            uo_id=f"Compute_Demux_{num_samples}x",
            name=f"Demultiplex ({num_samples} samples)",
            layer="compute",
            category="bioinformatics",
            time_score=0,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Cloud Compute",
            instrument_cost_usd=cost
        )

    def op_outsource_service(self, service_type: str, num_units: int = 1) -> UnitOp:
        # Map service type to pricing item
        # service_type: "oligo_synthesis", "cloning", "ngs_verification", "plasmid_expansion"
        item_key = f"service_{service_type}"
        cost = num_units * self.inv.get_price(item_key)
        
        return UnitOp(
            uo_id=f"Outsource_{service_type}_{num_units}x",
            name=f"Outsource {service_type} ({num_units}x)",
            layer="genetic_supply_chain",
            category="service",
            time_score=0, # Outsourced
            cost_score=2,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument=None,
            material_cost_usd=cost,
            instrument_cost_usd=0.0
        )

    def op_purchase_cell_line(self, line_name: str) -> UnitOp:
        # For now, assume a fixed cost or look up if we add to pricing
        # In the old code: CC1a/b were "Buy Vial"
        # Let's assume $500 for a vial if not in pricing, or add "cell_vial_immortalized" to pricing later.
        # For now, hardcode or use a generic "cell_vial" item if we had one.
        # Let's use a placeholder cost of $500.
        cost = 500.0
        
        return UnitOp(
            uo_id=f"Purchase_{line_name}",
            name=f"Purchase {line_name} Vial",
            layer="cell_prep",
            category="acquisition",
            time_score=0,
            cost_score=2,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument=None,
            material_cost_usd=cost,
            instrument_cost_usd=0.0
        )

    def op_store_sample(self, storage_type: str = "ln2", duration_months: int = 1) -> UnitOp:
        # Storage cost
        # LN2: Low cost per month
        # Freezer: Low cost
        # Let's say $1/month for LN2, $0.5 for -80
        cost = 1.0 * duration_months if storage_type == "ln2" else 0.5 * duration_months
        
        return UnitOp(
            uo_id=f"Store_{storage_type}_{duration_months}mo",
            name=f"Store in {storage_type} ({duration_months} mo)",
            layer="cell_prep",
            category="storage",
            time_score=0,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Freezer",
            material_cost_usd=0.0,
            instrument_cost_usd=cost
        )

    def op_qc_test(self, test_type: str = "mycoplasma") -> UnitOp:
        # QC Tests
        if test_type == "mycoplasma":
            cost = self.inv.get_price("mycoplasma_kit") # Per test?
            # Pricing says pack of 100 is $400 -> $4/test.
            # But get_price returns unit price if logical unit is defined?
            # Let's assume get_price returns the unit price ($4.0)
            pass
        else:
            cost = 10.0 # Generic
            
        return UnitOp(
            uo_id=f"QC_{test_type}",
            name=f"QC Test: {test_type}",
            layer="cell_prep",
            category="qc",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=0,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=cost,
            instrument_cost_usd=1.0
        )

    def op_compute_analysis(self, analysis_type: str, num_samples: int = 1) -> UnitOp:
        # Generic compute analysis
        # "alignment", "qc", "embedding", "image_analysis"
        # Assume $1 per sample for basic, $5 for heavy
        cost_per_sample = 1.0
        if "alignment" in analysis_type or "image" in analysis_type:
            cost_per_sample = 5.0
            
        return UnitOp(
            uo_id=f"Compute_{analysis_type}_{num_samples}x",
            name=f"Compute: {analysis_type} ({num_samples} samples)",
            layer="compute",
            category="bioinformatics",
            time_score=0,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Cloud Compute",
            material_cost_usd=0.0,
            instrument_cost_usd=num_samples * cost_per_sample
        )

    # ------------------------------------------------------------------
    # Atomic Operations
    # ------------------------------------------------------------------

    def op_aspirate(self, vessel_id: str, volume_ml: float) -> UnitOp:
        # Aspirate liquid (waste)
        # Cost: Tip usage (depends on volume)
        # < 20uL: 20uL tip
        # < 200uL: 200uL tip
        # < 1000uL: 1000uL tip
        # > 1mL: Serological pipette (10mL or 25mL)
        
        tip_cost = 0.0
        tip_name = "None"
        
        if volume_ml <= 0.02:
            tip_cost = self.inv.get_price("pipette_tip_20ul_filter")
            tip_name = "20uL Tip"
        elif volume_ml <= 0.2:
            tip_cost = self.inv.get_price("pipette_tip_200ul_filter")
            tip_name = "200uL Tip"
        elif volume_ml <= 1.0:
            tip_cost = self.inv.get_price("pipette_tip_1000ul_filter")
            tip_name = "1000uL Tip"
        elif volume_ml <= 10.0:
            tip_cost = self.inv.get_price("serological_pipette_10ml")
            tip_name = "10mL Pipette"
        else:
            tip_cost = self.inv.get_price("serological_pipette_25ml")
            tip_name = "25mL Pipette"
            
        return UnitOp(
            uo_id=f"Asp_{volume_ml}ml",
            name=f"Aspirate {volume_ml}mL",
            layer="atomic",
            category="liquid_handling",
            time_score=0,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Pipette",
            material_cost_usd=tip_cost,
            instrument_cost_usd=0.1 # Wear and tear
        )

    def op_dispense(self, vessel_id: str, volume_ml: float, liquid_name: str) -> UnitOp:
        # Dispense liquid
        # Cost: Tip usage + Liquid cost
        
        # 1. Tip Cost (same logic as aspirate)
        tip_cost = 0.0
        if volume_ml <= 0.02:
            tip_cost = self.inv.get_price("pipette_tip_20ul_filter")
        elif volume_ml <= 0.2:
            tip_cost = self.inv.get_price("pipette_tip_200ul_filter")
        elif volume_ml <= 1.0:
            tip_cost = self.inv.get_price("pipette_tip_1000ul_filter")
        elif volume_ml <= 10.0:
            tip_cost = self.inv.get_price("serological_pipette_10ml")
        else:
            tip_cost = self.inv.get_price("serological_pipette_25ml")
            
        # 2. Liquid Cost
        liquid_price = self.inv.get_price(liquid_name)
        liquid_cost = volume_ml * liquid_price
        
        return UnitOp(
            uo_id=f"Disp_{liquid_name}_{volume_ml}ml",
            name=f"Dispense {volume_ml}mL {liquid_name}",
            layer="atomic",
            category="liquid_handling",
            time_score=0,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Pipette",
            material_cost_usd=tip_cost + liquid_cost,
            instrument_cost_usd=0.1
        )

    def op_incubate(self, vessel_id: str, duration_min: int, temp_c: float = 37.0) -> UnitOp:
        # Incubation
        # Cost: Electricity / depreciation (negligible per minute but tracks time)
        return UnitOp(
            uo_id=f"Incubate_{duration_min}min",
            name=f"Incubate {duration_min} min @ {temp_c}C",
            layer="atomic",
            category="incubation",
            time_score=1, # Takes time
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Incubator",
            material_cost_usd=0.0,
            instrument_cost_usd=0.01 * duration_min # Nominal cost
        )

    def op_centrifuge(self, vessel_id: str, duration_min: int = None, g_force: int = None, preset: str = None) -> UnitOp:
        """
        Centrifuge operation with optional presets.
        
        Args:
            vessel_id: Vessel to centrifuge
            duration_min: Duration in minutes (overrides preset)
            g_force: G-force (overrides preset)
            preset: "soft", "standard", or "hard" (ignored if duration/g_force specified)
            
        Returns:
            UnitOp for centrifugation
        """
        # Apply presets if no explicit parameters
        if duration_min is None or g_force is None:
            if preset == "soft":
                duration_min = duration_min or 5
                g_force = g_force or 300
            elif preset == "hard":
                duration_min = duration_min or 10
                g_force = g_force or 1000
            else:  # "standard" or None
                duration_min = duration_min or 5
                g_force = g_force or 500
        
        return UnitOp(
            uo_id=f"Spin_{duration_min}min_{g_force}g",
            name=f"Centrifuge {duration_min} min @ {g_force}g",
            layer="atomic",
            category="separation",
            time_score=1,
            cost_score=0,
            material_cost_usd=0.0,
            instrument_cost_usd=0.5  # Usage cost
        )

    def op_stressor_treatment(
        self,
        vessel_id: str,
        stressor: str = "tbhp",
        concentration_um: float = 100.0,
        duration_h: float = 24.0
    ) -> UnitOp:
        """
        Treat cells with a stressor compound (oxidative stress, ER stress, etc.).

        Args:
            vessel_id: Vessel containing cells
            stressor: Stressor compound (tbhp, tunicamycin, thapsigargin, etc.)
            concentration_um: Final concentration in µM
            duration_h: Treatment duration in hours
        """
        v = self.vessels.get(vessel_id)

        steps = []

        # 1. Aspirate old media
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))

        # 2. Dispense fresh media with stressor
        # Assume stressor is pre-diluted or we add it separately
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dmem_high_glucose"))

        # 3. Add stressor (assume 1000x stock, so 1/1000 of working volume)
        stressor_vol_ml = v.working_volume_ml / 1000.0
        steps.append(self.op_dispense(vessel_id, stressor_vol_ml, stressor))

        # 4. Incubate for treatment duration
        duration_min = int(duration_h * 60)
        steps.append(self.op_incubate(vessel_id, duration_min))

        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)

        return UnitOp(
            uo_id=f"Stressor_{stressor}_{concentration_um}uM_{vessel_id}",
            name=f"Treat with {stressor} ({concentration_um}µM, {duration_h}h)",
            layer="cell_prep",
            category="perturbation",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 2.8,
            sub_steps=steps
        )

    def op_fix_cells(self, vessel_id: str, fixative: str = "pfa_4pct", duration_min: int = 15) -> UnitOp:
        """
        Fix cells for imaging.

        Args:
            vessel_id: Vessel containing cells
            fixative: Fixative type (pfa_4pct, methanol, etc.)
            duration_min: Fixation duration in minutes
        """
        v = self.vessels.get(vessel_id)

        steps = []

        # 1. Aspirate media
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))

        # 2. Wash with PBS
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs"))
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))

        # 3. Add fixative
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, fixative))

        # 4. Incubate
        steps.append(self.op_incubate(vessel_id, duration_min, temp_c=25.0))  # Room temp

        # 5. Wash 3x with PBS
        for _ in range(3):
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs"))

        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)

        return UnitOp(
            uo_id=f"Fix_{fixative}_{vessel_id}",
            name=f"Fix cells ({fixative}, {duration_min}min)",
            layer="phenotyping",
            category="sample_prep",
            time_score=1,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 2.8,
            sub_steps=steps
        )

    def op_cell_painting(
        self,
        vessel_id: str,
        dye_panel: str = "standard_5channel"
    ) -> UnitOp:
        """
        Cell Painting staining protocol.

        Args:
            vessel_id: Vessel containing fixed cells
            dye_panel: Dye panel to use
                - standard_5channel: Hoechst, ConA, Phalloidin, WGA, MitoTracker
                - minimal_3channel: Hoechst, Phalloidin, MitoTracker
                - custom: Define later
        """
        v = self.vessels.get(vessel_id)

        steps = []

        # Define dye panels
        if dye_panel == "standard_5channel":
            dyes = [
                ("hoechst_33342", 1.0),      # Nucleus (blue)
                ("concanavalin_a_647", 5.0), # ER (far-red)
                ("phalloidin_488", 2.0),     # Actin (green)
                ("wga_594", 5.0),            # Golgi/PM (red)
                ("mitotracker_deep_red", 0.5) # Mitochondria (deep red)
            ]
        elif dye_panel == "posh_5channel":
            # ISS-compatible Cell Painting with Mitoprobe
            dyes = [
                ("hoechst_33342", 0.5),       # Nucleus (µg/mL)
                ("concanavalin_a_488", 12.5), # ER (µg/mL)
                ("wga_555", 1.5),             # Golgi/Membrane (µg/mL)
                ("phalloidin_568", 0.33),     # Actin (µM)
                ("mitoprobe_12s_cy5", 0.25),  # Mitochondria (µM, RNA probe)
                ("mitoprobe_16s_cy5", 0.25),  # Mitochondria (µM, RNA probe)
            ]
        elif dye_panel == "posh_6channel":
            # ISS-compatible Cell Painting + pS6 biomarker
            dyes = [
                ("hoechst_33342", 0.5),
                ("concanavalin_a_488", 12.5),
                ("wga_555", 1.5),
                ("phalloidin_568", 0.33),
                ("mitoprobe_12s_cy5", 0.25),
                ("mitoprobe_16s_cy5", 0.25),
                ("ps6_primary", 0.004),       # 1:250 dilution (antibody)
                ("dylight_755_secondary", 0.001), # 1:1000 dilution
            ]
        elif dye_panel == "minimal_3channel":
            dyes = [
                ("hoechst_33342", 1.0),
                ("phalloidin_488", 2.0),
                ("mitotracker_deep_red", 0.5)
            ]
        else:
            raise ValueError(f"Unknown dye panel: {dye_panel}")

        # Permeabilization (if needed for intracellular dyes)
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "triton_x100_0.1pct"))
        steps.append(self.op_incubate(vessel_id, 10, temp_c=25.0))
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))

        # Blocking (optional, reduces background)
        steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "bsa_1pct"))
        steps.append(self.op_incubate(vessel_id, 30, temp_c=25.0))
        steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))

        # Staining
        for dye_name, conc_ug_ml in dyes:
            # Add dye (assume working volume with appropriate dilution)
            dye_vol_ml = v.working_volume_ml * conc_ug_ml * 0.001  # Simplified
            steps.append(self.op_dispense(vessel_id, dye_vol_ml, dye_name))

        # Incubate with dyes
        steps.append(self.op_incubate(vessel_id, 30, temp_c=25.0))

        # Wash 3x
        for _ in range(3):
            steps.append(self.op_aspirate(vessel_id, v.working_volume_ml))
            steps.append(self.op_dispense(vessel_id, v.working_volume_ml, "dpbs"))

        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)

        return UnitOp(
            uo_id=f"CellPaint_{dye_panel}_{vessel_id}",
            name=f"Cell Painting ({dye_panel})",
            layer="phenotyping",
            category="staining",
            time_score=1,
            cost_score=2,  # Dyes are expensive
            automation_fit=1,
            failure_risk=1,
            staff_attention=2,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst + 2.8,
            sub_steps=steps
        )

    def op_imaging(
        self,
        vessel_id: str,
        num_sites_per_well: int = 9,
        channels: int = 5,
        objective: str = "20x"
    ) -> UnitOp:
        """
        High-content imaging acquisition.

        Args:
            vessel_id: Vessel to image
            num_sites_per_well: Number of fields of view per well
            channels: Number of fluorescent channels
            objective: Objective magnification (10x, 20x, 40x, 60x)
        """
        v = self.vessels.get(vessel_id)

        # Calculate total images
        # Assume vessel has a certain number of wells
        # For now, use a lookup or default
        wells_map = {
            "plate_6well": 6,
            "plate_12well": 12,
            "plate_24well": 24,
            "plate_96well": 96,
            "plate_384well": 384
        }
        num_wells = wells_map.get(vessel_id, 96)  # Default to 96

        total_images = num_wells * num_sites_per_well * channels

        # Imaging cost: instrument time + storage
        # Assume ~1 second per image (including autofocus, stage movement)
        imaging_time_min = total_images / 60.0
        instrument_cost = imaging_time_min * 2.0  # $2/min for high-content imager

        # Storage cost (negligible but track it)
        # Assume 2 MB per image
        storage_gb = (total_images * 2.0) / 1000.0
        storage_cost = storage_gb * 0.01  # $0.01/GB

        return UnitOp(
            uo_id=f"Image_{objective}_{num_sites_per_well}sites_{vessel_id}",
            name=f"Image {num_wells} wells ({num_sites_per_well} sites/well, {channels}ch, {objective})",
            layer="phenotyping",
            category="imaging",
            time_score=2,
            cost_score=2,
            automation_fit=2,  # Fully automated
            failure_risk=1,
            staff_attention=1,
            instrument="High-Content Imager",
            material_cost_usd=storage_cost,
            instrument_cost_usd=instrument_cost
        )
    
    # ===================================================================
    # VANILLA POSH (CellPaint-POSH) OPERATIONS
    # ===================================================================
    
    def op_reverse_transcription(
        self,
        vessel_id: str,
        duration_h: float = 16.0,
        temp_c: float = 37.0
    ) -> UnitOp:
        """
        Reverse transcription of sgRNA to cDNA for POSH.
        
        Args:
            vessel_id: Vessel containing fixed cells
            duration_h: RT incubation duration (default: overnight, 16h)
            temp_c: RT temperature (default: 37°C)
        """
        v = self.vessels.get(vessel_id)
        
        steps = []
        
        # RT mix components (per well)
        # RevertAid RT Buffer (1x), dNTPs (250µM), BSA (0.2 mg/mL),
        # RT primer (1µM), Ribolock (0.8 U/µL), RevertAid RT (4.8 U/µL)
        
        rt_vol_ml = v.working_volume_ml
        
        # Enzyme costs
        revertaid_cost = self.inv.get_price("revertaid_rt") * 4.8 * rt_vol_ml * 1000  # U
        ribolock_cost = self.inv.get_price("ribolock") * 0.8 * rt_vol_ml * 1000  # U
        rt_primer_cost = self.inv.get_price("rt_primer") * 0.001  # 1µM in small volume
        
        # dNTPs, BSA (negligible)
        buffer_cost = 0.5  # Estimate for buffers
        
        total_cost = revertaid_cost + ribolock_cost + rt_primer_cost + buffer_cost
        
        # Incubation
        duration_min = int(duration_h * 60)
        steps.append(self.op_incubate(vessel_id, duration_min, temp_c))
        
        return UnitOp(
            uo_id=f"RT_{vessel_id}",
            name=f"Reverse Transcription ({duration_h}h @ {temp_c}°C)",
            layer="genetic_supply_chain",
            category="molecular_biology",
            time_score=2,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Incubator",
            material_cost_usd=total_cost,
            instrument_cost_usd=0.01 * duration_min,
            sub_steps=steps
        )
    
    def op_gap_fill_ligation(
        self,
        vessel_id: str,
        duration_min: int = 90,
        temp_c: float = 45.0
    ) -> UnitOp:
        """
        Gap fill, ligation, and extension for POSH padlock probe circularization.
        
        Args:
            vessel_id: Vessel containing RT-treated cells
            duration_min: Incubation duration (default: 90 min)
            temp_c: Temperature (default: 45°C)
        """
        v = self.vessels.get(vessel_id)
        
        steps = []
        
        # Gap fill mix components
        # Ampligase Buffer (1x), RNaseH (0.4 U/µL), BSA (0.2 mg/mL),
        # Padlock probe (0.1 µM), TaqIT (0.02 U/µL), dNTPs (50 nM), Ampligase (0.5 U/µL)
        
        gf_vol_ml = v.working_volume_ml
        
        # Enzyme costs
        rnase_h_cost = self.inv.get_price("rnase_h") * 0.4 * gf_vol_ml * 1000  # U
        taqit_cost = self.inv.get_price("taqit") * 0.02 * gf_vol_ml * 1000  # U
        ampligase_cost = self.inv.get_price("ampligase") * 0.5 * gf_vol_ml * 1000  # U
        padlock_cost = self.inv.get_price("padlock_probe") * 0.0001  # 0.1 µM in small volume
        
        buffer_cost = 0.5  # Buffers, dNTPs
        
        total_cost = rnase_h_cost + taqit_cost + ampligase_cost + padlock_cost + buffer_cost
        
        # Incubation
        steps.append(self.op_incubate(vessel_id, duration_min, temp_c))
        
        return UnitOp(
            uo_id=f"GapFill_{vessel_id}",
            name=f"Gap Fill & Ligation ({duration_min}min @ {temp_c}°C)",
            layer="genetic_supply_chain",
            category="molecular_biology",
            time_score=1,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Incubator",
            material_cost_usd=total_cost,
            instrument_cost_usd=0.01 * duration_min
        )
    
    def op_rolling_circle_amplification(
        self,
        vessel_id: str,
        duration_h: float = 16.0,
        temp_c: float = 30.0
    ) -> UnitOp:
        """
        Rolling Circle Amplification (RCA) to create visible rolonies from circularized padlock.
        
        Args:
            vessel_id: Vessel containing gap-filled cells
            duration_h: RCA incubation duration (default: overnight, 16h)
            temp_c: RCA temperature (default: 30°C)
        """
        v = self.vessels.get(vessel_id)
        
        steps = []
        
        # RCA mix components
        # phi29 buffer (1x), dNTPs (250 µM), BSA (0.2 mg/mL),
        # glycerol (5%), phi29 polymerase (1 U/µL)
        
        rca_vol_ml = v.working_volume_ml
        
        # Enzyme cost (phi29 is the main cost driver)
        phi29_cost = self.inv.get_price("phi29_polymerase") * 1.0 * rca_vol_ml * 1000  # U
        
        # dNTPs, BSA, glycerol, buffer
        buffer_cost = 1.0  # Estimate
        
        total_cost = phi29_cost + buffer_cost
        
        # Incubation
        duration_min = int(duration_h * 60)
        steps.append(self.op_incubate(vessel_id, duration_min, temp_c))
        
        return UnitOp(
            uo_id=f"RCA_{vessel_id}",
            name=f"Rolling Circle Amplification ({duration_h}h @ {temp_c}°C)",
            layer="genetic_supply_chain",
            category="molecular_biology",
            time_score=2,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Incubator",
            material_cost_usd=total_cost,
            instrument_cost_usd=0.01 * duration_min
        )
    
    def op_sbs_cycle(
        self,
        vessel_id: str,
        cycle_number: int = 1,
        automated: bool = False
    ) -> UnitOp:
        """
        Single cycle of Sequencing By Synthesis (SBS) for POSH.
        
        Includes: anchor primer hybridization, incorporation, washing, imaging, cleavage.
        
        Args:
            vessel_id: Vessel containing RCA-treated cells
            cycle_number: Cycle number (for tracking)
            automated: Whether using automated liquid handling
        """
        v = self.vessels.get(vessel_id)
        
        steps = []
        
        # 1. Anchor primer hybridization (15 min, RT) - only cycle 1
        if cycle_number == 1:
            anchor_cost = self.inv.get_price("anchor_primer") * 0.001  # 1µM
            ssc_cost = self.inv.get_price("ssc_2x") * v.working_volume_ml
            steps.append(self.op_incubate(vessel_id, 15, temp_c=25.0))
        else:
            anchor_cost = 0
            ssc_cost = 0
        
        # 2. Incorporation (3 min @ 60°C)
        # MiSeq reagent kit (per cycle cost)
        incorporation_cost = self.inv.get_price("miseq_reagent_v2_cycle")
        steps.append(self.op_incubate(vessel_id, 3, temp_c=60.0))
        
        # 3. Washing (2x: 4 washes + 6 min incubation)
        # PR2 buffer (from MiSeq kit, included in cycle cost)
        wash_cost = 0  # Included in MiSeq kit
        for _ in range(2):
            steps.append(self.op_incubate(vessel_id, 6, temp_c=60.0))
        
        # 4. Imaging (4-color + Hoechst fiducial)
        # Use 10x objective for SBS (lower mag, higher throughput)
        imaging_cost = 0  # Handled separately by op_imaging
        
        # 5. Cleavage (2 min @ 60°C, 4x iterations)
        # Cleavage reagent (from MiSeq kit, included in cycle cost)
        cleavage_cost = 0  # Included in MiSeq kit
        for _ in range(4):
            steps.append(self.op_incubate(vessel_id, 2, temp_c=60.0))
        
        total_mat_cost = anchor_cost + ssc_cost + incorporation_cost + wash_cost + cleavage_cost
        
        # Instrument cost
        if automated:
            # Automated: liquid handler + heater/shaker + robot
            instrument_cost = 5.0  # Per cycle
        else:
            # Manual: just incubator time
            instrument_cost = 2.0
        
        return UnitOp(
            uo_id=f"SBS_Cycle{cycle_number}_{vessel_id}",
            name=f"SBS Cycle {cycle_number} ({'Automated' if automated else 'Manual'})",
            layer="genetic_supply_chain",
            category="sequencing",
            time_score=1,
            cost_score=1,
            automation_fit=2 if automated else 0,
            failure_risk=1,
            staff_attention=0 if automated else 2,
            instrument="SBS System" if automated else "Incubator",
            material_cost_usd=total_mat_cost,
            instrument_cost_usd=instrument_cost
        )

    def op_count(self, vessel_id: str, method: str = "automated") -> UnitOp:
        """
        Count cells using various methods.
        
        Args:
            vessel_id: Vessel containing cells
            method: "automated", "hemocytometer", or "flow_cytometer"
            
        Returns:
            UnitOp for cell counting
        """
        if method == "automated":
            # Automated counter (e.g., Countess, Vi-CELL)
            # Cost: Cassette + Trypan Blue
            slide_cost = self.inv.get_price("cell_counter_cassette")
            trypan_cost = 0.01 * self.inv.get_price("trypan_blue")  # 10uL
            
            return UnitOp(
                uo_id="Count_Automated",
                name="Count Cells (Automated)",
                layer="atomic",
                category="qc",
                time_score=1,
                cost_score=0,
                automation_fit=1,
                failure_risk=0,
                staff_attention=1,
                instrument="Cell Counter",
                material_cost_usd=slide_cost + trypan_cost,
                instrument_cost_usd=0.5
            )
            
        elif method == "hemocytometer":
            # Manual hemocytometer
            # Cost: Only trypan blue (reusable hemocytometer)
            trypan_cost = 0.01 * self.inv.get_price("trypan_blue")  # 10uL
            
            return UnitOp(
                uo_id="Count_Hemocytometer",
                name="Count Cells (Hemocytometer)",
                layer="atomic",
                category="qc",
                time_score=2,  # Slower, manual
                cost_score=0,
                automation_fit=0,  # Manual only
                failure_risk=1,  # User-dependent
                staff_attention=3,  # High attention required
                instrument="Microscope",
                material_cost_usd=trypan_cost,
                instrument_cost_usd=2.0  # Microscope time
            )
            
        elif method == "flow_cytometer":
            # Flow cytometer counting (most accurate)
            # Cost: Counting beads
            beads_cost = 0.5  # ~$0.50 per sample for counting beads
            
            return UnitOp(
                uo_id="Count_Flow",
                name="Count Cells (Flow Cytometer)",
                layer="atomic",
                category="qc",
                time_score=1,
                cost_score=1,
                automation_fit=1,
                failure_risk=0,
                staff_attention=1,
                instrument="Flow Cytometer",
                material_cost_usd=beads_cost,
                instrument_cost_usd=5.0  # Flow cytometer time
            )
            
        else:
            raise ValueError(f"Unknown counting method: {method}")

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
                    # Legacy support or error if library is empty
                    # For now, if we hit a string, we try to create a dummy op if library fails
                    try:
                        uo = library.get(item)
                    except:
                        # Fallback for legacy strings if library is gone
                        uo = UnitOp(
                            uo_id=item, name=item, layer=layer_name, category="legacy",
                            time_score=0, cost_score=0, automation_fit=0, failure_risk=0,
                            staff_attention=0, instrument=None, material_cost_usd=0.0, instrument_cost_usd=0.0
                        )
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

# Legacy Recipes (Commented out as they rely on static ops)
# def get_posh_full_stack_recipe() -> AssayRecipe:
#     ...

# def get_perturb_seq_recipe() -> AssayRecipe:
#     ...

def get_bulk_rna_qc_recipe(ops: 'ParametricOps') -> AssayRecipe:
    return AssayRecipe(
        name="Bulk_RNA_QC",
        layers={
            "genetic_supply_chain": [], # Not relevant
            "cell_prep": [
                (ops.op_thaw("plate_6well"), 1),  # Thaw_parental_cells
                (ops.op_feed("plate_6well"), 3), # Run_differentiation_protocol (mock)
                (ops.op_harvest("plate_6well"), 1), # Harvest_cells_for_RNA
            ],
            "phenotyping": [
                (ops.op_bulk_rna_seq(1), 1), # RNA_extraction_bulk
            ],
            "compute": [
                (ops.op_compute_demux(1), 1), # Demultiplex_bulk_reads
                (ops.op_compute_analysis("alignment", 1), 1), # Alignment_and_gene_counts_bulk
                (ops.op_compute_analysis("qc_metrics", 1), 1), # Bulk_QC_metrics
                (ops.op_compute_analysis("embedding", 1), 1), # Expression_embedding_bulk
            ]
        }
    )

def get_spin_up_immortalized_line_recipe(ops: 'ParametricOps', cell_line: str = "HepG2") -> AssayRecipe:
    return AssayRecipe(
        name=f"Spin_Up_{cell_line}_Master_Bank",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (ops.op_purchase_cell_line(cell_line), 1),             # Buy vial
                (ops.op_thaw("plate_6well"), 1),   # Thaw and seed
                (ops.op_passage("plate_6well"), 2), # Expand (approx 2 passages)
                (ops.op_freeze(10), 1),# Keep generic freeze for now or implement op_freeze
                (ops.op_store_sample("ln2", 12), 1),              # Controlled rate freeze -> Store
                (ops.op_store_sample("ln2", 12), 1),              # Store in LN2
                (ops.op_qc_test("mycoplasma"), 1),              # Mycoplasma test
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
                (ops.op_purchase_cell_line("iPSC"), 1),              # Buy vial
                (ops.op_thaw("plate_6well"), 1),   # Thaw and seed
                (ops.op_passage("plate_6well"), 2), # Expand
                (ops.op_freeze(10), 1),# Freeze
                (ops.op_store_sample("ln2", 12), 1),              # Store in LN2
                (ops.op_qc_test("mycoplasma"), 1),              # Mycoplasma test
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
    return AssayRecipe(
        name=f"MCB_to_WCB_10x1e6_{cell_type}",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (ops.op_thaw("plate_6well"), 1),          # Thaw MCB
                (ops.op_passage("plate_6well"), 3),   # Expand to WCB (approx 3 passages)
                (ops.op_freeze(10), 1),  # Freeze 10 vials
                (ops.op_store_sample("ln2", 12), 1),          # Store
                (ops.op_qc_test("mycoplasma"), 1),          # Mycoplasma test
            ],
            "phenotyping": [],
            "compute": []
        }
    )

def get_imicroglia_differentiation_recipe(ops: 'ParametricOps') -> AssayRecipe:
    return AssayRecipe(
        name="iMicroglia_Differentiation_9well_Variance",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (ops.op_thaw("plate_12well"), 1), # Thaw WCB vial
                (ops.op_coat("plate_12well", ["pdl", "laminin_521"]), 3),   # Coat 3 plates
                (ops.op_passage("plate_12well"), 1),   # Seed 9 wells (1 op covers seeding event)
                (ops.op_feed("plate_12well", "adv_dmem_f12", ["revitacell", "glutamax", "doxycycline", "il34", "gmcsf", "mcsf", "tgfb1", "cx3cl1"]), 9),   # Feed 9 wells for 15 days
                (ops.op_harvest("plate_12well"), 1),   # Harvest 9 wells (1 op covers harvest event)
            ],
            "phenotyping": [
                (ops.op_bulk_rna_seq(9), 1),   # Bulk RNA-seq 9 samples
            ],
            "compute": [
                (ops.op_compute_demux(9), 1),     # Demultiplex 9 samples
                (ops.op_compute_analysis("alignment", 9), 1),     # Alignment 9 samples
                (ops.op_compute_analysis("qc_metrics", 1), 1),     # QC metrics
                (ops.op_compute_analysis("embedding", 1), 1),     # Expression embedding
            ]
        }
    )

def get_ngn2_differentiation_recipe(ops: 'ParametricOps') -> AssayRecipe:
    return AssayRecipe(
        name="NGN2_Differentiation_9well_Variance",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (ops.op_thaw("plate_12well"), 1),         # Thaw WCB vial
                (ops.op_feed("plate_12well", "adv_dmem_f12", ["n2_supp", "glutamax", "doxycycline", "puromycin"]), 3*9),# Induction feeds (3 days * 9 wells)
                (ops.op_coat("plate_12well", ["plo", "laminin_521"]), 3),       # Coat 3 destination plates
                (ops.op_passage("plate_12well"), 1),    # Harvest and replate
                (ops.op_feed("plate_12well", "neurobasal", ["b27_supp", "n2_supp", "glutamax", "bdnf", "gdnf", "cntf"]), 7*9)# Maturation feeds (7 feeds * 9 wells)
            ],
            "phenotyping": [
                (ops.op_bulk_rna_seq(9), 1),           # Bulk RNA-seq 9 samples
            ],
            "compute": [
                (ops.op_compute_demux(9), 1),
                (ops.op_compute_analysis("alignment", 9), 1),
                (ops.op_compute_analysis("qc_metrics", 1), 1),
                (ops.op_compute_analysis("embedding", 1), 1),
            ]
        }
    )

def get_imicroglia_phagocytosis_recipe(ops: 'ParametricOps') -> AssayRecipe:
    return AssayRecipe(
        name="iMicroglia_Phagocytosis_9well",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (ops.op_thaw("plate_12well"), 1), # Thaw WCB vial
                (ops.op_coat("plate_12well", ["pdl", "laminin_521"]), 3),   # Coat 3 plates
                (ops.op_passage("plate_12well"), 1),   # Seed 9 wells
                (ops.op_feed("plate_12well", "adv_dmem_f12", ["revitacell", "glutamax", "doxycycline", "il34", "gmcsf", "mcsf", "tgfb1", "cx3cl1"]), 9),   # Feed 9 wells for 15 days
            ],
            "phenotyping": [
                (ops.op_flow_stain(9, "live"), 1), # Add reagent to 9 wells (mock with flow stain)
                (ops.op_flow_acquisition(9), 1),        # Image 3 plates (batch)
            ],
            "compute": [
                (ops.op_compute_analysis("image_analysis", 9), 1),     # Image analysis
            ]
        }
    )

def get_posh_screening_recipe(
    ops: 'ParametricOps',
    num_grnas: int = 1000,
    representation: int = 250,
    vessel: str = "plate_96well",
    stressor: str = "tbhp",
    stressor_conc_um: float = 100.0,
    treatment_duration_h: float = 24.0
) -> AssayRecipe:
    """
    POSH (Pooled Optical Screening in Human Cells) full workflow.
    
    Assumes you already have transduced + selected cells.
    This recipe covers: Stressor Treatment → Fixation → Cell Painting → Imaging
    
    Args:
        ops: ParametricOps instance
        num_grnas: Library size (for documentation/tracking)
        representation: Coverage multiplier
        vessel: Plate format for screening
        stressor: Stressor compound (tbhp, tunicamycin, etc.)
        stressor_conc_um: Stressor concentration in µM
        treatment_duration_h: Treatment duration in hours
    """
    return AssayRecipe(
        name=f"POSH_Screen_{num_grnas}g_{stressor}_{vessel}",
        layers={
            "genetic_supply_chain": [],  # LV transduction already done
            "cell_prep": [
                # Stressor treatment
                (ops.op_stressor_treatment(
                    vessel, 
                    stressor=stressor, 
                    concentration_um=stressor_conc_um,
                    duration_h=treatment_duration_h
                ), 1),
            ],
            "phenotyping": [
                # Fixation
                (ops.op_fix_cells(vessel), 1),
                # Cell Painting
                (ops.op_cell_painting(vessel, dye_panel="standard_5channel"), 1),
                # Imaging
                (ops.op_imaging(vessel, num_sites_per_well=9, channels=5, objective="20x"), 1),
            ],
            "compute": [
                # Image analysis (placeholder - would need to define op_image_analysis)
                (ops.op_compute_analysis("image_analysis", 96), 1),  # 96 wells
            ]
        }
    )

def get_vanilla_posh_complete_recipe(
    ops: 'ParametricOps',
    num_grnas: int = 1000,
    representation: int = 250,
    vessel: str = "plate_96well",
    stressor: str = "tbhp",
    stressor_conc_um: float = 100.0,
    treatment_duration_h: float = 24.0,
    num_sbs_cycles: int = 13,
    use_ps6: bool = False,
    automated: bool = False
) -> AssayRecipe:
    """
    Complete Vanilla POSH (CellPaint-POSH) workflow.
    
    Full workflow: Fixation → RT → RCA → Cell Painting → SBS (13 cycles) → Analysis
    
    Args:
        ops: ParametricOps instance
        num_grnas: Library size
        representation: Coverage multiplier
        vessel: Plate format (plate_96well, plate_384well, etc.)
        stressor: Stressor compound (tbhp, tunicamycin, thapsigargin, etc.)
        stressor_conc_um: Stressor concentration in µM
        treatment_duration_h: Stressor treatment duration in hours
        num_sbs_cycles: Number of SBS cycles (default: 13 for full barcode)
        use_ps6: Whether to include pS6 biomarker (6th channel)
        automated: Whether to use automated liquid handling
    """
    
    # Determine dye panel
    dye_panel = "posh_6channel" if use_ps6 else "posh_5channel"
    
    # SBS cycles
    sbs_ops = [(ops.op_sbs_cycle(vessel, cycle_number=i+1, automated=automated), 1) 
               for i in range(num_sbs_cycles)]
    
    return AssayRecipe(
        name=f"VanillaPOSH_{num_grnas}g_{stressor}_{vessel}_{'auto' if automated else 'manual'}",
        layers={
            "genetic_supply_chain": [
                # RT-RCA workflow
                (ops.op_reverse_transcription(vessel, duration_h=16.0, temp_c=37.0), 1),
                (ops.op_gap_fill_ligation(vessel, duration_min=90, temp_c=45.0), 1),
                (ops.op_rolling_circle_amplification(vessel, duration_h=16.0, temp_c=30.0), 1),
            ] + sbs_ops,  # Add all SBS cycles
            "cell_prep": [
                # Stressor treatment (optional, before fixation)
                (ops.op_stressor_treatment(
                    vessel,
                    stressor=stressor,
                    concentration_um=stressor_conc_um,
                    duration_h=treatment_duration_h
                ), 1),
            ],
            "phenotyping": [
                # Fixation
                (ops.op_fix_cells(vessel), 1),
                # Cell Painting (ISS-compatible)
                (ops.op_cell_painting(vessel, dye_panel=dye_panel), 1),
                # Phenotyping imaging (20x, 5-6 channels)
                (ops.op_imaging(vessel, num_sites_per_well=9, channels=6 if use_ps6 else 5, objective="20x"), 1),
                # SBS imaging (10x, 4-color + Hoechst, per cycle)
                # Note: Imaging happens within each SBS cycle, but we track it here for cost
                (ops.op_imaging(vessel, num_sites_per_well=9, channels=5, objective="10x"), num_sbs_cycles),
            ],
            "compute": [
                # Image processing and analysis
                (ops.op_compute_analysis("illumination_correction", 96), 1),
                (ops.op_compute_analysis("cell_segmentation", 96), 1),
                (ops.op_compute_analysis("image_registration", 96), 1),
                (ops.op_compute_analysis("base_calling", 96 * num_sbs_cycles), 1),
                (ops.op_compute_analysis("barcode_stitching", 96), 1),
                (ops.op_compute_analysis("feature_extraction", 96), 1),  # CellStats or DINO
            ]
        }
    )

def get_flow_live_condition_recipe(ops: 'ParametricOps') -> AssayRecipe:
    return AssayRecipe(
        name="Flow_Live_1_Condition_3_Reps",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (ops.op_thaw("plate_24well"), 3), # 3 replicates
            ],
            "phenotyping": [
                (ops.op_flow_stain(3, "live"), 1),
                (ops.op_flow_acquisition(3), 1),
            ],
            "compute": [
                (ops.op_compute_demux(3), 1), # Process 3 files
            ]
        }
    )

def get_flow_fixed_condition_recipe(ops: 'ParametricOps') -> AssayRecipe:
    return AssayRecipe(
        name="Flow_Fixed_1_Condition_3_Reps",
        layers={
            "genetic_supply_chain": [],
            "cell_prep": [
                (ops.op_thaw("plate_6well"), 3), # 3 replicates of 1M cells
            ],
            "phenotyping": [
                (ops.op_flow_stain(3, "fixed"), 1),
                (ops.op_flow_acquisition(3), 1),
            ],
            "compute": [
                (ops.op_compute_demux(3), 1), # Process 3 files
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
                (ops.op_harvest("plate_24well"), 6),   # Harvest 6 wells
                (ops.op_flow_acquisition(6), 1), # Run 6 samples
            ],
            "compute": [
                (ops.op_compute_demux(6), 1), # Analyze 6 files
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
                (ops.op_feed(vessel, supplements=["puromycin"]), 5 * num_vessels),  # Selection feeds
                (ops.op_passage(vessel), num_vessels),       
            ],
            "phenotyping": [
                (ops.op_flow_stain(2, "fixed"), 1),   # QC checks (sample based, not vessel based)
                (ops.op_flow_acquisition(2), 1), 
            ],
            "compute": [
                (ops.op_compute_demux(2), 1), 
            ]
        }
    )

def get_lv_production_recipe(ops: 'ParametricOps') -> AssayRecipe:
    # LV Production (Outsourced Cloning + In-house Transfection)
    # 1. Outsourced Cloning (Oligos -> Plasmid)
    # 2. Transfection (T175)
    # 3. Harvest & Concentrate
    # 4. Titration
    
    vessel = "flask_t175"
    
    return AssayRecipe(
        name="LV_Production_Outsourced_Cloning",
        layers={
            "genetic_supply_chain": [
                (ops.op_outsource_service("oligo_synthesis"), 1), # 1. Oligo Synthesis
                (ops.op_outsource_service("cloning"), 1),         # 2. Cloning
                (ops.op_outsource_service("ngs_verification"), 1),# 3. NGS Verification
                (ops.op_outsource_service("plasmid_expansion"), 1),# 4. Plasmid Expansion
                (ops.op_transfect(vessel), 1), # 5. LV Prep (Transfect)
                (ops.op_harvest(vessel), 1),   #    LV Prep (Conc)
                (ops.op_p24_elisa(1), 1),           #    LV Prep (QC)
            ],
            "cell_prep": [],
            "phenotyping": [],
            "compute": []
        }
    )
