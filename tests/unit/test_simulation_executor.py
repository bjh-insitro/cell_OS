"""
Tests for SimulationExecutor
"""

import pytest
import tempfile
import os
from cell_os.simulation.executor import SimulationExecutor

class MockOp:
    def __init__(self, operation, parameters):
        self.uo_id = operation
        self.name = operation
        self.parameters = parameters

class TestSimulationExecutor:
    
    def setup_method(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.executor = SimulationExecutor(
            db_path=self.temp_db.name,
            collect_data=True,
            simulation_speed=0.0
        )
        
    def teardown_method(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
            
    def test_basic_workflow_execution(self):
        """Test that workflows execute and collect data."""
        workflow = [
            MockOp(
                operation="seed",
                parameters={
                    "vessel_id": "T75_1",
                    "cell_line": "HEK293T",
                    "initial_count": 1e6
                }
            ),
            MockOp(
                operation="viability_assay",
                parameters={"vessel_id": "T75_1"}
            )
        ]
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="test_basic",
            cell_line="HEK293T",
            vessel_id="T75_1",
            operation_type="test",
            unit_ops=workflow
        )
        result = self.executor.execute(execution.execution_id)
        
        if result.status.value == "failed":
            print(f"Execution failed: {result.error_message}")
            for step in result.steps:
                if step.status.value == "failed":
                    print(f"Step {step.name} failed: {step.error_message}")
        
        assert result.status.value == "completed"
        assert len(self.executor.collected_data) == 2
        assert self.executor.collected_data[0]["operation"] == "seed"
        assert self.executor.collected_data[1]["operation"] == "viability_assay"
        
    def test_passage_workflow(self):
        """Test passage workflow with data collection."""
        workflow = [
            MockOp(
                operation="seed",
                parameters={
                    "vessel_id": "T75_1",
                    "cell_line": "HEK293T",
                    "initial_count": 4e6
                }
            ),
            MockOp(
                operation="passage",
                parameters={
                    "source_vessel": "T75_1",
                    "target_vessel": "T75_2",
                    "split_ratio": 4.0
                }
            )
        ]
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="test_passage",
            cell_line="HEK293T",
            vessel_id="T75_1",
            operation_type="passage",
            unit_ops=workflow
        )
        result = self.executor.execute(execution.execution_id)
        
        assert result.status.value == "completed"
        
        # Check passage data
        passage_data = [d for d in self.executor.collected_data if d["operation"] == "passage"]
        assert len(passage_data) == 1
        assert passage_data[0]["split_ratio"] == 4.0
        assert passage_data[0]["passage_number"] == 1
        
    def test_dose_response_data_collection(self):
        """Test dose-response experiment data collection."""
        doses = [0.01, 0.1, 1.0]
        workflow = []
        
        # Seed wells
        for i, dose in enumerate(doses):
            workflow.append(
                MockOp(
                    operation="seed",
                    parameters={
                        "vessel_id": f"well_{i}",
                        "cell_line": "HEK293T",
                        "initial_count": 1e5
                    }
                )
            )
        
        # Treat
        for i, dose in enumerate(doses):
            workflow.append(
                MockOp(
                    operation="treat",
                    parameters={
                        "vessel_id": f"well_{i}",
                        "compound": "staurosporine",
                        "dose_uM": dose
                    }
                )
            )
        
        # Measure
        for i in range(len(doses)):
            workflow.append(
                MockOp(
                    operation="viability_assay",
                    parameters={"vessel_id": f"well_{i}"}
                )
            )
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="test_dose_response",
            cell_line="HEK293T",
            vessel_id="plate_1",
            operation_type="screen",
            unit_ops=workflow
        )
        result = self.executor.execute(execution.execution_id)
        
        assert result.status.value == "completed"
        
        # Check data
        treat_data = [d for d in self.executor.collected_data if d["operation"] == "treat"]
        viab_data = [d for d in self.executor.collected_data if d["operation"] == "viability_assay"]
        
        assert len(treat_data) == 3
        assert len(viab_data) == 3
        
        # Viability should decrease with dose
        viabilities = [d["viability"] for d in viab_data]
        # Note: Since simulation speed is 0.0 (instant), biological effects might not have time to develop
        # unless treat_with_compound applies immediate effect.
        # BiologicalVirtualMachine.treat_with_compound applies effect immediately.
        assert viabilities[0] > viabilities[-1]  # Lower dose = higher viability
        
    def test_data_export_json(self):
        """Test JSON data export."""
        workflow = [
            MockOp(
                operation="seed",
                parameters={"vessel_id": "T75_1", "cell_line": "HEK293T", "initial_count": 1e6}
            )
        ]
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="test_export",
            cell_line="HEK293T",
            vessel_id="T75_1",
            operation_type="test",
            unit_ops=workflow
        )
        self.executor.execute(execution.execution_id)
        
        # Export
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            export_path = f.name
            
        try:
            self.executor.export_data(export_path, format='json')
            assert os.path.exists(export_path)
            
            # Verify content
            import json
            with open(export_path) as f:
                data = json.load(f)
            assert len(data) == 1
            assert data[0]["operation"] == "seed"
        finally:
            if os.path.exists(export_path):
                os.unlink(export_path)
                
    def test_vessel_state_tracking(self):
        """Test that vessel states are tracked correctly."""
        workflow = [
            MockOp(
                operation="seed",
                parameters={"vessel_id": "T75_1", "cell_line": "HEK293T", "initial_count": 1e6}
            ),
            MockOp(
                operation="seed",
                parameters={"vessel_id": "T75_2", "cell_line": "HeLa", "initial_count": 2e6}
            )
        ]
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="test_tracking",
            cell_line="HEK293T",
            vessel_id="T75_1",
            operation_type="test",
            unit_ops=workflow
        )
        self.executor.execute(execution.execution_id)
        
        states = self.executor.get_vessel_states()
        
        assert len(states) == 2
        assert "T75_1" in states
        assert "T75_2" in states
        assert states["T75_1"]["cell_line"] == "HEK293T"
        assert states["T75_2"]["cell_line"] == "HeLa"
        
    def test_reset_simulation(self):
        """Test simulation reset."""
        workflow = [
            MockOp(
                operation="seed",
                parameters={"vessel_id": "T75_1", "cell_line": "HEK293T", "initial_count": 1e6}
            )
        ]
        
        execution = self.executor.create_execution_from_protocol(
            protocol_name="test_reset",
            cell_line="HEK293T",
            vessel_id="T75_1",
            operation_type="test",
            unit_ops=workflow
        )
        self.executor.execute(execution.execution_id)
        
        assert len(self.executor.collected_data) > 0
        assert len(self.executor.get_vessel_states()) > 0
        
        # Reset
        self.executor.reset_simulation()
        
        assert len(self.executor.collected_data) == 0
        assert len(self.executor.get_vessel_states()) == 0
