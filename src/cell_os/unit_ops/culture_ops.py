"""
Culture Operations Mixin.
Contains core cell culture operations: Thaw, Passage, Feed, Harvest, Seed, Coat, Freeze.
"""

from typing import List, Optional

# Import cell line database for automatic method selection
try:
    from cell_os.cell_line_database import get_cell_line_profile
    CELL_LINE_DB_AVAILABLE = True
except ImportError:
    CELL_LINE_DB_AVAILABLE = False


class CultureOpsMixin:
    """Mixin for cell culture operations."""
    
    # Note: This mixin assumes self.inv (Inventory) and self.op_dispense/aspirate/incubate/centrifuge exist.
    
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
            
        
        # Only aspirate coating if we actually just coated in this operation
        if coating_needed:
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
            material_cost_usd=get_single_cost("pipette_5ml") + (5.0 * get_single_cost(media)),
            name=f"Add 5mL {media} to 15mL Tube"
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
            name=f"Add 0.5mL {media} to Cryovial"
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
            name=f"Resuspend Pellet in 1.1mL {media}"
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
            name=f"Add 15mL {media} to {vessel_id}"
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
            material_cost_usd=total_mat + cryovial_cost,
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

    def op_feed(self, vessel_id: str, media: str = None, cell_line: str = None, supplements: List[str] = None, name: str = None):
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
        
        # Volume depends on vessel
        media_vol = 15.0
        if "plate_6well" in vessel_id:
            media_vol = 2.0 * 6 # 12mL total
        elif "flask_t75" in vessel_id.lower():
            media_vol = 15.0
            
        # Calculate media cost per mL
        media_cost_per_ml = 0.50 if media == "mtesr_plus_kit" else 0.05
        
        # 1. Aspirate old media
        # Pipette count: 15mL needs 2x 10mL or 1x 25mL. 12mL needs 2x 10mL.
        pipette_cost = self.inv.get_price("pipette_10ml") * (2 if media_vol > 10 else 1)
        
        steps.append(self.op_aspirate(
            vessel_id=vessel_id,
            volume_ml=media_vol,
            material_cost_usd=pipette_cost
        ))
        
        # 2. Add fresh media
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=media_vol,
            liquid_name=media,
            material_cost_usd=pipette_cost + (media_vol * media_cost_per_ml)
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
            name=name if name else f"Feed {vessel_id} with {media}",
            layer="culture",
            category="culture",
            time_score=15,
            cost_score=1,
            automation_fit=3,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=total_mat + supplement_cost,
            instrument_cost_usd=total_inst + 2.0,
            sub_steps=steps
        )

    def op_coat(self, vessel_id: str, agents: List[str] = None, num_vessels: int = 1):
        """Coat vessel(s) with ECM proteins."""
        from .base import UnitOp
        
        if agents is None:
            agents = ["matrigel"]
        
        steps = []
        
        # Vessel-specific coating volumes (working solution) PER VESSEL
        if "plate_6well" in vessel_id:
            coating_vol_per_vessel = 6.0 # 1mL per well * 6
        elif "flask_t75" in vessel_id.lower():
            coating_vol_per_vessel = 12.5 # mL for T75
        else:
            coating_vol_per_vessel = 5.0 # Default
        
        # Total volume needed for all vessels
        total_coating_vol = coating_vol_per_vessel * num_vessels
        
        for agent in agents:
            # Vitronectin requires dilution in PBS
            if agent == "vitronectin":
                # Stock: 0.5 mg/mL (5mg in 10mL)
                # Working: 10 µg/mL (0.01 mg/mL)
                # Dilution: 50x
                stock_vol_ml = total_coating_vol / 50.0
                pbs_vol_ml = total_coating_vol - stock_vol_ml
                
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
                
                # 2. Transfer to Vessels
                for i in range(num_vessels):
                    steps.append(self.op_aspirate(
                        vessel_id="tube_50ml",
                        volume_ml=coating_vol_per_vessel,
                        material_cost_usd=self.inv.get_price("pipette_10ml"),
                        name=f"Aspirate {coating_vol_per_vessel:.1f}mL from Tube"
                    ))
                    steps.append(self.op_dispense(
                        vessel_id=vessel_id,
                        volume_ml=coating_vol_per_vessel,
                        liquid_name=agent,
                        material_cost_usd=0.0,
                        name=f"Dispense {coating_vol_per_vessel:.1f}mL into {vessel_id} {i+1}"
                    ))
                
                # 3. Incubate
                steps.append(self.op_incubate(
                    vessel_id=vessel_id,
                    duration_min=60.0,
                    temp_c=37.0,
                    material_cost_usd=0.0,
                    instrument_cost_usd=1.0,
                    name=f"Incubate {num_vessels} {vessel_id}(s) for 1h @ 37C"
                ))
                
                tube_cost = self.inv.get_price("tube_50ml_conical")
                
            else:
                # Other agents (matrigel, etc.) - simplified
                agent_cost = total_coating_vol * 2.0  # Estimate
                steps.append(self.op_dispense(
                    vessel_id=vessel_id,
                    volume_ml=total_coating_vol,
                    liquid_name=agent,
                    material_cost_usd=self.inv.get_price("pipette_10ml") + agent_cost,
                    name=f"Coat {num_vessels} {vessel_id}(s) with {agent}"
                ))
                steps.append(self.op_incubate(
                    vessel_id=vessel_id,
                    duration_min=60.0,
                    temp_c=37.0,
                    material_cost_usd=0.0,
                    instrument_cost_usd=1.0,
                    name=f"Incubate {num_vessels} {vessel_id}(s) for 1h @ 37C"
                ))
                tube_cost = 0.0
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        vessel_desc = f"{num_vessels} {vessel_id}(s)" if num_vessels > 1 else vessel_id
        
        return UnitOp(
            uo_id=f"Coat_{vessel_id}",
            name=f"Coat {vessel_desc} with {', '.join(agents)}",
            layer="culture",
            category="coating",
            time_score=90,
            cost_score=2,
            automation_fit=2,
            failure_risk=1,
            staff_attention=2,
            instrument="Biosafety Cabinet + Incubator",
            material_cost_usd=total_mat + tube_cost,
            instrument_cost_usd=total_inst,
            sub_steps=steps
        )

    def op_seed_plate(self, vessel_id: str, num_wells: int, volume_per_well_ml: float = 2.0, cell_line: str = None, name: str = None):
        """Seed cells into plate wells with detailed sub-steps."""
        from .base import UnitOp
        
        steps = []
        
        # Helper to get single item cost
        def get_single_cost(item_id: str):
            return self.inv.get_price(item_id)
        
        # Determine media
        media = "dmem_10fbs"
        if cell_line:
            if CELL_LINE_DB_AVAILABLE:
                profile = get_cell_line_profile(cell_line)
                if profile and profile.media:
                    media = profile.media
            elif cell_line.lower() in ["ipsc", "hesc"]:
                media = "mtesr_plus_kit"
        
        media_cost_per_ml = 0.50 if media == "mtesr_plus_kit" else 0.05
        
        # 1. Resuspend pellet to achieve target cell density
        total_volume_needed = num_wells * volume_per_well_ml
        steps.append(self.op_dispense(
            vessel_id="tube_15ml",
            volume_ml=total_volume_needed,
            liquid_name=media,
            material_cost_usd=get_single_cost("pipette_10ml") + (total_volume_needed * media_cost_per_ml),
            name=f"Resuspend pellet in {total_volume_needed:.1f}mL {media}"
        ))
        
        # 2. Mix/pipette to ensure uniform suspension
        steps.append(self.op_aspirate(
            vessel_id="tube_15ml",
            volume_ml=total_volume_needed,
            material_cost_usd=get_single_cost("pipette_10ml"),
            name="Mix cell suspension"
        ))
        steps.append(self.op_dispense(
            vessel_id="tube_15ml",
            volume_ml=total_volume_needed,
            liquid_name="cell_suspension",
            material_cost_usd=0.0,
            name="Dispense back to mix"
        ))
        
        # 3. Seed wells
        for i in range(num_wells):
            steps.append(self.op_dispense(
                vessel_id=vessel_id,
                volume_ml=volume_per_well_ml,
                liquid_name="cell_suspension",
                material_cost_usd=get_single_cost("pipette_2ml") if volume_per_well_ml <= 5 else get_single_cost("pipette_10ml"),
                name=f"Seed well {i+1} ({volume_per_well_ml}mL)"
            ))
        
        # 4. Incubate (overnight)
        steps.append(self.op_incubate(
            vessel_id=vessel_id,
            duration_min=1440,  # 24 hours
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=1.0,
            name="Incubate overnight"
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Add plate cost
        plate_cost = get_single_cost("plate_6well") if "6well" in vessel_id else 0.0
        
        return UnitOp(
            uo_id=f"SeedPlate_{vessel_id}",
            name=name if name else f"Seed {num_wells} wells in {vessel_id}",
            layer="culture",
            category="seeding",
            time_score=15 + (num_wells * 2),  # Base time + per-well time
            cost_score=2,
            automation_fit=3,
            failure_risk=1,
            staff_attention=2,
            instrument="Biosafety Cabinet + Incubator",
            material_cost_usd=total_mat + plate_cost,
            instrument_cost_usd=total_inst,
            sub_steps=steps
        )

    def op_seed(self, vessel_id: str, num_cells: int, cell_line: str = None, name: str = None):
        """Seed cells into a vessel (generic/flask)."""
        from .base import UnitOp
        
        steps = []
        
        # Helper to get single item cost
        def get_single_cost(item_id: str):
            return self.inv.get_price(item_id)
        
        # Determine media
        media = "dmem_10fbs"
        if cell_line:
            if CELL_LINE_DB_AVAILABLE:
                profile = get_cell_line_profile(cell_line)
                if profile and profile.media:
                    media = profile.media
            elif cell_line.lower() in ["ipsc", "hesc"]:
                media = "mtesr_plus_kit"
        
        media_cost_per_ml = 0.50 if media == "mtesr_plus_kit" else 0.05
        
        # Determine volume based on vessel type
        volume_ml = 15.0  # Default for T75
        if "t25" in vessel_id.lower():
            volume_ml = 5.0
        elif "t175" in vessel_id.lower():
            volume_ml = 30.0
            
        # 1. Dispense media
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=volume_ml,
            liquid_name=media,
            material_cost_usd=get_single_cost("pipette_25ml") + (volume_ml * media_cost_per_ml),
            name=f"Fill {vessel_id} with {volume_ml}mL {media}"
        ))
        
        # 2. Add cells (assume concentrated suspension)
        steps.append(self.op_dispense(
            vessel_id=vessel_id,
            volume_ml=1.0,
            liquid_name="cell_suspension",
            material_cost_usd=get_single_cost("pipette_5ml"),
            name=f"Seed {num_cells:,} cells"
        ))
        
        # 3. Incubate
        steps.append(self.op_incubate(
            vessel_id=vessel_id,
            duration_min=1440,  # 24 hours
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=1.0,
            name="Incubate overnight"
        ))
        
        total_mat = sum(s.material_cost_usd for s in steps)
        total_inst = sum(s.instrument_cost_usd for s in steps)
        
        # Add vessel cost
        vessel_cost = 0.0
        if "t75" in vessel_id.lower():
            vessel_cost = get_single_cost("flask_T75")
        
        return UnitOp(
            uo_id=f"Seed_{vessel_id}",
            name=name if name else f"Seed {num_cells} cells in {vessel_id}",
            layer="culture",
            category="seeding",
            time_score=20,
            cost_score=2,
            automation_fit=3,
            failure_risk=1,
            staff_attention=2,
            instrument="Biosafety Cabinet + Incubator",
            material_cost_usd=total_mat + vessel_cost,
            instrument_cost_usd=total_inst,
            sub_steps=steps
        )
    
    def op_harvest(self, vessel_id: str, dissociation_method: str = None, cell_line: str = None, name: str = None):
        """Harvest cells for freezing or analysis."""
        from .base import UnitOp
        
        steps = []
        
        # Auto-detect dissociation method if not provided
        if dissociation_method is None:
            dissociation_method = "trypsin"  # Default
            if cell_line:
                if CELL_LINE_DB_AVAILABLE:
                    profile = get_cell_line_profile(cell_line)
                    if profile and profile.dissociation_method:
                        dissociation_method = profile.dissociation_method
                elif cell_line.lower() in ["ipsc", "hesc"]:
                    dissociation_method = "accutase"
        
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
            name=name if name else f"Harvest cells from {vessel_id} ({dissociation_method})",
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
