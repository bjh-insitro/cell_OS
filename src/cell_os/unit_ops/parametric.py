"""
Parametric Operations.
Unifies all operation types (Liquid Handling, Protocols, Imaging, Analysis) 
into a single access interface.
"""

from typing import List, Optional
from .base import VesselLibrary
from .liquid_handling import LiquidHandlingOps
from .protocols import ProtocolOps
from .imaging import ImagingOps
from .analysis import AnalysisOps

# Import cell line database for automatic method selection
try:
    from cell_os.cell_line_database import get_cell_line_profile, get_optimal_methods
    CELL_LINE_DB_AVAILABLE = True
except ImportError:
    CELL_LINE_DB_AVAILABLE = False


class ParametricOps(ProtocolOps):
    """Unified interface for all parametric operations.
    Inherits from all specialized operation classes.
    """
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.inv = pricing_inv
        
        # Initialize parent classes
        LiquidHandlingOps.__init__(self, vessel_lib, pricing_inv)
        ProtocolOps.__init__(self, vessel_lib, pricing_inv)
        ImagingOps.__init__(self, vessel_lib, pricing_inv)
        AnalysisOps.__init__(self, vessel_lib, pricing_inv)
        
        # Resolver for protocol selection (optional)
        self.resolver = None
    
    def get_cell_line_defaults(self, cell_line: str):
        """Get default parameters for a cell line from database."""
        if CELL_LINE_DB_AVAILABLE:
            return get_cell_line_profile(cell_line)
        return {}

    def op_centrifuge(self, vessel_id: str, duration_min: float, speed_rpm: float = 1000, temp_c: float = 25.0, material_cost_usd: float = 0.0, instrument_cost_usd: float = 0.0):
        """Centrifuge a vessel."""
        from .base import UnitOp
        
        return UnitOp(
            uo_id=f"Centrifuge_{vessel_id}",
            name=f"Centrifuge {vessel_id} ({duration_min}min @ {speed_rpm}rpm)",
            layer="atomic",
            category="separation",
            time_score=duration_min,
            cost_score=1,
            automation_fit=3,
            failure_risk=1,
            staff_attention=1,
            instrument="Centrifuge",
            material_cost_usd=material_cost_usd,
            instrument_cost_usd=instrument_cost_usd if instrument_cost_usd > 0 else 0.5,
            sub_steps=[]
        )

    # --- TIER 1: CORE CELL CULTURE OPERATIONS ---
    
    def op_thaw(self, vessel_id: str, cell_line: str = None):
        """Thaw cells from cryovial into culture vessel."""
        from .base import UnitOp
        
        steps = []
        
        # Helper to get single item cost
        def get_single_cost(item_id: str):
            # Retrieves the price for one logical unit (unit_price_usd).
            return self.inv.get_price(item_id)
        
        # 1. Coating (if needed - check cell line database)
        coating_needed = False
        coating_reagent = "matrigel"  # Default
        media = "dmem_10fbs"  # Default
        
        if cell_line and CELL_LINE_DB_AVAILABLE:
            profile = get_cell_line_profile(cell_line)
            if profile:
                coating_needed = profile.coating_required
                if coating_needed and profile.coating:
                    coating_reagent = profile.coating
                if profile.media:
                    media = profile.media
        elif cell_line:
            # Fallback for when database is not available
            if cell_line.lower() in ["ipsc", "hesc"]:
                coating_needed = True
                coating_reagent = "matrigel"
                media = "mtesr_plus_kit"
        
        if coating_needed:
            steps.append(self.op_coat(vessel_id, agents=[coating_reagent]))
        
        # 2. Prepare media volume
        media_vol_ml = 10.0  # Standard thaw volume
        
        # 3. Thaw vial in water bath
        # Simulated as incubation step
        steps.append(self.op_incubate(
            vessel_id="water_bath",
            duration_min=2.0,
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=0.5
        ))
        
        # 4. Transfer cells to vessel
        # Using pipette for cell transfer
        pipette_cost = get_single_cost("pipette_2ml")
        steps.append(self.op_aspirate(
            vessel_id="cryovial",
            volume_ml=1.0,
            material_cost_usd=pipette_cost
        ))
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=1.0,
            liquid_name=media,
            material_cost_usd=pipette_cost
        ))
        
        # 5. Add media to vessel
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=media_vol_ml,
            liquid_name=media,
            material_cost_usd=get_single_cost("pipette_10ml")
        ))
        
        # 6. Incubate overnight
        steps.append(self.op_incubate(
            vessel_id=vessel_id,
            duration_min=960.0,  # 16 hours
            temp_c=37.0,
            co2_pct=5.0,
            material_cost_usd=0.0,
            instrument_cost_usd=2.0
        ))
        
        # 7. Media change (remove DMSO)
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=media_vol_ml,
            material_cost_usd=get_single_cost("pipette_10ml")
        ))
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=media_vol_ml,
            liquid_name=media,
            material_cost_usd=get_single_cost("pipette_10ml")
        ))
        
        # Calculate total costs
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Add cryovial cost
        cryovial_cost = get_single_cost("cryovial_1_8ml")
        
        # Add media cost (rough estimate: $0.50/mL for mTeSR, $0.05/mL for DMEM)
        media_cost_per_ml = 0.50 if media == "mtesr_plus_kit" else 0.05
        media_cost = media_vol_ml * 2 * media_cost_per_ml  # 2x media changes
        
        return UnitOp(
            uo_id=f"Thaw_{vessel_id}",
            name=f"Thaw cells into {vessel_id}" + (f" ({cell_line})" if cell_line else ""),
            layer="culture",
            category="culture",
            time_score=1000,  # ~16 hours
            cost_score=2,
            automation_fit=2,
            failure_risk=3,
            staff_attention=2,
            instrument="Biosafety Cabinet + Incubator",
            material_cost_usd=total_mat + cryovial_cost + media_cost,
            instrument_cost_usd=total_inst + 10.0,
            sub_steps=steps
        )

    def op_passage(self, vessel_id: str, ratio: int = 1, dissociation_method: str = "accutase", cell_line: str = None):
        """Passage cells (dissociate, split, re-plate)."""
        from .base import UnitOp
        
        steps = []
        
        # Helper to get single item cost
        def get_single_cost(item_id: str):
            return self.inv.get_price(item_id)
        
        # Auto-select dissociation method based on cell line
        if cell_line and dissociation_method == "accutase":
            if cell_line.lower() in ["ipsc", "hesc"]:
                dissociation_method = "accutase"  # Gentle for stem cells
            elif cell_line.lower() in ["u2os", "hek293t", "hela"]:
                dissociation_method = "trypsin"  # Standard for adherent lines
        
        # 1. Aspirate old media
        media_vol = 10.0  # Assume 10mL for T75
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=media_vol,
            material_cost_usd=get_single_cost("pipette_10ml")
        ))
        
        # 2. Wash with PBS
        pbs_vol = 5.0
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=pbs_vol,
            liquid_name="pbs",
            material_cost_usd=get_single_cost("pipette_10ml")
        ))
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=pbs_vol,
            material_cost_usd=get_single_cost("pipette_10ml")
        ))
        
        # 3. Add dissociation reagent
        dissociation_vol = 2.0
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=dissociation_vol,
            liquid_name=dissociation_method,
            material_cost_usd=get_single_cost("pipette_5ml")
        ))
        
        # 4. Incubate
        incubation_time = 5.0 if dissociation_method == "trypsin" else 10.0
        steps.append(self.op_incubate(
            vessel_id=vessel_id,
            duration_min=incubation_time,
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=0.5
        ))
        
        # 5. Neutralize/collect cells
        media = "mtesr_plus_kit" if cell_line and cell_line.lower() in ["ipsc", "hesc"] else "dmem_10fbs"
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=8.0,
            liquid_name=media,
            material_cost_usd=get_single_cost("pipette_10ml")
        ))
        
        # 6. Triturate (mix)
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=10.0,
            material_cost_usd=get_single_cost("pipette_10ml")
        ))
        
        # 7. Dispense into new vessel(s)
        # If ratio > 1, split into multiple vessels
        vol_per_vessel = 10.0 / ratio
        for i in range(ratio):
            new_vessel_id = f"{vessel_id}_passage_{i+1}" if ratio > 1 else f"{vessel_id}_passaged"
            steps.append(self.op_dispense(
                vessel_id=new_vessel_id,
                volume_ml=vol_per_vessel,
                liquid_name=media,
                material_cost_usd=get_single_cost("pipette_10ml")
            ))
        
        # 8. Add fresh media to each new vessel
        for i in range(ratio):
            new_vessel_id = f"{vessel_id}_passage_{i+1}" if ratio > 1 else f"{vessel_id}_passaged"
            steps.append(self.op_dispense(
                vessel_id=new_vessel_id,
                volume_ml=media_vol - vol_per_vessel,
                liquid_name=media,
                material_cost_usd=get_single_cost("pipette_10ml")
            ))
        
        # Calculate total costs
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Add reagent costs
        dissociation_cost = 2.0 * (2.0 if dissociation_method == "accutase" else 0.5)  # Accutase is more expensive
        pbs_cost = pbs_vol * 0.01  # PBS is cheap
        media_cost_per_ml = 0.50 if media == "mtesr_plus_kit" else 0.05
        media_cost = media_vol * ratio * media_cost_per_ml
        
        # Add flask cost for new vessels
        flask_cost = get_single_cost("flask_T75") * ratio
        
        return UnitOp(
            uo_id=f"Passage_{vessel_id}_1:{ratio}",
            name=f"Passage {vessel_id} (1:{ratio} split, {dissociation_method})" + (f" [{cell_line}]" if cell_line else ""),
            layer="culture",
            category="culture",
            time_score=30,
            cost_score=2,
            automation_fit=3,
            failure_risk=2,
            staff_attention=3,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat + dissociation_cost + pbs_cost + media_cost + flask_cost,
            instrument_cost_usd=total_inst + 5.0,
            sub_steps=steps
        )

    def op_feed(self, vessel_id: str, media: str = None, cell_line: str = None, supplements: List[str] = None):
        """Feed cells (media change)."""
        from .base import UnitOp
        
        steps = []
        
        # Auto-select media based on cell line
        if media is None and cell_line:
            if cell_line.lower() in ["ipsc", "hesc"]:
                media = "mtesr_plus_kit"
            else:
                media = "dmem_10fbs"
        elif media is None:
            media = "dmem_10fbs"  # Default
        
        media_vol = 10.0  # Standard for T75
        
        # 1. Aspirate old media
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=media_vol,
            material_cost_usd=self.inv.get_price("pipette_10ml")
        ))
        
        # 2. Add fresh media
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=media_vol,
            liquid_name=media,
            material_cost_usd=self.inv.get_price("pipette_10ml")
        ))
        
        # 3. Add supplements if specified
        if supplements:
            for supp in supplements:
                steps.append(self.op_dispense(
                    vessel_id=vessel_id,
                    volume_ml=0.1,  # Small volume for supplements
                    liquid_name=supp,
                    material_cost_usd=self.inv.get_price("pipette_200ul")
                ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Add media cost
        media_cost_per_ml = 0.50 if media == "mtesr_plus_kit" else 0.05
        media_cost = media_vol * media_cost_per_ml
        
        # Add supplement costs
        supplement_cost = len(supplements) * 5.0 if supplements else 0.0
        
        return UnitOp(
            uo_id=f"Feed_{vessel_id}",
            name=f"Feed {vessel_id} ({media})" + (f" + {len(supplements)} supplements" if supplements else ""),
            layer="culture",
            category="culture",
            time_score=10,
            cost_score=1,
            automation_fit=4,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat + media_cost + supplement_cost,
            instrument_cost_usd=total_inst + 2.0,
            sub_steps=steps
        )

    def op_transduce(self, vessel_id: str, virus_vol_ul: float = 10.0, method: str = "passive"):
        """Transduce cells with viral vector."""
        from .base import UnitOp
        
        steps = []
        
        # 1. Add virus to media
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=virus_vol_ul / 1000.0,
            liquid_name="lentivirus",
            material_cost_usd=self.inv.get_price("pipette_200ul")
        ))
        
        # 2. If spinoculation, centrifuge
        if method == "spinoculation":
            steps.append(self.op_centrifuge(
                vessel_id=vessel_id,
                duration_min=90.0,
                speed_rpm=1000,
                temp_c=32.0,
                material_cost_usd=0.0,
                instrument_cost_usd=5.0
            ))
        
        # 3. Incubate
        incubation_time = 240.0 if method == "passive" else 120.0  # 4h passive, 2h spinoculation
        steps.append(self.op_incubate(
            vessel_id=vessel_id,
            duration_min=incubation_time,
            temp_c=37.0,
            co2_pct=5.0,
            material_cost_usd=0.0,
            instrument_cost_usd=2.0
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Virus is expensive
        virus_cost = virus_vol_ul * 10.0  # $10/µL estimate
        
        return UnitOp(
            uo_id=f"Transduce_{vessel_id}_{method}",
            name=f"Transduce {vessel_id} ({method}, {virus_vol_ul}µL virus)",
            layer="genetic_modification",
            category="transduction",
            time_score=240 if method == "passive" else 210,
            cost_score=4,
            automation_fit=2,
            failure_risk=3,
            staff_attention=2,
            instrument="Biosafety Cabinet" + (" + Centrifuge" if method == "spinoculation" else ""),
            material_cost_usd=total_mat + virus_cost,
            instrument_cost_usd=total_inst,
            sub_steps=steps
        )

    def op_coat(self, vessel_id: str, agents: List[str] = None):
        """Coat vessel with ECM or other agents."""
        from .base import UnitOp
        
        if agents is None:
            agents = ["matrigel"]
        
        steps = []
        
        coating_vol = 2.0  # mL
        
        for agent in agents:
            # 1. Add coating agent
            steps.append(self.op_dispense(
                vessel_id=vessel_id,
                volume_ml=coating_vol,
                liquid_name=agent,
                material_cost_usd=self.inv.get_price("pipette_5ml")
            ))
        
        # 2. Incubate
        steps.append(self.op_incubate(
            vessel_id=vessel_id,
            duration_min=60.0,
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=1.0
        ))
        
        # 3. Aspirate coating solution
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=coating_vol,
            material_cost_usd=self.inv.get_price("pipette_5ml")
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Coating agents are expensive (especially Matrigel)
        coating_cost = sum(50.0 if agent == "matrigel" else 5.0 for agent in agents)
        
        return UnitOp(
            uo_id=f"Coat_{vessel_id}_{'_'.join(agents)}",
            name=f"Coat {vessel_id} with {', '.join(agents)}",
            layer="preparation",
            category="coating",
            time_score=70,
            cost_score=3,
            automation_fit=3,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet + Incubator",
            material_cost_usd=total_mat + coating_cost,
            instrument_cost_usd=total_inst,
            sub_steps=steps
        )

    def op_transfect(self, vessel_id: str, method: str = "pei"):
        """Transfect cells with plasmid DNA."""
        from .base import UnitOp
        
        steps = []
        
        # 1. Prepare transfection complex
        # (simplified - real protocol has multiple steps)
        steps.append(self.op_dispense(
            vessel_id="tube_15ml",
            volume_ml=1.0,
            liquid_name="opti_mem",
            material_cost_usd=self.inv.get_price("tube_15ml_conical")
        ))
        
        # 2. Add DNA
        steps.append(self.op_dispense(
            vessel_id="tube_15ml",
            volume_ml=0.01,
            liquid_name="plasmid_dna",
            material_cost_usd=self.inv.get_price("pipette_200ul")
        ))
        
        # 3. Add transfection reagent
        reagent = method.lower()  # pei, lipofectamine, etc.
        steps.append(self.op_dispense(
            vessel_id="tube_15ml",
            volume_ml=0.05,
            liquid_name=reagent,
            material_cost_usd=self.inv.get_price("pipette_200ul")
        ))
        
        # 4. Incubate complex
        steps.append(self.op_incubate(
            vessel_id="tube_15ml",
            duration_min=20.0,
            temp_c=25.0,
            material_cost_usd=0.0,
            instrument_cost_usd=0.5
        ))
        
        # 5. Add to cells
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=1.0,
            liquid_name="transfection_complex",
            material_cost_usd=self.inv.get_price("pipette_2ml")
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Reagent costs
        reagent_cost = 10.0 if method == "pei" else 50.0  # Lipofectamine is expensive
        dna_cost = 20.0  # Plasmid prep cost
        
        return UnitOp(
            uo_id=f"Transfect_{vessel_id}_{method}",
            name=f"Transfect {vessel_id} ({method})",
            layer="genetic_modification",
            category="transfection",
            time_score=40,
            cost_score=3,
            automation_fit=2,
            failure_risk=3,
            staff_attention=3,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat + reagent_cost + dna_cost,
            instrument_cost_usd=total_inst + 2.0,
            sub_steps=steps
        )

    def op_harvest(self, vessel_id: str, dissociation_method: str = "accutase"):
        """Harvest cells for freezing or analysis."""
        from .base import UnitOp
        
        steps = []
        
        # Similar to passage but collect into tube instead of re-plating
        
        # 1. Aspirate media
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=10.0,
            material_cost_usd=self.inv.get_price("pipette_10ml")
        ))
        
        # 2. Wash with PBS
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=5.0,
            liquid_name="pbs",
            material_cost_usd=self.inv.get_price("pipette_10ml")
        ))
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=5.0,
            material_cost_usd=self.inv.get_price("pipette_10ml")
        ))
        
        # 3. Add dissociation reagent
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=2.0,
            liquid_name=dissociation_method,
            material_cost_usd=self.inv.get_price("pipette_5ml")
        ))
        
        # 4. Incubate
        steps.append(self.op_incubate(
            vessel_id=vessel_id,
            duration_min=10.0,
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=0.5
        ))
        
        # 5. Collect cells into tube
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=2.0,
            material_cost_usd=self.inv.get_price("tube_50ml_conical")
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        dissociation_cost = 2.0 * (2.0 if dissociation_method == "accutase" else 0.5)
        
        return UnitOp(
            uo_id=f"Harvest_{vessel_id}",
            name=f"Harvest cells from {vessel_id} ({dissociation_method})",
            layer="culture",
            category="harvest",
            time_score=20,
            cost_score=1,
            automation_fit=3,
            failure_risk=2,
            staff_attention=2,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat + dissociation_cost,
            instrument_cost_usd=total_inst + 3.0,
            sub_steps=steps
        )

    def op_freeze(self, num_vials: int = 10, freezing_media: str = "cryostor"):
        """Freeze cells into cryovials."""
        from .base import UnitOp
        
        steps = []
        
        # Calculate total volume (assuming 1mL per vial + 10% overage/dead volume)
        total_vol = num_vials * 1.1
        
        steps.append(self.op_aspirate("pooled_vessels", total_vol, material_cost_usd=self.inv.get_price("pipette_10ml")))
        steps.append(self.op_dispense("vials", 1.0 * num_vials, freezing_media, material_cost_usd=self.inv.get_price("pipette_10ml")))
        
        # Account for final vials and media cost
        vial_cost = self.inv.get_price("cryovial_1_8ml") * num_vials
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Freeze_{num_vials}vials",
            name=f"Freeze {num_vials} vials ({freezing_media})",
            layer="banking",
            category="culture",
            time_score=60,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat + vial_cost,
            instrument_cost_usd=total_inst + 5.0,
            sub_steps=steps
        )

    # --- TIER 2: QC OPERATIONS ---
    
    def op_mycoplasma_test(self, sample_id: str, method: str = "pcr"):
        """Test for mycoplasma contamination."""
        from .base import UnitOp
        
        steps = []
        
        # 1. Collect sample
        steps.append(self.op_aspirate(
            vessel_id=sample_id,
            volume_ml=1.0,
            material_cost_usd=self.inv.get_price("tube_15ml_conical")
        ))
        
        # 2. Process based on method
        if method == "pcr":
            # DNA extraction
            steps.append(self.op_incubate(
                vessel_id="tube_15ml",
                duration_min=30.0,
                temp_c=95.0,
                material_cost_usd=5.0,  # DNA extraction kit
                instrument_cost_usd=1.0
            ))
            
            # PCR
            steps.append(self.op_incubate(
                vessel_id="pcr_plate",
                duration_min=120.0,
                temp_c=60.0,
                material_cost_usd=10.0,  # PCR reagents
                instrument_cost_usd=5.0
            ))
            
            test_duration = 180  # 3 hours
            test_cost = 25.0
            
        elif method == "culture":
            # Culture-based detection (slower but cheaper)
            steps.append(self.op_incubate(
                vessel_id="culture_plate",
                duration_min=10080.0,  # 7 days
                temp_c=37.0,
                material_cost_usd=15.0,
                instrument_cost_usd=10.0
            ))
            
            test_duration = 10080  # 7 days
            test_cost = 30.0
        
        else:  # luminescence or other rapid methods
            steps.append(self.op_incubate(
                vessel_id="assay_plate",
                duration_min=60.0,
                temp_c=37.0,
                material_cost_usd=50.0,  # Commercial kit
                instrument_cost_usd=10.0
            ))
            
            test_duration = 90  # 1.5 hours
            test_cost = 75.0
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"MycoTest_{sample_id}_{method}",
            name=f"Mycoplasma Test ({method}) - {sample_id}",
            layer="qc",
            category="contamination_test",
            time_score=test_duration,
            cost_score=3,
            automation_fit=4,
            failure_risk=1,
            staff_attention=2,
            instrument="PCR Machine" if method == "pcr" else "Incubator + Plate Reader",
            material_cost_usd=total_mat + test_cost,
            instrument_cost_usd=total_inst,
            sub_steps=steps
        )
    
    def op_sterility_test(self, sample_id: str, duration_days: int = 7):
        """Test for bacterial/fungal contamination."""
        from .base import UnitOp
        
        steps = []
        
        # 1. Collect sample
        steps.append(self.op_aspirate(
            vessel_id=sample_id,
            volume_ml=5.0,
            material_cost_usd=self.inv.get_price("tube_15ml_conical")
        ))
        
        # 2. Inoculate culture media
        steps.append(self.op_dispense(
            vessel_id="culture_bottle",
            volume_ml=5.0,
            liquid_name="tryptic_soy_broth",
            material_cost_usd=5.0
        ))
        
        # 3. Incubate
        steps.append(self.op_incubate(
            vessel_id="culture_bottle",
            duration_min=duration_days * 1440.0,  # Convert days to minutes
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=2.0 * duration_days
        ))
        
        # 4. Visual inspection + optional plating
        steps.append(self.op_incubate(
            vessel_id="agar_plate",
            duration_min=2880.0,  # 2 days
            temp_c=37.0,
            material_cost_usd=3.0,
            instrument_cost_usd=1.0
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"SterilityTest_{sample_id}_{duration_days}d",
            name=f"Sterility Test ({duration_days} days) - {sample_id}",
            layer="qc",
            category="contamination_test",
            time_score=duration_days * 1440 + 2880,
            cost_score=2,
            automation_fit=2,
            failure_risk=1,
            staff_attention=1,
            instrument="Incubator",
            material_cost_usd=total_mat + 15.0,
            instrument_cost_usd=total_inst,
            sub_steps=steps
        )
    
    def op_karyotype(self, sample_id: str, method: str = "g_banding"):
        """Karyotype analysis for chromosomal abnormalities."""
        from .base import UnitOp
        
        steps = []
        
        # 1. Harvest cells in metaphase
        # Add colcemid to arrest in metaphase
        steps.append(self.op_dispense(
            vessel_id=sample_id,
            volume_ml=0.1,
            liquid_name="colcemid",
            material_cost_usd=5.0
        ))
        
        steps.append(self.op_incubate(
            vessel_id=sample_id,
            duration_min=120.0,  # 2 hours
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=1.0
        ))
        
        # 2. Harvest and fix
        steps.append(self.op_aspirate(
            vessel_id=sample_id,
            volume_ml=5.0,
            material_cost_usd=self.inv.get_price("tube_15ml_conical")
        ))
        
        # 3. Process based on method
        if method == "g_banding":
            # Traditional G-banding
            # Slide preparation, staining, imaging
            test_duration = 2880  # 2 days
            test_cost = 200.0  # Labor-intensive
            
        elif method == "fish":
            # FISH for specific chromosomes
            test_duration = 1440  # 1 day
            test_cost = 300.0  # Expensive probes
            
        else:  # "array_cgh" or other molecular methods
            test_duration = 4320  # 3 days
            test_cost = 500.0  # High-throughput
        
        steps.append(self.op_incubate(
            vessel_id="slide",
            duration_min=test_duration,
            temp_c=25.0,
            material_cost_usd=test_cost,
            instrument_cost_usd=50.0
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Karyotype_{sample_id}_{method}",
            name=f"Karyotype ({method}) - {sample_id}",
            layer="qc",
            category="genetic_analysis",
            time_score=test_duration + 120,
            cost_score=4,
            automation_fit=1,
            failure_risk=2,
            staff_attention=4,
            instrument="Microscope" if method == "g_banding" else "Array Scanner",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst,
            sub_steps=steps
        )
    
    def op_endotoxin_test(self, sample_id: str):
        """Test for endotoxin contamination (LAL assay)."""
        from .base import UnitOp
        
        steps = []
        
        # 1. Collect sample
        steps.append(self.op_aspirate(
            vessel_id=sample_id,
            volume_ml=0.1,
            material_cost_usd=self.inv.get_price("tube_15ml_conical")
        ))
        
        # 2. LAL assay
        steps.append(self.op_dispense(
            vessel_id="assay_plate",
            volume_ml=0.1,
            liquid_name="lal_reagent",
            material_cost_usd=25.0  # LAL reagent is expensive
        ))
        
        steps.append(self.op_incubate(
            vessel_id="assay_plate",
            duration_min=60.0,
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=5.0
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"EndotoxinTest_{sample_id}",
            name=f"Endotoxin Test (LAL) - {sample_id}",
            layer="qc",
            category="contamination_test",
            time_score=90,
            cost_score=2,
            automation_fit=4,
            failure_risk=1,
            staff_attention=2,
            instrument="Plate Reader",
            material_cost_usd=total_mat,
            instrument_cost_usd=total_inst,
            sub_steps=steps
        )