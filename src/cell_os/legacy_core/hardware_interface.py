"""
Hardware Abstraction Layer (HAL) for cell_OS.

This module defines the contract between the autonomous agents and the physical (or simulated) world.
It allows the system to switch between a 'MockSimulator' for fast development and a 'LabController'
for real-world execution without changing the agent logic.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union
import random
import time

class HardwareInterface(ABC):
    """
    Abstract Base Class defining the contract for all lab operations.
    All physical interactions must go through this interface.
    """

    @abstractmethod
    def dispense_liquid(self, wells: List[str], liquid_id: str, volume_ul: float) -> bool:
        """
        Dispense a specific liquid into a list of wells.
        
        Args:
            wells: List of well identifiers (e.g., ["A1", "A2"]).
            liquid_id: Identifier for the liquid (e.g., "LV_Batch_1", "Media_DMEM").
            volume_ul: Volume to dispense per well in microliters.
            
        Returns:
            bool: True if operation was successful, False otherwise.
        """
        pass

    @abstractmethod
    def run_microscopy_acquisition(self, plate_barcode: str, channels: List[str]) -> Dict[str, Any]:
        """
        Run a high-content imaging acquisition protocol.
        
        Args:
            plate_barcode: Barcode of the plate to image.
            channels: List of channels to acquire (e.g., ["DAPI", "GFP", "RFP"]).
            
        Returns:
            Dict: Metadata about the acquisition (e.g., image paths, timestamp).
        """
        pass

    @abstractmethod
    def measure_fluorescence(self, plate_barcode: str, target_channel: str) -> Dict[str, Union[float, Dict]]:
        """
        Measure fluorescence (bulk or single-cell) to determine phenotypes like Transduction Efficiency.
        
        Args:
            plate_barcode: Barcode of the plate.
            target_channel: Channel to measure (e.g., "BFP").
            
        Returns:
            Dict: Results dictionary. For titration, might include {'MOI': 0.3, 'TE': 0.25}.
        """
        pass

    @abstractmethod
    def run_generic_protocol(self, protocol_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a complex, named protocol on the automation system.
        
        Args:
            protocol_name: Name of the protocol (e.g., "Passage_Cells", "Fix_Plate").
            params: Parameters for the protocol.
            
        Returns:
            Dict: Execution confirmation and metadata.
        """
        pass


class MockSimulator(HardwareInterface):
    """
    A simulated lab environment for development and testing.
    Generates synthetic data consistent with the cell_OS physics models.
    """

    def dispense_liquid(self, wells: List[str], liquid_id: str, volume_ul: float) -> bool:
        print(f"[SIM] Dispensing {volume_ul}uL of {liquid_id} into {len(wells)} wells: {wells[:3]}...")
        # In a more advanced sim, we would update the state of a virtual plate here.
        return True

    def run_microscopy_acquisition(self, plate_barcode: str, channels: List[str]) -> Dict[str, Any]:
        print(f"[SIM] Running High-Content Imaging on {plate_barcode}. Channels: {channels}")
        time.sleep(0.5) # Simulate acquisition time
        return {
            "status": "synthetic_data_generated",
            "timestamp": time.time(),
            "plate_barcode": plate_barcode,
            "image_count": 1000,
            "output_path": f"/data/raw/mock_img_run_{int(time.time())}.csv"
        }

    def measure_fluorescence(self, plate_barcode: str, target_channel: str) -> Dict[str, Union[float, Dict]]:
        print(f"[SIM] Measuring Fluorescence ({target_channel}) on {plate_barcode}...")
        
        # Simulate a typical Lentiviral Titration result
        # Randomly generate an MOI between 0.1 and 5.0
        simulated_moi = random.uniform(0.1, 5.0)
        
        # Calculate Transduction Efficiency (TE) using Poisson: TE = 1 - e^(-MOI)
        # Add some noise
        theoretical_te = 1.0 - 2.71828**(-simulated_moi)
        measured_te = min(0.99, max(0.01, theoretical_te + random.gauss(0, 0.02)))
        
        return {
            "plate_barcode": plate_barcode,
            "channel": target_channel,
            "mean_intensity": random.uniform(100, 5000),
            "transduction_efficiency": measured_te,
            "estimated_moi": simulated_moi,
            "raw_data": {"well_A1": measured_te} # Simplified
        }

    def run_generic_protocol(self, protocol_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        print(f"[SIM] Executing Protocol: {protocol_name} with params: {params}")
        return {
            "status": "success",
            "protocol": protocol_name,
            "execution_time": 1.2
        }


class LabController(HardwareInterface):
    """
    The interface to real physical hardware.
    Currently a placeholder for future integration with SiLA2 or vendor APIs.
    """

    def dispense_liquid(self, wells: List[str], liquid_id: str, volume_ul: float) -> bool:
        raise NotImplementedError("Requires connection to real automation backend.")

    def run_microscopy_acquisition(self, plate_barcode: str, channels: List[str]) -> Dict[str, Any]:
        raise NotImplementedError("Requires connection to real automation backend.")

    def measure_fluorescence(self, plate_barcode: str, target_channel: str) -> Dict[str, Union[float, Dict]]:
        raise NotImplementedError("Requires connection to real automation backend.")

    def run_generic_protocol(self, protocol_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Requires connection to real automation backend.")
