"""
Simulation Mode for WorkflowExecutor

Extends WorkflowExecutor with synthetic data collection capabilities.
"""

from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from cell_os.workflow_executor import WorkflowExecutor, ExecutionStatus
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


class SimulationExecutor(WorkflowExecutor):
    """
    WorkflowExecutor with enhanced simulation and data collection.
    
    Features:
    - Automatic synthetic data generation
    - Biological state tracking across workflows
    - Data export for ML training
    """
    
    def __init__(self, db_path: str = "data/executions.db", 
                 inventory_manager=None,
                 collect_data: bool = True,
                 simulation_speed: float = 0.0):
        """
        Initialize simulation executor.
        
        Args:
            db_path: Path to execution database
            inventory_manager: Optional inventory manager
            collect_data: Whether to collect synthetic measurements
            simulation_speed: Speed multiplier (0.0 = instant, 1.0 = real-time)
        """
        # Initialize with BiologicalVirtualMachine
        hardware = BiologicalVirtualMachine(simulation_speed=simulation_speed)
        super().__init__(db_path=db_path, inventory_manager=inventory_manager, hardware=hardware)
        
        self.collect_data = collect_data
        self.collected_data: List[Dict[str, Any]] = []
        
        # Register simulation-specific handlers
        self._register_simulation_handlers()
        
    def _register_simulation_handlers(self):
        """Register handlers that collect synthetic data."""
        # Override standard handlers with data-collecting versions
        self.step_handlers["seed"] = self._handle_seed_with_data
        self.step_handlers["passage"] = self._handle_passage_with_data
        self.step_handlers["treat"] = self._handle_treat_with_data
        self.step_handlers["viability_assay"] = self._handle_viability_assay
        self.step_handlers["viability"] = self._handle_viability_assay
        
    def _handle_seed_with_data(self, step) -> Dict[str, Any]:
        """Handle seeding with state initialization."""
        vessel_id = step.parameters.get("vessel_id", "unknown")
        cell_line = step.parameters.get("cell_line", "HEK293T")
        initial_count = step.parameters.get("initial_count", 1e6)
        capacity = step.parameters.get("capacity", 1e7)
        
        # Seed in virtual machine
        self.hardware.seed_vessel(vessel_id, cell_line, initial_count, capacity)
        
        result = {
            "status": "success",
            "vessel_id": vessel_id,
            "cell_line": cell_line,
            "initial_count": initial_count
        }
        
        if self.collect_data:
            self.collected_data.append({
                "timestamp": datetime.now().isoformat(),
                "operation": "seed",
                "vessel_id": vessel_id,
                "cell_line": cell_line,
                "initial_count": initial_count,
                "step_id": step.step_id
            })
            
        return result
        
    def _handle_passage_with_data(self, step) -> Dict[str, Any]:
        """Handle passage with data collection."""
        source = step.parameters.get("source_vessel", "unknown")
        target = step.parameters.get("target_vessel", "unknown")
        split_ratio = step.parameters.get("split_ratio", 4.0)
        
        result = self.hardware.passage_cells(source, target, split_ratio)
        
        if self.collect_data:
            self.collected_data.append({
                "timestamp": datetime.now().isoformat(),
                "operation": "passage",
                "source_vessel": source,
                "target_vessel": target,
                "split_ratio": split_ratio,
                "cells_transferred": result.get("cells_transferred"),
                "viability": result.get("target_viability"),
                "passage_number": result.get("passage_number"),
                "step_id": step.step_id
            })
            
        return result
        
    def _handle_treat_with_data(self, step) -> Dict[str, Any]:
        """Handle compound treatment with data collection."""
        vessel_id = step.parameters.get("vessel_id", "unknown")
        compound = step.parameters.get("compound", "unknown")
        dose_uM = step.parameters.get("dose_uM", 0.0)
        
        result = self.hardware.treat_with_compound(vessel_id, compound, dose_uM)
        
        if self.collect_data:
            self.collected_data.append({
                "timestamp": datetime.now().isoformat(),
                "operation": "treat",
                "vessel_id": vessel_id,
                "compound": compound,
                "dose_uM": dose_uM,
                "viability_effect": result.get("viability_effect"),
                "current_viability": result.get("current_viability"),
                "ic50": result.get("ic50"),
                "step_id": step.step_id
            })
            
        return result
        
    def _handle_viability_assay(self, step) -> Dict[str, Any]:
        """Handle viability assay with synthetic readout."""
        vessel_id = step.parameters.get("vessel_id", "unknown")
        
        # Count cells to get viability
        result = self.hardware.count_cells(vessel_id, vessel_id=vessel_id)
        
        if self.collect_data:
            self.collected_data.append({
                "timestamp": datetime.now().isoformat(),
                "operation": "viability_assay",
                "vessel_id": vessel_id,
                "cell_count": result.get("count"),
                "viability": result.get("viability"),
                "confluence": result.get("confluence"),
                "passage_number": result.get("passage_number"),
                "step_id": step.step_id
            })
            
        return result
        
    def export_data(self, filepath: str, format: str = "json"):
        """
        Export collected synthetic data.
        
        Args:
            filepath: Output file path
            format: Export format ('json' or 'csv')
        """
        if format == "json":
            with open(filepath, 'w') as f:
                json.dump(self.collected_data, f, indent=2)
        elif format == "csv":
            import pandas as pd
            df = pd.DataFrame(self.collected_data)
            df.to_csv(filepath, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
            
    def get_vessel_states(self) -> Dict[str, Dict[str, Any]]:
        """Get current state of all vessels."""
        states = {}
        for vessel_id in self.hardware.vessel_states.keys():
            states[vessel_id] = self.hardware.get_vessel_state(vessel_id)
        return states
        
    def reset_simulation(self):
        """Reset simulation state and clear collected data."""
        self.hardware.vessel_states.clear()
        self.hardware.simulated_time = 0.0
        self.collected_data.clear()
