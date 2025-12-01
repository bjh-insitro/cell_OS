"""
QC and testing operations.
"""
from typing import List, Optional
from cell_os.unit_ops.base import UnitOp
from .base_operation import BaseOperation

class QCOps(BaseOperation):
    """Operations for quality control and testing."""
    
    def mycoplasma_test(self, sample_id: str, method: str = "pcr"):
        """Test for mycoplasma contamination."""
        steps = []
        
        # 1. Collect sample
        steps.append(self.lh.op_aspirate(
            vessel_id=sample_id,
            volume_ml=1.0,
            material_cost_usd=self.get_price("tube_15ml_conical")
        ))
        
        # 2. Process based on method
        if method == "pcr":
            # DNA extraction
            steps.append(self.lh.op_incubate(
                vessel_id="tube_15ml",
                duration_min=30.0,
                temp_c=95.0,
                material_cost_usd=5.0,  # DNA extraction kit
                instrument_cost_usd=1.0
            ))
            
            # PCR
            steps.append(self.lh.op_incubate(
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
            steps.append(self.lh.op_incubate(
                vessel_id="culture_plate",
                duration_min=10080.0,  # 7 days
                temp_c=37.0,
                material_cost_usd=15.0,
                instrument_cost_usd=10.0
            ))
            
            test_duration = 10080  # 7 days
            test_cost = 30.0
        
        else:  # luminescence or other rapid methods
            steps.append(self.lh.op_incubate(
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

    def sterility_test(self, sample_id: str, duration_days: int = 7):
        """Test for bacterial/fungal contamination."""
        steps = []
        
        # 1. Collect sample
        steps.append(self.lh.op_aspirate(
            vessel_id=sample_id,
            volume_ml=5.0,
            material_cost_usd=self.get_price("tube_15ml_conical")
        ))
        
        # 2. Inoculate culture media
        steps.append(self.lh.op_dispense(
            vessel_id="culture_bottle",
            volume_ml=5.0,
            liquid_name="tryptic_soy_broth",
            material_cost_usd=5.0
        ))
        
        # 3. Incubate
        steps.append(self.lh.op_incubate(
            vessel_id="culture_bottle",
            duration_min=duration_days * 1440.0,  # Convert days to minutes
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=2.0 * duration_days
        ))
        
        # 4. Visual inspection + optional plating
        steps.append(self.lh.op_incubate(
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

    def karyotype(self, sample_id: str, method: str = "g_banding"):
        """Karyotype analysis for chromosomal abnormalities."""
        steps = []
        
        # 1. Harvest cells in metaphase
        # Add colcemid to arrest in metaphase
        steps.append(self.lh.op_dispense(
            vessel_id=sample_id,
            volume_ml=0.1,
            liquid_name="colcemid",
            material_cost_usd=5.0
        ))
        
        steps.append(self.lh.op_incubate(
            vessel_id=sample_id,
            duration_min=120.0,  # 2 hours
            temp_c=37.0,
            material_cost_usd=0.0,
            instrument_cost_usd=1.0
        ))
        
        # 2. Harvest and fix
        steps.append(self.lh.op_aspirate(
            vessel_id=sample_id,
            volume_ml=5.0,
            material_cost_usd=self.get_price("tube_15ml_conical")
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
        
        steps.append(self.lh.op_incubate(
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
