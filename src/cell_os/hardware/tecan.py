"""
Tecan Hardware Interface.

Generates GWL worklists for Tecan Gemini/Evoware software.
"""

from typing import Dict, Any, List, Optional
import os
from datetime import datetime
import pandas as pd
from .base import HardwareInterface

class TecanInterface(HardwareInterface):
    """
    Interface for Tecan Liquid Handlers (Freedom EVO/Fluent).
    Generates GWL worklists.
    """
    
    def __init__(self, worklist_dir: str = "data/worklists/tecan"):
        self.worklist_dir = worklist_dir
        self.connected = False
        self.current_worklist: List[str] = []
        
        if not os.path.exists(worklist_dir):
            os.makedirs(worklist_dir)
            
    def connect(self) -> bool:
        """Simulate connection."""
        self.connected = True
        print("Connected to Tecan Interface (GWL Generator).")
        return True
    
    def disconnect(self):
        """Disconnect."""
        self.connected = False
        print("Disconnected from Tecan Interface.")
        
    def home(self) -> bool:
        print("Tecan: Homing request received (no-op).")
        return True
        
    def aspirate(self, volume_ul: float, location: str, **kwargs) -> Dict[str, Any]:
        """
        Queue aspiration.
        Format: A;RackLabel;RackID;RackType;Pos;TubeID;Vol;LiqClass;...
        We'll use a simplified format for now.
        """
        # Parse location "Rack_Pos"
        parts = location.split('_')
        rack = parts[0] if len(parts) > 0 else "Rack"
        pos = parts[1] if len(parts) > 1 else "1"
        
        line = f"A;{rack};;;{pos};;{volume_ul};{kwargs.get('liquid_class', 'Water')};;;"
        self.current_worklist.append(line)
        return {"status": "queued", "action": "aspirate"}
    
    def dispense(self, volume_ul: float, location: str, **kwargs) -> Dict[str, Any]:
        """Queue dispense."""
        parts = location.split('_')
        rack = parts[0] if len(parts) > 0 else "Rack"
        pos = parts[1] if len(parts) > 1 else "1"
        
        line = f"D;{rack};;;{pos};;{volume_ul};{kwargs.get('liquid_class', 'Water')};;;"
        self.current_worklist.append(line)
        return {"status": "queued", "action": "dispense"}
        
    def mix(self, volume_ul: float, repetitions: int, location: str, **kwargs) -> Dict[str, Any]:
        """Queue mix (Aspirate + Dispense loop)."""
        # GWL doesn't have a native "Mix" command in standard format, usually handled by scripts.
        # We'll simulate with W (Wash) or just comments.
        self.current_worklist.append(f"C;Mix {volume_ul}ul {repetitions}x at {location}")
        return {"status": "queued", "action": "mix"}
        
    def move_plate(self, source_loc: str, target_loc: str, **kwargs) -> Dict[str, Any]:
        """Queue plate movement (RoMa vector)."""
        # Vector movement
        self.current_worklist.append(f"C;Move {source_loc} to {target_loc}")
        return {"status": "queued", "action": "move_plate"}
        
    def centrifuge(self, duration_seconds: float, g_force: float, **kwargs) -> Dict[str, Any]:
        print(f"Tecan: Centrifuge command ignored.")
        return {"status": "ignored", "reason": "not_supported"}
        
    def incubate(self, duration_seconds: float, temperature_c: float, **kwargs) -> Dict[str, Any]:
        self.current_worklist.append(f"C;Incubate {duration_seconds}s at {temperature_c}C")
        return {"status": "queued", "action": "incubate"}
        
    def count_cells(self, sample_loc: str, **kwargs) -> Dict[str, Any]:
        return {"status": "error", "message": "Cell counting not supported"}
        
    def execute_batch(self, filename: Optional[str] = None) -> str:
        """
        Write the queued actions to a GWL file.
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tecan_worklist_{timestamp}.gwl"
            
        filepath = os.path.join(self.worklist_dir, filename)
        
        with open(filepath, 'w') as f:
            for line in self.current_worklist:
                f.write(line + "\n")
        
        print(f"Tecan: Worklist written to {filepath}")
        
        # Clear queue
        self.current_worklist = []
        
        return filepath
