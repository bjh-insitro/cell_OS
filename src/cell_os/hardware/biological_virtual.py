"""
Biological Virtual Machine

Enhanced VirtualMachine with biological state tracking and realistic synthetic data generation.
"""

import time
import logging
import numpy as np
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from .virtual import VirtualMachine

# Import database for parameter loading
try:
    from ..database.repositories.simulation_params import SimulationParamsRepository
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("SimulationParamsRepository not available, will use YAML fallback")

logger = logging.getLogger(__name__)


class VesselState:
    """Tracks the biological state of a vessel."""
    
    def __init__(self, vessel_id: str, cell_line: str, initial_count: float = 0):
        self.vessel_id = vessel_id
        self.cell_line = cell_line
        self.cell_count = initial_count
        self.viability = 0.98
        self.passage_number = 0
        self.last_passage_time = 0.0
        self.last_feed_time = 0.0
        self.confluence = 0.0
        self.vessel_capacity = 1e7  # Default capacity
        self.compounds = {}  # compound_id -> concentration
        self.seed_time = 0.0


class BiologicalVirtualMachine(VirtualMachine):
    """
    Enhanced VirtualMachine with biological simulation capabilities.
    
    Features:
    - Cell growth modeling (exponential with saturation)
    - Viability dynamics (confluence-dependent)
    - Passage tracking
    - Compound treatment effects
    - Realistic noise injection
    - Data-driven parameters from YAML
    """
    
    def __init__(self, simulation_speed: float = 1.0, 
                 params_file: Optional[str] = None,
                 use_database: bool = True):
        super().__init__(simulation_speed=simulation_speed)
        self.vessel_states: Dict[str, VesselState] = {}
        self.simulated_time = 0.0
        self.use_database = use_database and DB_AVAILABLE
        self._load_parameters(params_file)
        self._load_raw_yaml_for_nested_params(params_file)  # Load nested params for CellROX/segmentation
    
    def _load_parameters(self, params_file: Optional[str] = None):
        """Load simulation parameters from database or YAML file."""
        
        # Try database first if enabled
        if self.use_database:
            try:
                db = SimulationParamsRepository()
                logger.info("Loading parameters from database")
                
                # Load cell line parameters
                self.cell_line_params = {}
                for cell_line_id in db.get_all_cell_lines():
                    params = db.get_cell_line_params(cell_line_id)
                    if params:
                        self.cell_line_params[cell_line_id] = {
                            'doubling_time_h': params.doubling_time_h,
                            'max_confluence': params.max_confluence,
                            'max_passage': params.max_passage,
                            'senescence_rate': params.senescence_rate,
                            'seeding_efficiency': params.seeding_efficiency,
                            'passage_stress': params.passage_stress,
                            'cell_count_cv': params.cell_count_cv,
                            'viability_cv': params.viability_cv,
                            'biological_cv': params.biological_cv,
                            'coating_required': params.coating_required
                        }
                
                # Load compound sensitivity
                self.compound_sensitivity = {}
                for compound in db.get_all_compounds():
                    self.compound_sensitivity[compound] = {}
                    for cell_line_id in db.get_all_cell_lines():
                        sensitivity = db.get_compound_sensitivity(compound, cell_line_id)
                        if sensitivity:
                            self.compound_sensitivity[compound][cell_line_id] = sensitivity.ic50_um
                            if 'hill_slope' not in self.compound_sensitivity[compound]:
                                self.compound_sensitivity[compound]['hill_slope'] = sensitivity.hill_slope

                # Drop compounds that never returned any sensitivity rows so we can
                # detect incomplete databases and fall back to YAML fixtures.
                self.compound_sensitivity = {
                    compound: data
                    for compound, data in self.compound_sensitivity.items()
                    if any(key != 'hill_slope' for key in data.keys())
                }
                
                # Load defaults
                self.defaults = {}
                for param_name in ['doubling_time_h', 'max_confluence', 'max_passage', 
                                  'senescence_rate', 'seeding_efficiency', 'passage_stress',
                                  'cell_count_cv', 'viability_cv', 'biological_cv',
                                  'default_ic50', 'default_hill_slope']:
                    value = db.get_default_param(param_name)
                    if value is not None:
                        self.defaults[param_name] = value
                
                has_defaults = bool(self.defaults)
                if self.cell_line_params and self.compound_sensitivity and has_defaults:
                    logger.info("Loaded parameters from database")
                    logger.info(f"  Cell lines: {len(self.cell_line_params)}")
                    logger.info(f"  Compounds: {len(self.compound_sensitivity)}")
                    return

                logger.warning(
                    "Simulation parameter database is missing data "
                    "(cell_lines=%s, compounds=%s, defaults=%s); "
                    "falling back to YAML",
                    len(self.cell_line_params),
                    len(self.compound_sensitivity),
                    len(self.defaults),
                )
                
            except Exception as e:
                logger.warning(f"Failed to load from database: {e}, falling back to YAML")
        
        # Fallback to YAML
        if params_file is None:
            # Default to data/simulation_parameters.yaml
            params_file = Path(__file__).parent.parent.parent.parent / "data" / "simulation_parameters.yaml"
        
        try:
            with open(params_file, 'r') as f:
                params = yaml.safe_load(f)
                
            self.cell_line_params = params.get('cell_lines', {})
            self.compound_sensitivity = params.get('compound_sensitivity', {})
            self.defaults = params.get('defaults', {})
            
            logger.info(f"Loaded simulation parameters from {params_file}")
            logger.info(f"  Cell lines: {len(self.cell_line_params)}")
            logger.info(f"  Compounds: {len(self.compound_sensitivity)}")
            
        except FileNotFoundError:
            logger.warning(f"Parameters file not found: {params_file}, using defaults")
            self._use_default_parameters()
            
    def _use_default_parameters(self):
        """Fallback to hardcoded parameters if YAML not found."""
        self.cell_line_params = {
            "HEK293T": {"doubling_time_h": 24.0, "max_confluence": 0.9},
            "HeLa": {"doubling_time_h": 20.0, "max_confluence": 0.85},
            "Jurkat": {"doubling_time_h": 18.0, "max_confluence": 1.0},
        }
        self.compound_sensitivity = {
            "staurosporine": {"HEK293T": 0.05, "HeLa": 0.08, "hill_slope": 1.2},
            "tunicamycin": {"HEK293T": 0.80, "HeLa": 0.60, "hill_slope": 1.0},
        }
        self.defaults = {
            "doubling_time_h": 24.0,
            "max_confluence": 0.9,
            "default_ic50": 1.0,
            "default_ic50": 1.0,
            "default_hill_slope": 1.0,
            "lag_duration_h": 12.0,
            "edge_penalty": 0.15
        }
        
    def advance_time(self, hours: float):
        """Advance simulated time and update all vessel states."""
        self.simulated_time += hours
        
        for vessel in self.vessel_states.values():
            self._update_vessel_growth(vessel, hours)
            
    def _update_vessel_growth(self, vessel: VesselState, hours: float):
        """Update cell count based on growth model."""
        if vessel.cell_count == 0:
            return
            
        # Get cell line parameters with fallback to defaults
        params = self.cell_line_params.get(vessel.cell_line, self.defaults)
        doubling_time = params.get("doubling_time_h", self.defaults.get("doubling_time_h", 24.0))
        max_confluence = params.get("max_confluence", self.defaults.get("max_confluence", 0.9))
        
        # Exponential growth with confluence-dependent saturation
        growth_rate = np.log(2) / doubling_time
        
        # --- 1. Lag Phase Dynamics ---
        # Growth ramps up linearly over lag_duration_h
        lag_duration = params.get("lag_duration_h", self.defaults.get("lag_duration_h", 12.0))
        time_since_seed = self.simulated_time - vessel.seed_time
        
        lag_factor = 1.0
        if time_since_seed < lag_duration:
            lag_factor = max(0.0, time_since_seed / lag_duration)
            
        # --- 2. Spatial Edge Effects ---
        # Penalty for edge wells (evaporation/temp gradients)
        edge_penalty = 0.0
        if self._is_edge_well(vessel.vessel_id):
            edge_penalty = params.get("edge_penalty", self.defaults.get("edge_penalty", 0.15))
            
        # Apply factors
        effective_growth_rate = growth_rate * lag_factor * (1.0 - edge_penalty)
        
        # Reduce growth as confluence increases
        confluence = vessel.cell_count / vessel.vessel_capacity
        growth_factor = 1.0 - (confluence / max_confluence) ** 2
        growth_factor = max(0, growth_factor)
        
        # Update count
        vessel.cell_count *= np.exp(effective_growth_rate * hours * growth_factor)
        vessel.confluence = vessel.cell_count / vessel.vessel_capacity
        
        # Viability decreases with over-confluence
        if vessel.confluence > max_confluence:
            viability_loss = (vessel.confluence - max_confluence) * 0.1
            vessel.viability = max(0.5, vessel.viability - viability_loss)
            
    def _is_edge_well(self, vessel_id: str) -> bool:
        """
        Check if vessel is an edge well (Rows A/H, Cols 1/12).
        Assumes format like 'Plate1_A01' or just 'A01'.
        """
        # Extract the well part (last 3 chars usually)
        # Try to find pattern [A-H][0-9]{2}
        import re
        match = re.search(r'([A-P])(\d{1,2})$', vessel_id)
        if match:
            row = match.group(1)
            col = int(match.group(2))
            
            # Standard 96-well plate definition
            is_row_edge = (row == 'A') or (row == 'H')
            is_col_edge = (col == 1) or (col == 12)
            
            return is_row_edge or is_col_edge
            
        return False
            
    def seed_vessel(self, vessel_id: str, cell_line: str, initial_count: float, capacity: float = 1e7):
        """Initialize a vessel with cells."""
        state = VesselState(vessel_id, cell_line, initial_count)
        state.vessel_capacity = capacity
        state.vessel_capacity = capacity
        state.last_passage_time = self.simulated_time
        state.seed_time = self.simulated_time
        self.vessel_states[vessel_id] = state
        logger.info(f"Seeded {vessel_id} with {initial_count:.2e} {cell_line} cells")
        
    def count_cells(self, sample_loc: str, **kwargs) -> Dict[str, Any]:
        """Count cells with realistic biological variation."""
        vessel_id = kwargs.get("vessel_id", sample_loc)
        
        if vessel_id not in self.vessel_states:
            # Return default if vessel not tracked
            return super().count_cells(sample_loc, **kwargs)
            
        vessel = self.vessel_states[vessel_id]
        
        # Get cell line-specific noise parameters
        params = self.cell_line_params.get(vessel.cell_line, self.defaults)
        count_cv = params.get("cell_count_cv", self.defaults.get("cell_count_cv", 0.10))
        viability_cv = params.get("viability_cv", self.defaults.get("viability_cv", 0.02))
        
        # Add measurement noise
        measured_count = vessel.cell_count * np.random.normal(1.0, count_cv)
        measured_count = max(0, measured_count)
        
        # Viability measurement noise
        measured_viability = vessel.viability * np.random.normal(1.0, viability_cv)
        measured_viability = np.clip(measured_viability, 0.0, 1.0)
        
        self._simulate_delay(0.5)
        
        return {
            "status": "success",
            "action": "count_cells",
            "count": measured_count,
            "viability": measured_viability,
            "concentration": measured_count / 1.0,  # Assume 1mL sample
            "confluence": vessel.confluence,
            "passage_number": vessel.passage_number,
            "vessel_id": vessel_id,
            "timestamp": datetime.now().isoformat()
        }
        
    def passage_cells(self, source_vessel: str, target_vessel: str, split_ratio: float = 4.0, **kwargs) -> Dict[str, Any]:
        """Simulate cell passaging."""
        if source_vessel not in self.vessel_states:
            logger.warning(f"Source vessel {source_vessel} not found in state tracker")
            return {"status": "error", "message": "Vessel not found"}
            
        source = self.vessel_states[source_vessel]
        
        # Calculate cells transferred
        cells_transferred = source.cell_count / split_ratio
        
        # Get cell line-specific passage stress
        params = self.cell_line_params.get(source.cell_line, self.defaults)
        passage_stress = params.get("passage_stress", self.defaults.get("passage_stress", 0.02))
        
        # Passage stress reduces viability slightly
        new_viability = source.viability * (1.0 - passage_stress)
        
        # Create new vessel state
        target_capacity = kwargs.get("target_capacity", source.vessel_capacity)
        target = VesselState(target_vessel, source.cell_line, cells_transferred)
        target.viability = new_viability
        target.passage_number = source.passage_number + 1
        target.last_passage_time = self.simulated_time
        target.vessel_capacity = target_capacity
        
        self.vessel_states[target_vessel] = target
        
        # Update source (or remove if fully passaged)
        if split_ratio >= 1.0:
            del self.vessel_states[source_vessel]
        else:
            source.cell_count = cells_transferred
            
        self._simulate_delay(2.0)
        
        logger.info(f"Passaged {source_vessel} -> {target_vessel} (1:{split_ratio})")
        
        return {
            "status": "success",
            "action": "passage",
            "cells_transferred": cells_transferred,
            "target_viability": new_viability,
            "passage_number": target.passage_number
        }
        
    def treat_with_compound(self, vessel_id: str, compound: str, dose_uM: float, **kwargs) -> Dict[str, Any]:
        """Simulate compound treatment and dose-response."""
        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return {"status": "error", "message": "Vessel not found"}
            
        vessel = self.vessel_states[vessel_id]
        
        # Get IC50 and hill slope from YAML database
        compound_data = self.compound_sensitivity.get(compound, {})
        ic50 = compound_data.get(vessel.cell_line, self.defaults.get("default_ic50", 1.0))
        hill_slope = compound_data.get("hill_slope", self.defaults.get("default_hill_slope", 1.0))
        
        # Apply dose-response model (4-parameter logistic)
        viability_effect = 1.0 / (1.0 + (dose_uM / ic50) ** hill_slope)
        
        # Add biological variability
        params = self.cell_line_params.get(vessel.cell_line, self.defaults)
        biological_cv = params.get("biological_cv", self.defaults.get("biological_cv", 0.05))
        viability_effect *= np.random.normal(1.0, biological_cv)
        viability_effect = np.clip(viability_effect, 0.0, 1.0)
        
        # Update vessel state
        vessel.viability *= viability_effect
        vessel.cell_count *= viability_effect
        vessel.compounds[compound] = dose_uM
        
        self._simulate_delay(0.5)
        
        logger.info(f"Treated {vessel_id} with {dose_uM}μM {compound} (viability: {vessel.viability:.2f})")
        
        return {
            "status": "success",
            "action": "treat",
            "compound": compound,
            "dose_uM": dose_uM,
            "viability_effect": viability_effect,
            "current_viability": vessel.viability,
            "ic50": ic50,
            "hill_slope": hill_slope
        }
        
    def incubate(self, duration_seconds: float, temperature_c: float, **kwargs) -> Dict[str, Any]:
        """Simulate incubation with cell growth."""
        hours = duration_seconds / 3600.0
        
        # Advance time for all vessels
        self.advance_time(hours)
        
        # Fast-forward simulation time
        self._simulate_delay(0.5)
        
        logger.info(f"Incubated for {hours:.1f}h at {temperature_c}°C (simulated time: {self.simulated_time:.1f}h)")
        
        return {
            "status": "success",
            "action": "incubate",
            "duration_h": hours,
            "simulated_time_h": self.simulated_time,
            "vessels_updated": len(self.vessel_states)
        }
        
    def get_vessel_state(self, vessel_id: str) -> Optional[Dict[str, Any]]:
        """Get current state of a vessel."""
        if vessel_id not in self.vessel_states:
            return None
            
        vessel = self.vessel_states[vessel_id]
        return {
            "vessel_id": vessel.vessel_id,
            "cell_line": vessel.cell_line,
            "cell_count": vessel.cell_count,
            "viability": vessel.viability,
            "confluence": vessel.confluence,
            "passage_number": vessel.passage_number,
            "compounds": vessel.compounds
        }
    
    def simulate_cellrox_signal(self, vessel_id: str, compound: str, dose_uM: float) -> float:
        """
        Simulate CellROX oxidative stress signal.
        
        Uses a Hill equation to model ROS-dependent fluorescence increase.
        
        Args:
            vessel_id: Vessel identifier
            compound: Compound name (e.g., "tbhp")
            dose_uM: Compound concentration in µM
            
        Returns:
            CellROX fluorescence signal (arbitrary units)
        """
        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return 0.0
        
        vessel = self.vessel_states[vessel_id]
        cell_line = vessel.cell_line
        
        # Get CellROX parameters from YAML (nested under compound)
        cellrox_params = None
        if compound in self.compound_sensitivity:
            # Check if we have the full YAML data with cellrox_params
            if hasattr(self, 'raw_yaml_data'):
                compound_data = self.raw_yaml_data.get('compound_sensitivity', {}).get(compound, {})
                cellrox_params = compound_data.get('cellrox_params', {}).get(cell_line, {})
        
        # Fallback to defaults if not found
        if not cellrox_params:
            logger.warning(f"No CellROX params for {compound} + {cell_line}, using defaults")
            cellrox_params = {
                'ec50_uM': 50.0,
                'max_fold': 5.0,
                'baseline': 100.0,
                'hill_slope': 1.8
            }
        
        ec50 = cellrox_params.get('ec50_uM', 50.0)
        max_fold = cellrox_params.get('max_fold', 5.0)
        baseline = cellrox_params.get('baseline', 100.0)
        hill_slope = cellrox_params.get('hill_slope', 1.8)
        
        # Hill equation for signal increase
        # signal = baseline * (1 + (max_fold - 1) * dose^h / (EC50^h + dose^h))
        if dose_uM <= 0:
            signal = baseline
        else:
            fold_increase = (dose_uM ** hill_slope) / (ec50 ** hill_slope + dose_uM ** hill_slope)
            signal = baseline * (1.0 + (max_fold - 1.0) * fold_increase)
        
        # Add biological noise
        cv = self.cell_line_params.get(cell_line, {}).get('biological_cv', 0.05)
        noise = np.random.normal(1.0, cv)
        signal *= noise
        
        return max(0.0, signal)
    
    def simulate_segmentation_quality(self, vessel_id: str, compound: str, dose_uM: float) -> float:
        """
        Simulate cell segmentation quality.
        
        High doses of oxidative stress cause cell rounding and death,
        reducing segmentation quality.
        
        Args:
            vessel_id: Vessel identifier
            compound: Compound name (e.g., "tbhp")
            dose_uM: Compound concentration in µM
            
        Returns:
            Segmentation quality (0.0 to 1.0, where 1.0 is perfect)
        """
        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return 0.0
        
        vessel = self.vessel_states[vessel_id]
        cell_line = vessel.cell_line
        
        # Get segmentation parameters from YAML (nested under compound)
        seg_params = None
        if compound in self.compound_sensitivity:
            # Check if we have the full YAML data with segmentation_params
            if hasattr(self, 'raw_yaml_data'):
                compound_data = self.raw_yaml_data.get('compound_sensitivity', {}).get(compound, {})
                seg_params = compound_data.get('segmentation_params', {}).get(cell_line, {})
        
        # Fallback to defaults if not found
        if not seg_params:
            logger.warning(f"No segmentation params for {compound} + {cell_line}, using defaults")
            seg_params = {
                'degradation_ic50_uM': 200.0,
                'min_quality': 0.3,
                'hill_slope': 2.5
            }
        
        degradation_ic50 = seg_params.get('degradation_ic50_uM', 200.0)
        min_quality = seg_params.get('min_quality', 0.3)
        hill_slope = seg_params.get('hill_slope', 2.5)
        
        # Inverse Hill equation for quality degradation
        # quality = min_quality + (1 - min_quality) * IC50^h / (IC50^h + dose^h)
        if dose_uM <= 0:
            quality = 1.0
        else:
            degradation_factor = (degradation_ic50 ** hill_slope) / (degradation_ic50 ** hill_slope + dose_uM ** hill_slope)
            quality = min_quality + (1.0 - min_quality) * degradation_factor
        
        # Also factor in viability (dead cells are hard to segment)
        quality *= vessel.viability
        
        # Add noise
        cv = 0.05  # 5% CV for segmentation quality
        noise = np.random.normal(1.0, cv)
        quality *= noise
        
        return np.clip(quality, 0.0, 1.0)
    
    def _load_raw_yaml_for_nested_params(self, params_file: Optional[str] = None):
        """Load raw YAML data to access nested parameters."""
        if params_file is None:
            params_file = "data/simulation_parameters.yaml"

        yaml_path = Path(params_file)
        if not yaml_path.exists():
            logger.warning(f"YAML file not found: {params_file}")
            return

        with open(yaml_path, 'r') as f:
            self.raw_yaml_data = yaml.safe_load(f)

    def _load_cell_thalamus_params(self):
        """Load Cell Thalamus parameters for morphology simulation."""
        thalamus_params_file = Path(__file__).parent.parent.parent.parent / "data" / "cell_thalamus_params.yaml"

        if not thalamus_params_file.exists():
            logger.warning(f"Cell Thalamus params not found: {thalamus_params_file}")
            self.thalamus_params = None
            return

        with open(thalamus_params_file, 'r') as f:
            self.thalamus_params = yaml.safe_load(f)

        logger.info("Loaded Cell Thalamus parameters")

    def cell_painting_assay(self, vessel_id: str, **kwargs) -> Dict[str, Any]:
        """
        Simulate Cell Painting morphology assay.

        Returns 5-channel morphology features:
        - ER (endoplasmic reticulum)
        - Mito (mitochondria)
        - Nucleus (nuclear morphology)
        - Actin (cytoskeleton)
        - RNA (translation sites)

        Args:
            vessel_id: Vessel identifier
            **kwargs: Additional parameters (plate_id, day, operator for technical noise)

        Returns:
            Dict with channel values and metadata
        """
        # Lazy load thalamus params
        if not hasattr(self, 'thalamus_params') or self.thalamus_params is None:
            self._load_cell_thalamus_params()

        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return {"status": "error", "message": "Vessel not found"}

        vessel = self.vessel_states[vessel_id]
        cell_line = vessel.cell_line

        # Get baseline morphology for this cell line
        baseline = self.thalamus_params['baseline_morphology'].get(cell_line, {})
        if not baseline:
            logger.warning(f"No baseline morphology for {cell_line}, using A549")
            baseline = self.thalamus_params['baseline_morphology']['A549']

        # Start with baseline
        morph = {
            'er': baseline['er'],
            'mito': baseline['mito'],
            'nucleus': baseline['nucleus'],
            'actin': baseline['actin'],
            'rna': baseline['rna']
        }

        # Apply compound effects via stress axes
        for compound_name, dose_uM in vessel.compounds.items():
            if dose_uM == 0:
                continue

            # Look up compound params
            compound_params = self.thalamus_params['compounds'].get(compound_name, {})
            if not compound_params:
                logger.warning(f"Unknown compound for morphology: {compound_name}")
                continue

            stress_axis = compound_params['stress_axis']
            intensity = compound_params['intensity']
            ec50 = compound_params['ec50_uM']
            hill_slope = compound_params['hill_slope']

            # Get stress axis channel effects
            axis_effects = self.thalamus_params['stress_axes'][stress_axis]['channels']

            # Calculate dose response (Hill equation)
            # Effect ranges from 0 (no dose) to intensity (saturating dose)
            dose_effect = intensity * (dose_uM ** hill_slope) / (ec50 ** hill_slope + dose_uM ** hill_slope)

            # Apply to each channel
            for channel, axis_strength in axis_effects.items():
                # Channel response = baseline * (1 + dose_effect * axis_strength)
                # Positive axis_strength increases signal, negative decreases
                morph[channel] *= (1.0 + dose_effect * axis_strength)

        # Apply viability effect (dead cells have reduced signal)
        viability_factor = 0.3 + 0.7 * vessel.viability  # Dead cells retain 30% signal
        for channel in morph:
            morph[channel] *= viability_factor

        # Add biological noise
        bio_cv = self.thalamus_params['biological_noise']['cell_line_cv']
        for channel in morph:
            morph[channel] *= np.random.normal(1.0, bio_cv)

        # Add technical noise (plate, day, operator effects)
        tech_noise = self.thalamus_params['technical_noise']
        plate_cv = tech_noise['plate_cv']
        day_cv = tech_noise['day_cv']
        operator_cv = tech_noise['operator_cv']
        well_cv = tech_noise['well_cv']

        # Apply technical factors
        plate_factor = np.random.normal(1.0, plate_cv)
        day_factor = np.random.normal(1.0, day_cv)
        operator_factor = np.random.normal(1.0, operator_cv)
        well_factor = np.random.normal(1.0, well_cv)

        total_tech_factor = plate_factor * day_factor * operator_factor * well_factor

        for channel in morph:
            morph[channel] *= total_tech_factor
            morph[channel] = max(0.0, morph[channel])  # No negative signals

        self._simulate_delay(2.0)  # Imaging takes time

        return {
            "status": "success",
            "action": "cell_painting",
            "vessel_id": vessel_id,
            "cell_line": cell_line,
            "morphology": morph,
            "viability": vessel.viability,
            "timestamp": datetime.now().isoformat()
        }

    def atp_viability_assay(self, vessel_id: str, **kwargs) -> Dict[str, Any]:
        """
        Simulate LDH cytotoxicity assay (orthogonal scalar readout).

        LDH (lactate dehydrogenase) release measures membrane integrity - only rises
        when cells die and membranes rupture. Orthogonal to Cell Painting morphology.

        Key advantages over ATP:
        - Not confounded by mitochondrial dysfunction (CCCP, oligomycin crash ATP but may not kill cells)
        - True cytotoxicity measurement (membrane rupture = cell death)
        - Orthogonal to Cell Painting (supernatant biochemistry vs cellular morphology)

        LDH signal is INVERSELY proportional to viability:
        - High viability (0.95) → Low LDH (from 5% dead cells)
        - Low viability (0.30) → High LDH (from 70% dead cells)

        Args:
            vessel_id: Vessel identifier
            **kwargs: Additional parameters (plate_id, day, operator for technical noise)

        Returns:
            Dict with LDH signal and metadata
        """
        # Lazy load thalamus params
        if not hasattr(self, 'thalamus_params') or self.thalamus_params is None:
            self._load_cell_thalamus_params()

        if vessel_id not in self.vessel_states:
            logger.warning(f"Vessel {vessel_id} not found")
            return {"status": "error", "message": "Vessel not found"}

        vessel = self.vessel_states[vessel_id]
        cell_line = vessel.cell_line

        # Get baseline LDH for this cell line
        # LDH is released by dead/dying cells (inverse of ATP)
        baseline_ldh = self.thalamus_params['baseline_atp'].get(cell_line, 50000.0)  # Keep same param name for backward compat

        # LDH scales with ORIGINAL cell count and DEATH (inverse of viability)
        # High viability (0.95) = low LDH (from 5% dead cells)
        # Low viability (0.30) = high LDH (from 70% dead cells)

        # IMPORTANT: Reconstruct original cell count before death
        # treat_with_compound reduces cell_count proportionally to viability,
        # but LDH is released from ALL dead cells (which remain in well initially)
        if vessel.viability > 0:
            original_cell_count = vessel.cell_count / vessel.viability
        else:
            original_cell_count = vessel.cell_count  # All dead

        cell_count_factor = original_cell_count / 1e6  # Normalize to 1M cells
        death_factor = 1.0 - vessel.viability  # Inverse of viability

        # LDH signal proportional to dead/dying cells
        ldh_signal = baseline_ldh * cell_count_factor * death_factor

        # Add biological noise
        bio_cv = self.thalamus_params['biological_noise']['cell_line_cv']
        ldh_signal *= np.random.normal(1.0, bio_cv)

        # Add technical noise
        tech_noise = self.thalamus_params['technical_noise']
        plate_cv = tech_noise['plate_cv']
        day_cv = tech_noise['day_cv']
        operator_cv = tech_noise['operator_cv']
        well_cv = tech_noise['well_cv']

        plate_factor = np.random.normal(1.0, plate_cv)
        day_factor = np.random.normal(1.0, day_cv)
        operator_factor = np.random.normal(1.0, operator_cv)
        well_factor = np.random.normal(1.0, well_cv)

        total_tech_factor = plate_factor * day_factor * operator_factor * well_factor
        ldh_signal *= total_tech_factor
        ldh_signal = max(0.0, ldh_signal)

        self._simulate_delay(0.5)  # LDH assay is quick

        return {
            "status": "success",
            "action": "ldh_viability",
            "vessel_id": vessel_id,
            "cell_line": cell_line,
            "ldh_signal": ldh_signal,
            "atp_signal": ldh_signal,  # Keep for backward compatibility
            "viability": vessel.viability,
            "cell_count": vessel.cell_count,
            "timestamp": datetime.now().isoformat()
        }
