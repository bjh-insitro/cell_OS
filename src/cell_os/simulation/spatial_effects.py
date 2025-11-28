"""
Spatial Effects Simulation

Models spatial variability in plate-based experiments:
- Edge effects (evaporation, temperature)
- Position-dependent variation
- Cross-contamination
- Liquid handler accuracy
"""

import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class PlateGeometry:
    """Define plate geometry and well positions."""
    rows: int
    cols: int
    well_volume_ul: float = 200.0
    
    def get_well_position(self, well_id: str) -> Tuple[int, int]:
        """Convert well ID (e.g., 'A1') to (row, col) indices."""
        row = ord(well_id[0].upper()) - ord('A')
        col = int(well_id[1:]) - 1
        return (row, col)
    
    def get_well_id(self, row: int, col: int) -> str:
        """Convert (row, col) indices to well ID."""
        return f"{chr(ord('A') + row)}{col + 1}"
    
    def is_edge_well(self, row: int, col: int) -> bool:
        """Check if well is on the edge of the plate."""
        return (row == 0 or row == self.rows - 1 or 
                col == 0 or col == self.cols - 1)
    
    def get_distance_from_center(self, row: int, col: int) -> float:
        """Get Euclidean distance from plate center."""
        center_row = (self.rows - 1) / 2
        center_col = (self.cols - 1) / 2
        return np.sqrt((row - center_row)**2 + (col - center_col)**2)


class SpatialEffectsSimulator:
    """
    Simulate spatial effects in plate-based experiments.
    
    Features:
    - Edge effects (evaporation, temperature)
    - Temperature gradients
    - Position-dependent pipetting accuracy
    - Cross-contamination
    """
    
    def __init__(self, plate_geometry: PlateGeometry, random_seed: Optional[int] = None):
        self.plate = plate_geometry
        self.rng = np.random.default_rng(random_seed)
        
        # Effect parameters (can be tuned)
        self.edge_evaporation_rate = 0.05  # 5% volume loss at edges
        self.edge_temperature_effect = 0.02  # 2% growth rate change at edges
        self.pipetting_cv_base = 0.02  # 2% base CV
        self.pipetting_cv_position = 0.01  # Additional 1% CV at corners
        self.cross_contamination_prob = 0.001  # 0.1% chance per adjacent well
        
    def apply_edge_effects(self, well_id: str, value: float, effect_type: str = "evaporation") -> float:
        """
        Apply edge effects to a measurement.
        
        Args:
            well_id: Well identifier (e.g., 'A1')
            value: Measured value
            effect_type: Type of effect ('evaporation', 'temperature', 'growth')
            
        Returns:
            Modified value with edge effects
        """
        row, col = self.plate.get_well_position(well_id)
        
        if not self.plate.is_edge_well(row, col):
            return value
            
        if effect_type == "evaporation":
            # Edge wells lose volume due to evaporation
            volume_loss = self.edge_evaporation_rate * self.rng.normal(1.0, 0.2)
            return value * (1.0 - volume_loss)
            
        elif effect_type == "temperature":
            # Edge wells have different temperature (affects growth)
            temp_effect = self.edge_temperature_effect * self.rng.normal(1.0, 0.3)
            return value * (1.0 + temp_effect)
            
        elif effect_type == "growth":
            # Combination of temperature and evaporation effects on growth
            evap_effect = -self.edge_evaporation_rate * 0.5  # Reduced growth
            temp_effect = self.edge_temperature_effect
            combined = evap_effect + temp_effect
            return value * (1.0 + combined * self.rng.normal(1.0, 0.2))
            
        return value
    
    def apply_temperature_gradient(self, well_id: str, base_temperature: float = 37.0) -> float:
        """
        Simulate temperature gradient across plate.
        
        Incubators often have slight temperature variations.
        
        Args:
            well_id: Well identifier
            base_temperature: Target temperature in °C
            
        Returns:
            Actual temperature at this well position
        """
        row, col = self.plate.get_well_position(well_id)
        
        # Distance from center affects temperature
        dist = self.plate.get_distance_from_center(row, col)
        max_dist = self.plate.get_distance_from_center(0, 0)
        
        # Temperature decreases slightly towards edges
        gradient_magnitude = 0.3  # Max 0.3°C variation
        temp_offset = -(dist / max_dist) * gradient_magnitude
        
        # Add random variation
        temp_offset += self.rng.normal(0, 0.1)
        
        return base_temperature + temp_offset
    
    def apply_pipetting_error(self, well_id: str, target_volume: float) -> float:
        """
        Simulate position-dependent pipetting accuracy.
        
        Liquid handlers are less accurate at plate corners.
        
        Args:
            well_id: Well identifier
            target_volume: Intended volume in μL
            
        Returns:
            Actual dispensed volume
        """
        row, col = self.plate.get_well_position(well_id)
        
        # Base pipetting error
        cv = self.pipetting_cv_base
        
        # Additional error at corners
        dist = self.plate.get_distance_from_center(row, col)
        max_dist = self.plate.get_distance_from_center(0, 0)
        cv += self.pipetting_cv_position * (dist / max_dist)
        
        # Apply error
        actual_volume = target_volume * self.rng.normal(1.0, cv)
        return max(0, actual_volume)
    
    def check_cross_contamination(self, well_id: str, contaminated_wells: set) -> bool:
        """
        Check if well gets contaminated from adjacent wells.
        
        Args:
            well_id: Well to check
            contaminated_wells: Set of currently contaminated well IDs
            
        Returns:
            True if well becomes contaminated
        """
        row, col = self.plate.get_well_position(well_id)
        
        # Check all adjacent wells (including diagonals)
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                    
                adj_row, adj_col = row + dr, col + dc
                
                # Check bounds
                if (0 <= adj_row < self.plate.rows and 
                    0 <= adj_col < self.plate.cols):
                    
                    adj_well = self.plate.get_well_id(adj_row, adj_col)
                    
                    if adj_well in contaminated_wells:
                        # Chance of contamination from adjacent well
                        if self.rng.random() < self.cross_contamination_prob:
                            return True
        
        return False
    
    def generate_plate_heatmap(self, effect_type: str = "evaporation") -> np.ndarray:
        """
        Generate a heatmap of spatial effects across the plate.
        
        Args:
            effect_type: Type of effect to visualize
            
        Returns:
            2D array with effect magnitude for each well
        """
        heatmap = np.zeros((self.plate.rows, self.plate.cols))
        
        for row in range(self.plate.rows):
            for col in range(self.plate.cols):
                well_id = self.plate.get_well_id(row, col)
                
                if effect_type == "evaporation":
                    if self.plate.is_edge_well(row, col):
                        heatmap[row, col] = self.edge_evaporation_rate
                        
                elif effect_type == "temperature":
                    temp = self.apply_temperature_gradient(well_id)
                    heatmap[row, col] = temp - 37.0  # Deviation from target
                    
                elif effect_type == "distance":
                    heatmap[row, col] = self.plate.get_distance_from_center(row, col)
        
        return heatmap
    
    def simulate_plate_experiment(self, 
                                  base_values: Dict[str, float],
                                  apply_evaporation: bool = True,
                                  apply_temperature: bool = True,
                                  apply_pipetting: bool = True) -> Dict[str, float]:
        """
        Simulate a complete plate experiment with all spatial effects.
        
        Args:
            base_values: Dict mapping well_id to ideal measurement value
            apply_evaporation: Whether to apply edge evaporation
            apply_temperature: Whether to apply temperature gradients
            apply_pipetting: Whether to apply pipetting errors
            
        Returns:
            Dict mapping well_id to measured value (with spatial effects)
        """
        results = {}
        
        for well_id, base_value in base_values.items():
            value = base_value
            
            if apply_evaporation:
                value = self.apply_edge_effects(well_id, value, "evaporation")
            
            if apply_temperature:
                # Temperature affects growth rate
                temp = self.apply_temperature_gradient(well_id)
                temp_factor = 1.0 + (temp - 37.0) * 0.05  # 5% per degree
                value *= temp_factor
            
            if apply_pipetting:
                # Pipetting error affects concentration
                volume_error = self.apply_pipetting_error(well_id, 100.0) / 100.0
                value *= volume_error
            
            results[well_id] = value
        
        return results


# Standard plate geometries
PLATE_96 = PlateGeometry(rows=8, cols=12, well_volume_ul=200)
PLATE_384 = PlateGeometry(rows=16, cols=24, well_volume_ul=50)
PLATE_6 = PlateGeometry(rows=2, cols=3, well_volume_ul=2000)
PLATE_24 = PlateGeometry(rows=4, cols=6, well_volume_ul=1000)
