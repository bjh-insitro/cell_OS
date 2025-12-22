"""
Analysis and computational operations.
"""

from .base import UnitOp, VesselLibrary

from cell_os.inventory import BOMItem

class AnalysisOps:
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.inv = pricing_inv

    def op_count(self, vessel_id: str, method: str = "manual", material_cost_usd: float = None) -> UnitOp:
        items = []
        
        # 1. Slide/Chamber
        if method == "nc202":
            items.append(BOMItem(resource_id="cell_counter_slides", quantity=1))
            items.append(BOMItem(resource_id="nc202_usage", quantity=1))
        else:
            # Manual or other
            items.append(BOMItem(resource_id="cell_counter_slides", quantity=1))
            
        # Calculate costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
        else:
            # Fallback if mixin not available (shouldn't happen with correct inheritance)
            mat_cost = 3.0
            inst_cost = 0.5

        # Override if provided
        if material_cost_usd is not None:
            mat_cost = material_cost_usd
        
        return UnitOp(
            uo_id=f"Count_{vessel_id}",
            name=f"Count Cells ({vessel_id}) - {method}",
            layer="atomic",
            category="analysis",
            time_score=5,
            cost_score=0,
            automation_fit=1,
            failure_risk=0,
            staff_attention=1,
            instrument="Cell Counter",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[],
            items=items
        )

    def op_compute_analysis(self, analysis_type: str, num_samples: int) -> UnitOp:
        items = []
        
        # Cloud compute usage
        items.append(BOMItem(
            resource_id="cloud_compute_analysis",
            quantity=num_samples
        ))
        
        # Calculate costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
        else:
            mat_cost = 0.0
            inst_cost = num_samples * 0.01
        
        return UnitOp(
            uo_id=f"Compute_{analysis_type}",
            name=f"Compute: {analysis_type} ({num_samples} samples)",
            layer="analysis",
            category="compute",
            time_score=10,  # Async
            cost_score=1,
            automation_fit=1,
            failure_risk=0,
            staff_attention=0,
            instrument="Cloud Compute",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[],
            items=items
        )

    def op_ngs_verification(self, vessel_id: str) -> UnitOp:
        items = []
        
        # 1. Library Prep Kit
        items.append(BOMItem(resource_id="ngs_library_prep_kit", quantity=1))
        
        # 2. Sequencer Usage
        items.append(BOMItem(resource_id="sequencer_usage", quantity=1))
        
        # Calculate costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
        else:
            mat_cost = 50.0
            inst_cost = 100.0
            
        return UnitOp(
            uo_id=f"NGS_Verify_{vessel_id}",
            name=f"NGS Verification ({vessel_id})",
            layer="qc",
            category="sequencing",
            time_score=1440,  # 24 hours
            cost_score=3,
            automation_fit=0,
            failure_risk=1,
            staff_attention=2,
            instrument="Sequencer",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[],
            items=items
        )

    def op_golden_gate_assembly(self, vessel_id: str, num_reactions: int = 1) -> UnitOp:
        return UnitOp(
            uo_id=f"GoldenGate_{num_reactions}rxn",
            name=f"Golden Gate Assembly ({num_reactions} rxn)",
            layer="cloning",
            category="molecular_biology",
            time_score=120,
            cost_score=2,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Thermocycler",
            material_cost_usd=5.0 * num_reactions,
            instrument_cost_usd=1.0,
            sub_steps=[]
        )

    def op_transformation(self, vessel_id: str, num_reactions: int = 1) -> UnitOp:
        return UnitOp(
            uo_id=f"Transformation_{num_reactions}rxn",
            name=f"Transformation ({num_reactions} rxn)",
            layer="cloning",
            category="molecular_biology",
            time_score=90,
            cost_score=1,
            automation_fit=0,
            failure_risk=1,
            staff_attention=2,
            instrument="Water Bath",
            material_cost_usd=2.0 * num_reactions,
            instrument_cost_usd=0.5,
            sub_steps=[]
        )

    def op_plasmid_prep(self, vessel_id: str, scale: str = "miniprep") -> UnitOp:
        cost = 5.0 if scale == "miniprep" else 25.0
        
        return UnitOp(
            uo_id=f"PlasmidPrep_{scale}",
            name=f"Plasmid Prep ({scale})",
            layer="cloning",
            category="molecular_biology",
            time_score=60,
            cost_score=1,
            automation_fit=0,
            failure_risk=0,
            staff_attention=2,
            instrument="Centrifuge",
            material_cost_usd=cost,
            instrument_cost_usd=1.0,
            sub_steps=[]
        )

    def op_transfect_hek293t(self, vessel_id: str, vessel_type: str) -> UnitOp:
        return UnitOp(
            uo_id=f"TransfectHEK_{vessel_id}",
            name=f"Transfect HEK293T ({vessel_type})",
            layer="viral_production",
            category="culture",
            time_score=60,
            cost_score=2,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=20.0,
            instrument_cost_usd=5.0,
            sub_steps=[]
        )

    def op_harvest_virus(self, vessel_id: str) -> UnitOp:
        return UnitOp(
            uo_id=f"HarvestVirus_{vessel_id}",
            name=f"Harvest Virus ({vessel_id})",
            layer="viral_production",
            category="culture",
            time_score=30,
            cost_score=1,
            automation_fit=1,
            failure_risk=1,
            staff_attention=1,
            instrument="Biosafety Cabinet",
            material_cost_usd=5.0,
            instrument_cost_usd=2.0,
            sub_steps=[]
        )

    def op_ldh_assay(self, vessel_id: str, num_wells: int = None, name: str = None) -> UnitOp:
        """LDH Cytotoxicity Assay (CyQUANT).

        Measures lactate dehydrogenase release as marker of cytotoxicity.
        Uses verified pricing from ThermoFisher C20301.
        """
        v = self.vessels.get(vessel_id)
        items = []

        # Determine number of wells
        if num_wells is None:
            # Infer from vessel type
            if "384" in vessel_id:
                num_wells = 384
            elif "96" in vessel_id:
                num_wells = 96
            elif "6" in vessel_id:
                num_wells = 6
            else:
                num_wells = 1

        # LDH assay reagent (ThermoFisher C20301: $0.52/test, verified 2024-12)
        items.append(BOMItem(
            resource_id="cyquant_ldh_c20301",
            quantity=num_wells
        ))

        # Plate reader usage (if needed for fluorescence detection)
        # Typically ~5 min for full 384-well plate
        read_time_hours = 0.1  # 6 minutes
        items.append(BOMItem(
            resource_id="plate_reader_usage",
            quantity=read_time_hours
        ))

        # Calculate costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
        else:
            # Fallback costs
            mat_cost = 0.52 * num_wells  # $0.52 per test
            inst_cost = 5.0  # Plate reader time

        return UnitOp(
            uo_id=f"LDH_{vessel_id}",
            name=name if name else f"LDH Cytotoxicity Assay ({num_wells} wells)",
            layer="readout",
            category="assay",
            time_score=30,  # 30 minutes total
            cost_score=2,
            automation_fit=1,
            failure_risk=0,
            staff_attention=1,
            instrument="Plate Reader",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[],
            items=items
        )

    def op_flow_cytometry(self, vessel_id: str, num_samples: int = 96, name: str = None) -> UnitOp:
        items = []
        
        # 1. Sheath fluid (0.5mL per sample)
        items.append(BOMItem(
            resource_id="flow_sheath_fluid",
            quantity=0.5 * num_samples
        ))
        
        # 2. Sample tubes or plate
        if num_samples <= 96:
            items.append(BOMItem(resource_id="plate_96well_u", quantity=1))
        else:
            items.append(BOMItem(resource_id="flow_tube_5ml", quantity=num_samples))
            
        # 3. Instrument usage
        items.append(BOMItem(
            resource_id="flow_cytometer_usage",
            quantity=num_samples
        ))
        
        # Calculate costs
        if hasattr(self, 'calculate_costs_from_items'):
            mat_cost, inst_cost = self.calculate_costs_from_items(items)
        else:
            mat_cost = 0.5 * num_samples
            inst_cost = 20.0
            
        return UnitOp(
            uo_id=f"FlowCytometry_{vessel_id}",
            name=name if name else f"Flow Cytometry ({num_samples} samples)",
            layer="analysis",
            category="readout",
            time_score=60,
            cost_score=2,
            automation_fit=1,
            failure_risk=1,
            staff_attention=2,
            instrument="Flow Cytometer",
            material_cost_usd=mat_cost,
            instrument_cost_usd=inst_cost,
            sub_steps=[],
            items=items
        )
