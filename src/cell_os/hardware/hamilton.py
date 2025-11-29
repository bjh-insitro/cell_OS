"""
Hamilton Hardware Interface.

Generates worklists for Hamilton VENUS software.
"""

from typing import Dict, Any, List, Optional
import os
from datetime import datetime
import pandas as pd
from .base import HardwareInterface

class HamiltonInterface(HardwareInterface):
    """
    Interface for Hamilton Liquid Handlers (STAR/Vantage).
    Generates CSV worklists for execution.
    """
    
    def __init__(self, worklist_dir: str = "data/worklists/hamilton"):
        self.worklist_dir = worklist_dir
        self.connected = False
        self.current_worklist: List[Dict[str, Any]] = []
        
        if not os.path.exists(worklist_dir):
            os.makedirs(worklist_dir)
            
    def connect(self) -> bool:
        """Simulate connection."""
        self.connected = True
        print("Connected to Hamilton Interface (Worklist Generator).")
        return True
    
    def disconnect(self):
        """Disconnect."""
        self.connected = False
        print("Disconnected from Hamilton Interface.")
        
    def home(self) -> bool:
        """
        Hamiltons don't typically need explicit homing from external software 
        unless recovering from error. We'll just log it.
        """
        print("Hamilton: Homing request received (no-op).")
        return True
        
    def aspirate(self, volume_ul: float, location: str, **kwargs) -> Dict[str, Any]:
        """
        Queue aspiration. 
        Note: Hamilton worklists usually define a transfer (Asp + Disp).
        We'll store this as a partial transfer or assume immediate dispense follows.
        For simplicity, we'll log it as an action but true worklists need source AND dest.
        """
        self.current_worklist.append({
            "Action": "Aspirate",
            "Volume": volume_ul,
            "Location": location,
            "LiquidClass": kwargs.get("liquid_class", "Default")
        })
        return {"status": "queued", "action": "aspirate"}
    
    def dispense(self, volume_ul: float, location: str, **kwargs) -> Dict[str, Any]:
        """Queue dispense."""
        self.current_worklist.append({
            "Action": "Dispense",
            "Volume": volume_ul,
            "Location": location,
            "LiquidClass": kwargs.get("liquid_class", "Default")
        })
        return {"status": "queued", "action": "dispense"}
        
    def mix(self, volume_ul: float, repetitions: int, location: str, **kwargs) -> Dict[str, Any]:
        """Queue mix."""
        self.current_worklist.append({
            "Action": "Mix",
            "Volume": volume_ul,
            "Repetitions": repetitions,
            "Location": location
        })
        return {"status": "queued", "action": "mix"}
        
    def move_plate(self, source_loc: str, target_loc: str, **kwargs) -> Dict[str, Any]:
        """Queue plate movement (e.g. via iSWAP/CoRE gripper)."""
        self.current_worklist.append({
            "Action": "MovePlate",
            "Source": source_loc,
            "Target": target_loc,
            "GripMode": kwargs.get("grip_mode", "Portrait")
        })
        return {"status": "queued", "action": "move_plate"}
        
    def centrifuge(self, duration_seconds: float, g_force: float, **kwargs) -> Dict[str, Any]:
        """Hamiltons don't usually control centrifuges directly unless integrated."""
        print(f"Hamilton: Centrifuge command ignored (manual intervention required).")
        return {"status": "ignored", "reason": "not_supported"}
        
    def incubate(self, duration_seconds: float, temperature_c: float, **kwargs) -> Dict[str, Any]:
        """Hamilton Inheco/ODTC control."""
        self.current_worklist.append({
            "Action": "Incubate",
            "Duration": duration_seconds,
            "Temperature": temperature_c
        })
        return {"status": "queued", "action": "incubate"}
        
    def count_cells(self, sample_loc: str, **kwargs) -> Dict[str, Any]:
        """Not supported on liquid handler."""
        return {"status": "error", "message": "Cell counting not supported"}
        
    def execute_batch(self, filename: Optional[str] = None) -> str:
        """
        Write the queued actions to a worklist file.
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"hamilton_worklist_{timestamp}.csv"
            
        filepath = os.path.join(self.worklist_dir, filename)
        
        df = pd.DataFrame(self.current_worklist)
        df.to_csv(filepath, index=False)
        
        print(f"Hamilton: Worklist written to {filepath}")
        
        # Clear queue
        self.current_worklist = []
        
        return filepath
