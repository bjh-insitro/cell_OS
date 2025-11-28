"""
Virtual Machine Implementation

Simulates hardware operations for development and testing.
"""

import time
import logging
from typing import Dict, Any
from .base import HardwareInterface

logger = logging.getLogger(__name__)

class VirtualMachine(HardwareInterface):
    """
    A virtual implementation of the hardware interface.
    Logs actions and simulates delays.
    """
    
    def __init__(self, simulation_speed: float = 1.0):
        self.simulation_speed = simulation_speed # Multiplier for delays (1.0 = real time, 0.1 = 10x faster)
        self.connected = False
        
    def _simulate_delay(self, seconds: float):
        """Sleep for scaled duration."""
        time.sleep(seconds * self.simulation_speed)
    
    def connect(self) -> bool:
        logger.info("Connecting to Virtual Machine...")
        self.connected = True
        return True
    
    def disconnect(self):
        logger.info("Disconnecting from Virtual Machine...")
        self.connected = False
        
    def home(self) -> bool:
        logger.info("Homing Virtual Machine...")
        self._simulate_delay(0.5)
        return True
        
    def aspirate(self, volume_ul: float, location: str, **kwargs) -> Dict[str, Any]:
        logger.info(f"Aspirating {volume_ul} uL from {location}")
        self._simulate_delay(0.2)
        return {"status": "success", "action": "aspirate", "volume_ul": volume_ul, "location": location}
    
    def dispense(self, volume_ul: float, location: str, **kwargs) -> Dict[str, Any]:
        logger.info(f"Dispensing {volume_ul} uL to {location}")
        self._simulate_delay(0.2)
        return {"status": "success", "action": "dispense", "volume_ul": volume_ul, "location": location}
        
    def mix(self, volume_ul: float, repetitions: int, location: str, **kwargs) -> Dict[str, Any]:
        logger.info(f"Mixing {volume_ul} uL {repetitions} times at {location}")
        self._simulate_delay(0.1 * repetitions)
        return {"status": "success", "action": "mix", "volume_ul": volume_ul, "repetitions": repetitions}
        
    def move_plate(self, source_loc: str, target_loc: str, **kwargs) -> Dict[str, Any]:
        logger.info(f"Moving plate from {source_loc} to {target_loc}")
        self._simulate_delay(1.0)
        return {"status": "success", "action": "move_plate", "source": source_loc, "target": target_loc}
        
    def centrifuge(self, duration_seconds: float, g_force: float, **kwargs) -> Dict[str, Any]:
        logger.info(f"Centrifuging for {duration_seconds}s at {g_force}g")
        # Don't sleep for full duration in simulation unless requested
        self._simulate_delay(0.5) 
        return {"status": "success", "action": "centrifuge", "duration": duration_seconds}
        
    def incubate(self, duration_seconds: float, temperature_c: float, **kwargs) -> Dict[str, Any]:
        logger.info(f"Incubating for {duration_seconds}s at {temperature_c}C")
        self._simulate_delay(0.5)
        return {"status": "success", "action": "incubate", "duration": duration_seconds}
        
    def count_cells(self, sample_loc: str, **kwargs) -> Dict[str, Any]:
        logger.info(f"Counting cells at {sample_loc}")
        self._simulate_delay(0.5)
        return {
            "status": "success", 
            "action": "count_cells", 
            "count": 1.5e6, 
            "viability": 0.98,
            "concentration": 1.5e6
        }
