"""
Tests for Failure Mode Simulation
"""

import pytest
from cell_os.simulation.failure_modes import (
    FailureModeSimulator,
    FailureType,
    ContaminationType,
    FailureEvent
)


class TestFailureModeSimulator:
    
    def setup_method(self):
        self.simulator = FailureModeSimulator(random_seed=42)
    
    def test_contamination_detection(self):
        """Test contamination event generation."""
        # Run multiple times to get at least one contamination
        contaminations = 0
        for _ in range(100):
            event = self.simulator.check_for_contamination(
                vessel_id="T75_1",
                days_in_culture=10.0,
                sterile_technique_quality=0.5  # Poor technique
            )
            if event:
                contaminations += 1
                assert event.failure_type == FailureType.CONTAMINATION
                assert event.affected_vessels == ["T75_1"]
                assert not event.recoverable
        
        # Should have some contaminations with poor technique
        assert contaminations > 0
    
    def test_contamination_types(self):
        """Test different contamination types."""
        # Increase rate for testing
        original_rate = self.simulator.contamination_rate
        self.simulator.contamination_rate = 0.5
        
        contam_types = set()
        for _ in range(100):
            event = self.simulator.check_for_contamination(
                vessel_id="T75_1",
                days_in_culture=1.0,
                sterile_technique_quality=0.5
            )
            if event and "contamination_type" in event.metadata:
                contam_types.add(event.metadata["contamination_type"])
        
        # Should see multiple types
        assert len(contam_types) > 1
        
        self.simulator.contamination_rate = original_rate
    
    def test_equipment_failure(self):
        """Test equipment failure generation."""
        # Increase rate for testing
        original_rate = self.simulator.equipment_failure_rate
        self.simulator.equipment_failure_rate = 0.3
        
        failures = 0
        for _ in range(100):
            event = self.simulator.check_equipment_failure(
                equipment_type="pipette",
                age_years=5.0  # Old equipment
            )
            if event:
                failures += 1
                assert event.failure_type == FailureType.EQUIPMENT_FAILURE
                assert "pipette" in event.description
        
        assert failures > 0
        
        self.simulator.equipment_failure_rate = original_rate
    
    def test_reagent_degradation(self):
        """Test reagent degradation detection."""
        # Increase rate for testing
        original_rate = self.simulator.reagent_degradation_rate
        self.simulator.reagent_degradation_rate = 0.5
        
        degradations = 0
        for _ in range(100):
            event = self.simulator.check_reagent_degradation(
                reagent_name="FBS",
                days_since_opening=90,  # Old reagent
                storage_temp_c=10.0  # Poor storage
            )
            if event:
                degradations += 1
                assert event.failure_type == FailureType.REAGENT_DEGRADATION
                assert not event.recoverable
        
        assert degradations > 0
        
        self.simulator.reagent_degradation_rate = original_rate
    
    def test_human_error(self):
        """Test human error generation."""
        # Increase rate for testing
        original_rate = self.simulator.human_error_rate
        self.simulator.human_error_rate = 0.5
        
        errors = 0
        for _ in range(100):
            event = self.simulator.check_human_error(
                operation_type="passage",
                operator_experience=0.3  # Inexperienced
            )
            if event:
                errors += 1
                assert event.failure_type == FailureType.HUMAN_ERROR
        
        assert errors > 0
        
        self.simulator.human_error_rate = original_rate
    
    def test_failure_effect_on_measurement(self):
        """Test that failures affect measurements."""
        # Create a contamination event
        event = FailureEvent(
            failure_type=FailureType.CONTAMINATION,
            timestamp=None,
            affected_vessels=["T75_1"],
            severity=0.8,
            description="bacterial contamination",
            recoverable=False,
            metadata={}
        )
        
        original_value = 100.0
        affected_value = self.simulator.apply_failure_effect(event, original_value)
        
        # Contamination should reduce value
        assert affected_value < original_value
    
    def test_failure_history(self):
        """Test failure history tracking."""
        # Clear history
        self.simulator.clear_history()
        assert len(self.simulator.failure_history) == 0
        
        # Generate some failures
        self.simulator.contamination_rate = 1.0  # Guarantee failure
        self.simulator.check_for_contamination("T75_1", 1.0, 0.0)
        
        assert len(self.simulator.failure_history) > 0
        
        # Get summary
        summary = self.simulator.get_failure_summary()
        assert summary[FailureType.CONTAMINATION.value] > 0
    
    def test_experience_affects_error_rate(self):
        """Test that operator experience affects error rate."""
        self.simulator.human_error_rate = 0.5
        
        # Novice operator
        novice_errors = 0
        for _ in range(100):
            if self.simulator.check_human_error("passage", operator_experience=0.2):
                novice_errors += 1
        
        # Expert operator
        expert_errors = 0
        for _ in range(100):
            if self.simulator.check_human_error("passage", operator_experience=0.95):
                expert_errors += 1
        
        # Novice should have more errors
        assert novice_errors > expert_errors
