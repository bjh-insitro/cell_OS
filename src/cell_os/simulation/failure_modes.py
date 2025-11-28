"""
Failure Mode Simulation

Models realistic experimental failures:
- Contamination (bacterial, fungal, mycoplasma)
- Equipment failures (pipette drift, incubator malfunction)
- Reagent quality issues (expired media, degraded compounds)
- Human errors (mislabeling, protocol deviations)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta


class FailureType(Enum):
    """Types of experimental failures."""
    CONTAMINATION = "contamination"
    EQUIPMENT_FAILURE = "equipment_failure"
    REAGENT_DEGRADATION = "reagent_degradation"
    HUMAN_ERROR = "human_error"


class ContaminationType(Enum):
    """Types of contamination."""
    BACTERIAL = "bacterial"
    FUNGAL = "fungal"
    MYCOPLASMA = "mycoplasma"
    YEAST = "yeast"


@dataclass
class FailureEvent:
    """Record of a failure event."""
    failure_type: FailureType
    timestamp: datetime
    affected_vessels: List[str]
    severity: float  # 0-1, impact on experiment
    description: str
    recoverable: bool
    metadata: Dict


class FailureModeSimulator:
    """
    Simulate realistic experimental failures.
    
    Failures occur stochastically based on configurable probabilities.
    """
    
    def __init__(self, random_seed: Optional[int] = None, rng: Optional[np.random.Generator] = None):
        if rng is not None:
            self.rng = rng
        else:
            self.rng = np.random.default_rng(random_seed)
        self.failure_history: List[FailureEvent] = []
        
        # Failure probabilities (per day)
        self.contamination_rate = 0.01  # 1% per day
        self.equipment_failure_rate = 0.005  # 0.5% per day
        self.reagent_degradation_rate = 0.02  # 2% per day
        self.human_error_rate = 0.03  # 3% per day
        
        # Contamination-specific parameters
        self.contamination_types = {
            ContaminationType.BACTERIAL: 0.60,  # 60% of contaminations
            ContaminationType.FUNGAL: 0.25,
            ContaminationType.MYCOPLASMA: 0.10,
            ContaminationType.YEAST: 0.05
        }
        
    def check_for_contamination(self, 
                                vessel_id: str,
                                days_in_culture: float,
                                sterile_technique_quality: float = 0.95) -> Optional[FailureEvent]:
        """
        Check if contamination occurs.
        
        Args:
            vessel_id: Vessel identifier
            days_in_culture: Days since last passage
            sterile_technique_quality: 0-1, quality of aseptic technique
            
        Returns:
            FailureEvent if contamination occurs, None otherwise
        """
        # Probability increases with time and poor technique
        base_prob = self.contamination_rate * days_in_culture
        adjusted_prob = base_prob * (1.0 - sterile_technique_quality)
        
        if self.rng.random() < adjusted_prob:
            # Determine contamination type
            contam_type = self.rng.choice(
                list(self.contamination_types.keys()),
                p=list(self.contamination_types.values())
            )
            
            # Severity varies by type
            severity_map = {
                ContaminationType.BACTERIAL: self.rng.uniform(0.8, 1.0),  # Severe
                ContaminationType.FUNGAL: self.rng.uniform(0.7, 0.95),
                ContaminationType.MYCOPLASMA: self.rng.uniform(0.3, 0.6),  # Subtle
                ContaminationType.YEAST: self.rng.uniform(0.6, 0.9)
            }
            severity = severity_map[contam_type]
            
            event = FailureEvent(
                failure_type=FailureType.CONTAMINATION,
                timestamp=datetime.now(),
                affected_vessels=[vessel_id],
                severity=severity,
                description=f"{contam_type.value} contamination detected",
                recoverable=False,  # Contaminated cultures must be discarded
                metadata={
                    "contamination_type": contam_type.value,
                    "days_in_culture": days_in_culture,
                    "technique_quality": sterile_technique_quality
                }
            )
            
            self.failure_history.append(event)
            return event
            
        return None
    
    def check_equipment_failure(self,
                               equipment_type: str,
                               age_years: float = 1.0) -> Optional[FailureEvent]:
        """
        Check if equipment fails.
        
        Args:
            equipment_type: Type of equipment (pipette, incubator, etc.)
            age_years: Age of equipment in years
            
        Returns:
            FailureEvent if failure occurs
        """
        # Older equipment fails more often
        age_factor = 1.0 + (age_years - 1.0) * 0.2  # 20% increase per year
        prob = self.equipment_failure_rate * age_factor
        
        if self.rng.random() < prob:
            # Different equipment has different failure modes
            failure_modes = {
                "pipette": ["drift", "tip_ejection_failure", "motor_failure"],
                "incubator": ["temperature_fluctuation", "CO2_failure", "door_seal"],
                "centrifuge": ["imbalance_sensor", "rotor_failure", "speed_control"],
                "microscope": ["lamp_failure", "stage_drift", "autofocus_failure"]
            }
            
            mode = self.rng.choice(failure_modes.get(equipment_type, ["generic_failure"]))
            
            # Severity varies
            severity = self.rng.uniform(0.3, 0.9)
            
            # Some failures are recoverable (can be fixed)
            recoverable = self.rng.random() < 0.6  # 60% can be fixed
            
            event = FailureEvent(
                failure_type=FailureType.EQUIPMENT_FAILURE,
                timestamp=datetime.now(),
                affected_vessels=[],  # Affects all current experiments
                severity=severity,
                description=f"{equipment_type} {mode}",
                recoverable=recoverable,
                metadata={
                    "equipment_type": equipment_type,
                    "failure_mode": mode,
                    "age_years": age_years
                }
            )
            
            self.failure_history.append(event)
            return event
            
        return None
    
    def check_reagent_degradation(self,
                                  reagent_name: str,
                                  days_since_opening: float,
                                  storage_temp_c: float = 4.0) -> Optional[FailureEvent]:
        """
        Check if reagent has degraded.
        
        Args:
            reagent_name: Name of reagent
            days_since_opening: Days since bottle was opened
            storage_temp_c: Storage temperature
            
        Returns:
            FailureEvent if degradation detected
        """
        # Degradation accelerates with time and poor storage
        base_prob = self.reagent_degradation_rate * (days_since_opening / 30.0)
        
        # Temperature abuse increases degradation
        if storage_temp_c > 8.0:  # Should be at 4°C
            temp_factor = 1.0 + (storage_temp_c - 4.0) * 0.1
            base_prob *= temp_factor
        
        if self.rng.random() < base_prob:
            # Severity increases with age
            severity = min(1.0, days_since_opening / 90.0)  # Worse after 3 months
            
            event = FailureEvent(
                failure_type=FailureType.REAGENT_DEGRADATION,
                timestamp=datetime.now(),
                affected_vessels=[],  # Affects all experiments using this reagent
                severity=severity,
                description=f"{reagent_name} degraded",
                recoverable=False,  # Need fresh reagent
                metadata={
                    "reagent_name": reagent_name,
                    "days_since_opening": days_since_opening,
                    "storage_temp_c": storage_temp_c
                }
            )
            
            self.failure_history.append(event)
            return event
            
        return None
    
    def check_human_error(self,
                         operation_type: str,
                         operator_experience: float = 0.8) -> Optional[FailureEvent]:
        """
        Check if human error occurs.
        
        Args:
            operation_type: Type of operation (passage, treatment, etc.)
            operator_experience: 0-1, experience level (1 = expert)
            
        Returns:
            FailureEvent if error occurs
        """
        # Less experienced operators make more errors
        prob = self.human_error_rate * (1.0 - operator_experience)
        
        if self.rng.random() < prob:
            # Common error types
            error_types = [
                "mislabeling",
                "wrong_volume",
                "wrong_reagent",
                "missed_step",
                "cross_contamination",
                "incorrect_incubation_time"
            ]
            
            error = self.rng.choice(error_types)
            
            # Severity varies by error type
            severity_map = {
                "mislabeling": 0.9,  # Very serious
                "wrong_volume": 0.5,
                "wrong_reagent": 0.95,
                "missed_step": 0.7,
                "cross_contamination": 0.85,
                "incorrect_incubation_time": 0.4
            }
            severity = severity_map.get(error, 0.6)
            
            # Some errors can be caught and corrected
            recoverable = error in ["wrong_volume", "incorrect_incubation_time"]
            
            event = FailureEvent(
                failure_type=FailureType.HUMAN_ERROR,
                timestamp=datetime.now(),
                affected_vessels=[],
                severity=severity,
                description=f"Human error: {error}",
                recoverable=recoverable,
                metadata={
                    "operation_type": operation_type,
                    "error_type": error,
                    "operator_experience": operator_experience
                }
            )
            
            self.failure_history.append(event)
            return event
            
        return None
    
    def apply_failure_effect(self,
                            failure: FailureEvent,
                            measurement_value: float) -> float:
        """
        Apply the effect of a failure on a measurement.
        
        Args:
            failure: The failure event
            measurement_value: Original measurement
            
        Returns:
            Modified measurement value
        """
        if failure.failure_type == FailureType.CONTAMINATION:
            # Contamination reduces viability and changes morphology
            reduction = failure.severity * self.rng.uniform(0.5, 1.0)
            return measurement_value * (1.0 - reduction)
            
        elif failure.failure_type == FailureType.EQUIPMENT_FAILURE:
            # Equipment failures add noise or bias
            if "drift" in failure.description:
                # Systematic bias
                bias = failure.severity * self.rng.uniform(-0.2, 0.2)
                return measurement_value * (1.0 + bias)
            else:
                # Random noise
                noise = failure.severity * 0.3
                return measurement_value * self.rng.normal(1.0, noise)
                
        elif failure.failure_type == FailureType.REAGENT_DEGRADATION:
            # Degraded reagents reduce effectiveness
            reduction = failure.severity * 0.5
            return measurement_value * (1.0 - reduction)
            
        elif failure.failure_type == FailureType.HUMAN_ERROR:
            # Errors can cause wide variation
            if "wrong_volume" in failure.description:
                # Volume error
                error = failure.severity * self.rng.uniform(-0.3, 0.3)
                return measurement_value * (1.0 + error)
            elif "mislabeling" in failure.description:
                # Return random value (completely wrong sample)
                return self.rng.uniform(0, measurement_value * 2)
            else:
                # General degradation
                return measurement_value * (1.0 - failure.severity * 0.3)
        
        return measurement_value
    
    def get_failure_summary(self) -> Dict[str, int]:
        """Get summary of all failures."""
        summary = {ft.value: 0 for ft in FailureType}
        for event in self.failure_history:
            summary[event.failure_type.value] += 1
        return summary
    
    def clear_history(self):
        """Clear failure history."""
        self.failure_history.clear()
