"""
Protocol Resolver for Cell Culture Operations.

Resolves abstract protocol templates to concrete unit operations by binding
logical reagent roles and volume keys to cell-line-specific parameters.
"""

from typing import List, Dict, Any, Optional
import yaml
from pathlib import Path

from cell_os.unit_ops.base import UnitOp, VesselLibrary
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.inventory import Inventory
from cell_os.protocol_templates import PASSAGE_T75_TEMPLATE, PASSAGE_T25_TEMPLATE


class ProtocolResolver:
    """
    Resolves abstract protocol templates to concrete unit operations.
    
    Binds:
    - Reagent roles (growth_media, wash_buffer, detach_reagent) to concrete reagent IDs
    - Volume keys (wash_1, collect_1, etc.) to actual volumes in mL
    - Incubation keys to temperature and time parameters
    """
    
    def __init__(
        self,
        cell_lines_yaml: str = "data/cell_lines.yaml",
        vessels: Optional[VesselLibrary] = None,
        inventory: Optional[Inventory] = None
    ):
        """
        Initialize protocol resolver.
        
        Args:
            cell_lines_yaml: Path to cell line configuration YAML
            vessels: VesselLibrary instance (creates new if None)
            inventory: Inventory instance (creates new if None)
        """
        self.cell_lines = self._load_cell_lines(cell_lines_yaml)
        self.vessels = vessels or VesselLibrary()
        self.inventory = inventory or Inventory(pricing_path="data/raw/pricing.yaml")
        
        # Initialize ParametricOps for consistent UnitOp creation
        self.ops = ParametricOps(self.vessels, self.inventory)
    
    def _load_cell_lines(self, yaml_path: str) -> Dict[str, Any]:
        """Load cell line configurations from YAML."""
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"Cell lines config not found: {yaml_path}")
        
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        return data.get('cell_lines', {})
    
    def resolve_passage_protocol(self, cell_line_name: str, vessel_type: str) -> List[UnitOp]:
        """
        Resolve passaging protocol for a specific cell line and vessel type.
        
        Args:
            cell_line_name: Cell line identifier (e.g., "iPSC", "HEK293")
            vessel_type: Vessel type identifier (e.g., "T75", "T25")
            
        Returns:
            List of concrete UnitOp instances with resolved parameters
        """
        if vessel_type == "T75":
            return self.resolve_passage_protocol_t75(cell_line_name)
        elif vessel_type == "T25":
            return self.resolve_passage_protocol_t25(cell_line_name)
        else:
            raise ValueError(f"Unsupported vessel type for passaging: {vessel_type}")

    def resolve_passage_protocol_t75(self, cell_line_name: str) -> List[UnitOp]:
        """Resolve T75 passaging protocol."""
        return self._resolve_protocol(cell_line_name, "T75", "flask_t75", PASSAGE_T75_TEMPLATE)

    def resolve_passage_protocol_t25(self, cell_line_name: str) -> List[UnitOp]:
        """Resolve T25 passaging protocol."""
        return self._resolve_protocol(cell_line_name, "T25", "flask_t25", PASSAGE_T25_TEMPLATE)

    def _resolve_protocol(
        self, 
        cell_line_name: str, 
        vessel_key: str, 
        vessel_id: str, 
        template: List[Dict[str, Any]]
    ) -> List[UnitOp]:
        """Internal helper to resolve a protocol from a template."""
        # Get cell line config
        if cell_line_name not in self.cell_lines:
            raise ValueError(f"Unknown cell line: {cell_line_name}")
        
        cell_config = self.cell_lines[cell_line_name]
        
        # Get vessel spec
        vessel = self.vessels.get(vessel_id)
        
        # Get passaging params
        if "passage" not in cell_config or vessel_key not in cell_config["passage"]:
            raise ValueError(f"No {vessel_key} passaging config for {cell_line_name}")
        
        passage_params = cell_config["passage"][vessel_key]
        
        # Inject reference_vessel if present in parent passage block
        if "reference_vessel" in cell_config["passage"]:
            passage_params = passage_params.copy()
            passage_params["reference_vessel"] = cell_config["passage"]["reference_vessel"]
        
        # Resolve each step in the template
        unit_ops = []
        for step in template:
            uo = self._instantiate_step(step, cell_config, passage_params, vessel_id)
            unit_ops.append(uo)
        
        return unit_ops
    
    def _instantiate_step(
        self,
        step: Dict[str, Any],
        cell_config: Dict[str, Any],
        passage_params: Dict[str, Any],
        vessel_id: str
    ) -> UnitOp:
        """
        Instantiate a single protocol step as a UnitOp using ParametricOps.
        """
        uo_type = step["uo"]
        
        # Resolve reagent role to concrete reagent ID
        reagent_id = None
        if "reagent_role" in step:
            role = step["reagent_role"]
            reagent_id = cell_config.get(role)
            if reagent_id is None:
                raise ValueError(f"Reagent role '{role}' not defined for cell line")
        
        # Resolve volume key to actual volume
        volume = None
        if "volume_key" in step:
            volume_key = step["volume_key"]
            vessel = self.vessels.get(vessel_id)
            volume = self._resolve_volume_ml(passage_params, vessel, volume_key)
        
        # Resolve incubation parameters
        temp_c = None
        minutes = None
        if "incubation_key" in step:
            incubation_key = step["incubation_key"]
            incubations = passage_params.get("incubation", {})
            if incubation_key not in incubations:
                raise ValueError(f"Incubation key '{incubation_key}' not defined in passage config")
            incubation = incubations[incubation_key]
            temp_c = incubation.get("temp_C")
            minutes = incubation.get("minutes")
        
        # Delegate to ParametricOps
        if uo_type == "aspirate":
            return self.ops.op_aspirate(vessel_id, volume)
        elif uo_type == "dispense":
            return self.ops.op_dispense(vessel_id, volume, reagent_id)
        elif uo_type == "incubate":
            return self.ops.op_incubate(vessel_id, minutes, temp_c)
        elif uo_type == "centrifuge":
            speed_g = step.get("speed_g", 300)
            minutes = step.get("minutes", 5)
            return self.ops.op_centrifuge(vessel_id, minutes, speed_g)
        elif uo_type == "count":
            method = step.get("method", "manual")
            volume = volume if volume else 0.1
            # op_count expects vessel_id, method, material_cost_usd
            # We let op_count handle defaults or pass explicit costs if needed
            # For now, we rely on op_count's internal logic
            return self.ops.op_count(vessel_id, method)
        else:
            raise ValueError(f"Unknown unit operation type: {uo_type}")

    def _resolve_volume_ml(self, passage_cfg: Dict[str, Any], vessel: Any, volume_key: str) -> float:
        """
        Resolve a volume in mL for a given step.
        
        Currently treats volumes_mL_reference as literal per-vessel volumes (no scaling).
        reference_vessel is ignored for now.
        """
        if volume_key == "working_volume":
            return vessel.working_volume_ml
            
        # 1. Check volumes_mL_absolute
        if "volumes_mL_absolute" in passage_cfg:
            if volume_key in passage_cfg["volumes_mL_absolute"]:
                return passage_cfg["volumes_mL_absolute"][volume_key]
        
        # 2. Check volumes_mL_reference as literal
        if "volumes_mL_reference" in passage_cfg:
            if volume_key in passage_cfg["volumes_mL_reference"]:
                return passage_cfg["volumes_mL_reference"][volume_key]
        
        # 3. Legacy fallback
        if "volumes_mL" in passage_cfg:
            if volume_key in passage_cfg["volumes_mL"]:
                return passage_cfg["volumes_mL"][volume_key]
        
        raise KeyError(f"Volume key '{volume_key}' not found in passage config")
