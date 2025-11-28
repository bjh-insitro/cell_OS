"""
Analysis and computational operations.
"""

from .base import UnitOp, VesselLibrary

class AnalysisOps:
    def __init__(self, vessel_lib: VesselLibrary, pricing_inv):
        self.vessels = vessel_lib
        self.inv = pricing_inv

    def op_count(self, vessel_id: str, method: str = "manual", material_cost_usd: float = None) -> UnitOp:
        inst_cost = 0.5  # Quick count
        
        mat_cost = material_cost_usd if material_cost_usd is not None else 0.5
        
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
            material_cost_usd=mat_cost,  # Slide/chamber
            instrument_cost_usd=inst_cost,
            sub_steps=[]
        )

    def op_compute_analysis(self, analysis_type: str, num_samples: int) -> UnitOp:
        # Cloud compute cost estimate
        cost_per_sample = 0.01
        if analysis_type == "image_processing": cost_per_sample = 0.05
        if analysis_type == "feature_extraction": cost_per_sample = 0.02
        
        total_cost = num_samples * cost_per_sample
        
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
            material_cost_usd=0.0,
            instrument_cost_usd=total_cost,
            sub_steps=[]
        )

    def op_ngs_verification(self, vessel_id: str) -> UnitOp:
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
            material_cost_usd=50.0,
            instrument_cost_usd=100.0,
            sub_steps=[]
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

    def op_flow_cytometry(self, vessel_id: str, num_samples: int = 96) -> UnitOp:
        return UnitOp(
            uo_id=f"FlowCytometry_{vessel_id}",
            name=f"Flow Cytometry ({num_samples} samples)",
            layer="analysis",
            category="readout",
            time_score=60,
            cost_score=2,
            automation_fit=1,
            failure_risk=1,
            staff_attention=2,
            instrument="Flow Cytometer",
            material_cost_usd=0.5 * num_samples, # Sheath fluid, tubes/plates
            instrument_cost_usd=20.0,
            sub_steps=[]
        )
