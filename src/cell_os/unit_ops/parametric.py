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

    def op_centrifuge(self, vessel_id: str, duration_min: float, speed_rpm: float = 1000, temp_c: float = 25.0, material_cost_usd: float = 0.0, instrument_cost_usd: float = 0.0, name: str = None):
        """Centrifuge a vessel."""
        from .base import UnitOp
        
        if name is None:
            name = f"Centrifuge {vessel_id} ({duration_min}min @ {speed_rpm}rpm)"
        
        return UnitOp(
            uo_id=f"Centrifuge_{vessel_id}",
            name=name,
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
    
    def op_thaw(self, vessel_id: str, cell_line: str = None, skip_coating: bool = False):
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
                coating_needed = profile.coating_required and not skip_coating
                if coating_needed and profile.coating:
                    coating_reagent = profile.coating
                if profile.media:
                    media = profile.media
        elif cell_line:
            # Fallback for when database is not available
            if cell_line.lower() in ["ipsc", "hesc"]:
                coating_needed = True and not skip_coating
                coating_reagent = "matrigel"
                media = "mtesr_plus_kit"
        
        if coating_needed:
            steps.append(self.op_coat(vessel_id, agents=[coating_reagent]))
            
        # Aspirate coating solution (if this cell line requires coating)
        # We do this if we just coated OR if we skipped coating (implying it was done before)
        requires_coating = coating_needed or skip_coating
        # Double check profile if skip_coating is True but we're not sure
        if skip_coating and not requires_coating:
             if profile and profile.coating_required:
                 requires_coating = True
             elif cell_line and cell_line.lower() in ["ipsc", "hesc"]:
                 requires_coating = True

        if requires_coating:
             # Assume standard coating volume for aspiration
             aspirate_vol = 12.5 if "flask_T75" in vessel_id or "flask_t75" in vessel_id.lower() else 2.0
             steps.append(self.op_aspirate(
                vessel_id=vessel_id,
                volume_ml=aspirate_vol,
                material_cost_usd=get_single_cost("pipette_10ml"),
                name=f"Aspirate {aspirate_vol}mL Coating from {vessel_id}"
            ))
        
        # 2. Thaw vial
        steps.append(self.op_incubate(
            vessel_id="water_bath",
            duration_min=2.0,
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=0.5,
            name="Thaw Vial in Water Bath"
        ))
        
        # 3. Add 5mL media to 15mL tube
        tube_id = "tube_15ml"
        tube_cost = get_single_cost("tube_15ml_conical")
        steps.append(self.op_dispense(
            vessel_id=tube_id,
            volume_ml=5.0,
            liquid_name=media,
            material_cost_usd=get_single_cost("pipette_5ml") + (5.0 * get_single_cost(media)) + tube_cost,
            name="Add 5mL Media to 15mL Tube"
        ))
        
        # 4. Transfer vial contents to 15mL tube
        steps.append(self.op_aspirate(
            vessel_id="cryovial",
            volume_ml=1.0,
            material_cost_usd=get_single_cost("pipette_2ml"),
            name="Aspirate Cells from Cryovial"
        ))
        steps.append(self.op_dispense(
            vessel_id=tube_id,
            volume_ml=1.0,
            liquid_name="cells",
            material_cost_usd=0.0, # Reuse pipette
            name="Dispense Cells into 15mL Tube"
        ))
        
        # 5. Wash vial with 500uL media and transfer
        steps.append(self.op_dispense(
            vessel_id="cryovial",
            volume_ml=0.5,
            liquid_name=media,
            material_cost_usd=get_single_cost("pipette_2ml") + (0.5 * get_single_cost(media)),
            name="Add 0.5mL Wash Media to Cryovial"
        ))
        steps.append(self.op_aspirate(
            vessel_id="cryovial",
            volume_ml=0.5,
            material_cost_usd=0.0, # Reuse
            name="Aspirate Wash from Cryovial"
        ))
        steps.append(self.op_dispense(
            vessel_id=tube_id,
            volume_ml=0.5,
            liquid_name="wash",
            material_cost_usd=0.0,
            name="Dispense Wash into 15mL Tube"
        ))
        
        # 6. Centrifuge
        steps.append(self.op_centrifuge(
            vessel_id=tube_id,
            duration_min=5.0,
            speed_rpm=1200,
            temp_c=25.0,
            instrument_cost_usd=0.5
        ))
        
        # 7. Aspirate supernatant
        steps.append(self.op_aspirate(
            vessel_id=tube_id,
            volume_ml=6.4, # Leave ~100uL pellet
            material_cost_usd=get_single_cost("pipette_10ml"),
            name="Aspirate Supernatant"
        ))
        
        # 8. Resuspend in 1.1mL media
        steps.append(self.op_dispense(
            vessel_id=tube_id,
            volume_ml=1.1,
            liquid_name=media,
            material_cost_usd=get_single_cost("pipette_2ml") + (1.1 * get_single_cost(media)),
            name="Resuspend Pellet in 1.1mL Media"
        ))
        
        # 9. Take 100uL for count
        steps.append(self.op_aspirate(
            vessel_id=tube_id,
            volume_ml=0.1,
            material_cost_usd=get_single_cost("tip_200ul_lr"),
            name="Sample 100uL for Count"
        ))
        
        # 10. Add 15mL growth media to Flask

        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=15.0,
            liquid_name=media,
            material_cost_usd=(2 * get_single_cost("pipette_10ml")) + (15.0 * get_single_cost(media)), # Use 2x 10mL pipettes or equivalent
            name=f"Add 15mL Growth Media to {vessel_id}"
        ))
        
        # 12. Transfer 1e6 cells (remaining 1mL) to Flask
        steps.append(self.op_aspirate(
            vessel_id=tube_id,
            volume_ml=1.0,
            material_cost_usd=get_single_cost("pipette_2ml"),
            name="Aspirate Cells from 15mL Tube"
        ))
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=1.0,
            liquid_name="cells",
            material_cost_usd=0.0,
            name=f"Dispense Cells into {vessel_id}"
        ))
        
        # 13. Incubate overnight
        steps.append(self.op_incubate(
            vessel_id=vessel_id,
            duration_min=1440.0,  # 24 hours
            temp_c=37.0,
            co2_pct=5.0,
            material_cost_usd=0.0,
            instrument_cost_usd=2.0
        ))
        
        
        # Calculate total costs
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Add cryovial cost
        cryovial_cost = get_single_cost("cryovial_1_8ml")
        
        # Calculate total media volume used in thaw process
        # 5mL in tube + 0.5mL wash + 1.1mL resuspension + 15mL in flask = 21.6mL
        media_vol_ml = 5.0 + 0.5 + 1.1 + 15.0
        
        # Add media cost (rough estimate: $0.50/mL for mTeSR, $0.05/mL for DMEM)
        media_cost_per_ml = 0.50 if media == "mtesr_plus_kit" else 0.05
        media_cost = media_vol_ml * media_cost_per_ml
        
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
            if CELL_LINE_DB_AVAILABLE:
                profile = get_cell_line_profile(cell_line)
                if profile and profile.media:
                    media = profile.media
            
            # Fallback if DB failed or no media in profile
            if media is None:
                if cell_line.lower() in ["ipsc", "hesc"]:
                    media = "mtesr_plus_kit"
                else:
                    media = "dmem_10fbs"
        elif media is None:
            media = "dmem_10fbs"  # Default
        
        media_vol = 15.0  # Standard for T75
        
        # Calculate media cost per mL
        media_cost_per_ml = 0.50 if media == "mtesr_plus_kit" else 0.05
        
        # 1. Aspirate old media
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=media_vol,
            material_cost_usd=self.inv.get_price("pipette_10ml") * 2  # Need 2x 10mL pipettes for 15mL
        ))
        
        # 2. Add fresh media
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=media_vol,
            liquid_name=media,
            material_cost_usd=(self.inv.get_price("pipette_10ml") * 2) + (media_vol * media_cost_per_ml)
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
            material_cost_usd=total_mat + supplement_cost,
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
        
        # Vessel-specific coating volumes (working solution)
        # T75 = 75 cm², protocol calls for ~1 mL per 6 cm² = 12.5 mL
        coating_vol = 12.5  # mL for T75
        
        for agent in agents:
            # Vitronectin requires dilution in PBS
            if agent == "vitronectin":
                # Stock: 0.5 mg/mL (5mg in 10mL)
                # Working: 10 µg/mL (0.01 mg/mL)
                # Dilution: 50x
                stock_vol_ml = coating_vol / 50.0  # 0.25 mL
                pbs_vol_ml = coating_vol - stock_vol_ml  # 12.25 mL
                
                # Costs
                pbs_cost = pbs_vol_ml * self.inv.get_price("dpbs")
                stock_cost = stock_vol_ml * self.inv.get_price("vitronectin")
                
                # 1. Prepare Solution in Tube
                # Add PBS
                steps.append(self.op_dispense(
                    vessel_id="tube_50ml",
                    volume_ml=pbs_vol_ml,
                    liquid_name="pbs",
                    material_cost_usd=self.inv.get_price("pipette_10ml") + pbs_cost,
                    name=f"Dispense {pbs_vol_ml:.2f}mL PBS into Tube"
                ))
                
                # Add Vitronectin
                steps.append(self.op_dispense(
                    vessel_id="tube_50ml",
                    volume_ml=stock_vol_ml,
                    liquid_name=agent,
                    material_cost_usd=self.inv.get_price("pipette_2ml") + stock_cost,
                    name=f"Dispense {stock_vol_ml:.2f}mL {agent} into Tube"
                ))
                
                # Mix (Aspirate/Dispense)
                steps.append(self.op_aspirate(
                    vessel_id="tube_50ml",
                    volume_ml=5.0,
                    material_cost_usd=0.0,
                    name="Mix Solution (Aspirate)"
                ))
                steps.append(self.op_dispense(
                    vessel_id="tube_50ml",
                    volume_ml=5.0,
                    liquid_name="mixture",
                    material_cost_usd=0.0,
                    name="Mix Solution (Dispense)"
                ))
                
                # 2. Transfer to Flask
                steps.append(self.op_aspirate(
                    vessel_id="tube_50ml",
                    volume_ml=coating_vol,
                    material_cost_usd=self.inv.get_price("pipette_10ml"),
                    name=f"Aspirate {coating_vol}mL Coating Solution"
                ))
                steps.append(self.op_dispense(
                    vessel_id=vessel_id,
                    volume_ml=coating_vol,
                    liquid_name="coating_solution",
                    material_cost_usd=0.0, # Pipette cost accounted for in aspirate
                    name=f"Dispense {coating_vol}mL Coating Solution into Flask"
                ))
                
            else:
                # Other coating agents (Matrigel, Laminin, etc.) - use as-is
                steps.append(self.op_dispense(
                    vessel_id=vessel_id,
                    volume_ml=coating_vol,
                    liquid_name=agent,
                    material_cost_usd=self.inv.get_price("pipette_10ml")
                ))
        
        # Incubation time depends on coating agent
        # Vitronectin: 24 hours (1440 min) at RT or 37°C
        # Matrigel/Laminin: 1 hour (60 min) at 37°C
        incubation_time = 1440.0 if "vitronectin" in agents else 60.0
        
        steps.append(self.op_incubate(
            vessel_id=vessel_id,
            duration_min=incubation_time,
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=1.0
        ))
        
        # Aspirate coating solution is now handled in op_thaw or manually before seeding
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Calculate coating agent cost based on actual usage
        coating_cost = 0.0
        for agent in agents:
            if agent == "vitronectin":
                # 0.25 mL of stock at $90/mL
                # This cost is now included in the op_dispense step for vitronectin
                pass 
            elif agent == "matrigel":
                # Matrigel is expensive, ~$50 per coating
                coating_cost += 50.0
            elif agent == "laminin_521":
                # Laminin 521 is also expensive
                coating_cost += 30.0
            else:
                # Other coatings
                coating_cost += 5.0
        
        return UnitOp(
            uo_id=f"Coat_{vessel_id}_{'_'.join(agents)}",
            name=f"Coat {vessel_id} with {', '.join(agents)}",
            layer="preparation",
            category="coating",
            time_score=int(incubation_time + 15),  # Incubation + handling
            cost_score=3,
            automation_fit=3,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet + Incubator",
            material_cost_usd=total_mat,
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

    def op_harvest(self, vessel_id: str, dissociation_method: str = "accutase", cell_line: str = None):
        """Harvest cells for freezing or analysis."""
        from .base import UnitOp
        
        steps = []
        
        # Determine media type for quench
        media = "mtesr_plus_kit" if cell_line and cell_line.lower() in ["ipsc", "hesc"] else "dmem_10fbs"
        
        # 1. Aspirate media (15mL for T75)
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=15.0,
            material_cost_usd=self.inv.get_price("pipette_10ml") * 2,
            name="Aspirate 15.0mL from T-75 Flask"
        ))
        
        # 2. Wash with PBS
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=5.0,
            liquid_name="pbs",
            material_cost_usd=self.inv.get_price("pipette_10ml"),
            name="Dispense 5.0mL pbs into T-75 Flask"
        ))
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=5.0,
            material_cost_usd=self.inv.get_price("pipette_10ml"),
            name="Aspirate 5.0mL from T-75 Flask"
        ))
        
        # 3. Add dissociation reagent
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=2.0,
            liquid_name=dissociation_method,
            material_cost_usd=0.0,
            name=f"Dispense 2.0mL {dissociation_method} into T-75 Flask"
        ))
        
        # 4. Incubate
        steps.append(self.op_incubate(
            vessel_id=vessel_id,
            duration_min=10.0,
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=0.5,
            name="Incubate 10.0 min @ 37.0C"
        ))
        
        # 5. Quench with 5mL media
        media_cost_per_ml = 0.50 if media == "mtesr_plus_kit" else 0.05
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=5.0,
            liquid_name=media,
            material_cost_usd=self.inv.get_price("pipette_10ml") + (5.0 * media_cost_per_ml),
            name=f"Quench with 5.0mL {media}"
        ))
        
        # 6. Collect cells into 15mL tube (7mL total)
        tube_id = "tube_15ml"
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=7.0,
            material_cost_usd=self.inv.get_price("pipette_10ml"),
            name="Aspirate 7.0mL from T-75 Flask"
        ))
        steps.append(self.op_dispense(
            vessel_id=tube_id,
            volume_ml=7.0,
            liquid_name="cells",
            material_cost_usd=self.inv.get_price("tube_15ml_conical"),
            name="Dispense into 15mL tube"
        ))
        
        # 7. Count cells (sample 100uL)
        steps.append(self.op_aspirate(
            vessel_id=tube_id,
            volume_ml=0.1,
            material_cost_usd=self.inv.get_price("tip_200ul_lr"),
            name="Sample 100uL for count"
        ))
        
        # 8. Centrifuge
        steps.append(self.op_centrifuge(
            vessel_id=tube_id,
            duration_min=5.0,
            speed_rpm=1200,
            temp_c=25.0,
            instrument_cost_usd=0.5,
            name="Centrifuge 5min @ 1200rpm"
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        dissociation_cost = 2.0 * (2.0 if dissociation_method == "accutase" else 0.5)
        pbs_cost = 5.0 * 0.01  # PBS is cheap
        
        return UnitOp(
            uo_id=f"Harvest_{vessel_id}",
            name=f"Harvest cells from {vessel_id} ({dissociation_method})",
            layer="culture",
            category="harvest",
            time_score=30,
            cost_score=2,
            automation_fit=3,
            failure_risk=2,
            staff_attention=2,
            instrument="Biosafety Cabinet + Centrifuge",
            material_cost_usd=total_mat + dissociation_cost + pbs_cost,
            instrument_cost_usd=total_inst + 3.0,
            sub_steps=steps
        )

    def op_freeze(self, num_vials: int = 10, freezing_media: str = "cryostor_cs10", cell_line: str = None):
        """Freeze cells into cryovials."""
        from .base import UnitOp
        
        steps = []
        
        # Use 0.35mL per vial for iPSC/hESC, 1.0mL for others
        volume_per_vial = 0.35 if cell_line and cell_line.lower() in ["ipsc", "hesc"] else 1.0
        vial_type = "micronic_tube" if volume_per_vial == 0.35 else "cryovial_1_8ml"
        
        # 1. Aspirate supernatant (after centrifuge from harvest)
        tube_id = "tube_15ml"
        steps.append(self.op_aspirate(
            vessel_id=tube_id,
            volume_ml=6.9,  # Leave pellet with ~100uL
            material_cost_usd=self.inv.get_price("pipette_10ml"),
            name="Aspirate supernatant"
        ))
        
        # 2. Resuspend pellet in CryoStor to achieve target concentration
        # Target: 1e6 cells per 0.35mL (or per 1.0mL for other cell types)
        # Total volume needed = num_vials * volume_per_vial
        total_volume_ml = num_vials * volume_per_vial
        
        cryostor_cost_per_ml = 5.0  # CryoStor CS10 is expensive
        steps.append(self.op_dispense(
            vessel_id=tube_id,
            volume_ml=total_volume_ml,
            liquid_name=freezing_media,
            material_cost_usd=self.inv.get_price("pipette_2ml") + (total_volume_ml * cryostor_cost_per_ml),
            name=f"Resuspend in {total_volume_ml:.2f}mL {freezing_media}"
        ))
        
        # 3. Mix by pipetting
        steps.append(self.op_aspirate(
            vessel_id=tube_id,
            volume_ml=min(1.0, total_volume_ml),
            material_cost_usd=0.0,  # Reuse pipette
            name="Mix by pipetting"
        ))
        steps.append(self.op_dispense(
            vessel_id=tube_id,
            volume_ml=min(1.0, total_volume_ml),
            liquid_name="cell_suspension",
            material_cost_usd=0.0,
            name="Mix by pipetting"
        ))
        
        # 4. Aliquot into vials
        for i in range(num_vials):
            vial_id = f"vial_{i+1}"
            steps.append(self.op_aspirate(
                vessel_id=tube_id,
                volume_ml=volume_per_vial,
                material_cost_usd=self.inv.get_price("pipette_2ml") if i == 0 else 0.0,  # First vial pays for pipette
                name=f"Aspirate {volume_per_vial}mL for vial {i+1}"
            ))
            steps.append(self.op_dispense(
                vessel_id=vial_id,
                volume_ml=volume_per_vial,
                liquid_name="cell_suspension",
                material_cost_usd=self.inv.get_price(vial_type),  # Each vial has a cost
                name=f"Dispense into vial {i+1}"
            ))
        
        # 5. Controlled rate freezing
        steps.append(self.op_incubate(
            vessel_id="controlled_rate_freezer",
            duration_min=120.0,  # 2 hours
            temp_c=-80.0,
            material_cost_usd=0.0,
            instrument_cost_usd=10.0,  # Controlled rate freezer is expensive to run
            name="Controlled rate freezing to -80C"
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        return UnitOp(
            uo_id=f"Freeze_{num_vials}vials",
            name=f"Freeze {num_vials} vials ({freezing_media}, {volume_per_vial}mL each)",
            layer="banking",
            category="culture",
            time_score=60,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet + Controlled Rate Freezer",
            material_cost_usd=total_mat,
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