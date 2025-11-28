"""
Hardware Interface Base Class

Defines the standard contract for interacting with laboratory hardware.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class HardwareInterface(ABC):
    """
    Abstract base class for hardware interfaces.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the hardware."""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Disconnect from the hardware."""
        pass
    
    @abstractmethod
    def home(self) -> bool:
        """Home the robot/hardware."""
        pass
        
    # --- Liquid Handling ---
    
    @abstractmethod
    def aspirate(self, volume_ul: float, location: str, **kwargs) -> Dict[str, Any]:
        """Aspirate liquid."""
        pass
    
    @abstractmethod
    def dispense(self, volume_ul: float, location: str, **kwargs) -> Dict[str, Any]:
        """Dispense liquid."""
        pass
        
    @abstractmethod
    def mix(self, volume_ul: float, repetitions: int, location: str, **kwargs) -> Dict[str, Any]:
        """Mix liquid."""
        pass
        
    # --- Labware Movement ---
    
    @abstractmethod
    def move_plate(self, source_loc: str, target_loc: str, **kwargs) -> Dict[str, Any]:
        """Move a plate/vessel from one location to another."""
        pass
        
    # --- Peripheral Control ---
    
    @abstractmethod
    def centrifuge(self, duration_seconds: float, g_force: float, **kwargs) -> Dict[str, Any]:
        """Run centrifuge."""
        pass
        
    @abstractmethod
    def incubate(self, duration_seconds: float, temperature_c: float, **kwargs) -> Dict[str, Any]:
        """Incubate."""
        pass
        
    @abstractmethod
    def count_cells(self, sample_loc: str, **kwargs) -> Dict[str, Any]:
        """Count cells."""
        pass
