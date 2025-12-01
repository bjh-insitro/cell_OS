"""
Protocol Resolver for Cell Culture Operations.

Resolves abstract protocol templates to concrete unit operations by binding
logical reagent roles and volume keys to cell-line-specific parameters.
"""

from typing import List, Dict, Any, Optional
from types import SimpleNamespace

from cell_os.unit_ops.base import UnitOp, VesselLibrary
from cell_os.unit_ops.parametric import ParametricOps
from cell_os.inventory import Inventory
from cell_os.protocol_templates import PASSAGE_T75_TEMPLATE, PASSAGE_T25_TEMPLATE
from cell_os.cell_line_config import CellLineConfigStore


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
        inventory: Optional[Inventory] = None,
        cell_lines_db: str = "data/cell_lines.db",
    ):
        """
        Initialize protocol resolver.
        
        Args:
            cell_lines_yaml: Path to cell line configuration YAML (if exists)
            vessels: VesselLibrary instance (creates new if None)
            inventory: Inventory instance (creates new if None)
            cell_lines_db: Path to SQLite database (used when YAML is absent)
        """
        self.config_store = CellLineConfigStore(cell_lines_yaml, cell_lines_db)
        self.vessels = vessels or VesselLibrary()
        self.inventory = inventory or Inventory()  # Loads from database by default
        
        # Initialize ParametricOps for consistent UnitOp creation
        self.ops = ParametricOps(self.vessels, self.inventory)
        self.ops.resolver = self
    
    def get_cell_line_profile(self, cell_line: str) -> Optional[SimpleNamespace]:
        """
        Get cell line profile from YAML configuration.
        Returns an object with attributes matching the profile fields.
        """
        try:
            cfg = self.config_store.get_config(cell_line)
        except ValueError:
            return None
        profile = cfg.get("profile")
        if not profile:
            return None
        return SimpleNamespace(**profile)
    
    def _scale_volumes(self, volumes: Dict[str, float], from_vessel_id: str, to_vessel_id: str, scaling_method: str = "working_volume") -> Dict[str, float]:
        """
        Scale volumes from one vessel to another based on vessel properties.
        
        Args:
            volumes: Dictionary of volume values to scale
            from_vessel_id: Source vessel ID (e.g., "flask_t75")
            to_vessel_id: Target vessel ID (e.g., "flask_t25")
            scaling_method: "working_volume" or "surface_area"
            
        Returns:
            Dictionary with scaled volumes
        """
        from_vessel = self.vessels.get(from_vessel_id)
        to_vessel = self.vessels.get(to_vessel_id)
        
        # Calculate scaling factor
        if scaling_method == "surface_area":
            if hasattr(from_vessel, 'surface_area_cm2') and hasattr(to_vessel, 'surface_area_cm2'):
                scale_factor = to_vessel.surface_area_cm2 / from_vessel.surface_area_cm2
            else:
                # Fallback to working volume if surface area not available
                scale_factor = to_vessel.working_volume_ml / from_vessel.working_volume_ml
        else:  # working_volume
            scale_factor = to_vessel.working_volume_ml / from_vessel.working_volume_ml
        
        # Scale all volumes
        scaled = {}
        for key, value in volumes.items():
            if isinstance(value, (int, float)):
                scaled[key] = round(value * scale_factor, 1)
            else:
                scaled[key] = value
        
        return scaled
    
    def get_thaw_config(self, cell_line: str, vessel_id: str) -> Dict[str, Any]:
        """
        Get thaw configuration for a specific cell line and vessel.
        
        Args:
            cell_line: Cell line identifier (e.g., "iPSC", "HEK293")
            vessel_id: Vessel identifier (e.g., "flask_t75")
            
        Returns:
            Dictionary with thaw configuration including volumes, media, coating info
        """
        cell_config = self.config_store.get_config(cell_line)
        profile = self.get_cell_line_profile(cell_line)
        vessel = self.vessels.get(vessel_id)
        
        # Infer vessel type from vessel_id
        parts = vessel_id.split('_')
        if len(parts) > 1 and parts[0] == "flask":
            vessel_type = parts[1].upper()
        else:
            vessel_type = parts[-1].upper()
        
        # Get thaw config with fallback to reference vessel
        thaw_config = {}
        reference_vessel_type = None
        needs_scaling = False
        
        if "thaw" in cell_config:
            thaw_cfg = cell_config["thaw"]
            if vessel_type in thaw_cfg:
                # Exact match found
                thaw_config = thaw_cfg[vessel_type].copy()
            elif "reference_vessel" in thaw_cfg and thaw_cfg["reference_vessel"] in thaw_cfg:
                # Use reference vessel and scale
                reference_vessel_type = thaw_cfg["reference_vessel"]
                thaw_config = thaw_cfg[reference_vessel_type].copy()
                needs_scaling = True
        
        # Scale volumes if needed
        if needs_scaling and reference_vessel_type and "volumes_mL" in thaw_config:
            ref_vessel_id = f"flask_{reference_vessel_type.lower()}"
            thaw_config["volumes_mL"] = self._scale_volumes(
                thaw_config["volumes_mL"],
                ref_vessel_id,
                vessel_id,
                scaling_method="working_volume"
            )
        
        # Fill in defaults from profile
        config = {
            "coating_required": thaw_config.get("coating_required", getattr(profile, "coating_required", False) if profile else False),
            "coating_reagent": thaw_config.get("coating_reagent", getattr(profile, "coating_reagent", "laminin_521") if profile else "laminin_521"),
            "media": cell_config.get("growth_media", "mtesr_plus_kit"),
            "volumes_mL": thaw_config.get("volumes_mL", {
                "media_aliquot": 40.0,
                "pre_warm": vessel.working_volume_ml,
                "wash_aliquot": 5.0,
                "wash_vial": 1.0,
                "resuspend": 1.0,
                "transfer": 1.0
            })
        }
        
        return config
    
    def get_feed_config(self, cell_line: str, vessel_id: str) -> Dict[str, Any]:
        """
        Get feed configuration for a specific cell line and vessel.
        
        Args:
            cell_line: Cell line identifier (e.g., "iPSC", "HEK293")
            vessel_id: Vessel identifier (e.g., "flask_t75")
            
        Returns:
            Dictionary with feed configuration including volume, media, schedule
        """
        cell_config = self.config_store.get_config(cell_line)
        vessel = self.vessels.get(vessel_id)
        
        # Infer vessel type from vessel_id
        parts = vessel_id.split('_')
        if len(parts) > 1 and parts[0] == "flask":
            vessel_type = parts[1].upper()
        else:
            vessel_type = parts[-1].upper()
        
        # Get feed config with fallback to reference vessel
        feed_config = {}
        reference_vessel_type = None
        needs_scaling = False
        
        if "feed" in cell_config:
            feed_cfg = cell_config["feed"]
            if vessel_type in feed_cfg:
                # Exact match found
                feed_config = feed_cfg[vessel_type].copy()
            elif "reference_vessel" in feed_cfg and feed_cfg["reference_vessel"] in feed_cfg:
                # Use reference vessel and scale
                reference_vessel_type = feed_cfg["reference_vessel"]
                feed_config = feed_cfg[reference_vessel_type].copy()
                needs_scaling = True
        
        # Scale volume if needed
        if needs_scaling and reference_vessel_type and "volume_ml" in feed_config:
            ref_vessel_id = f"flask_{reference_vessel_type.lower()}"
            ref_vessel = self.vessels.get(ref_vessel_id)
            scale_factor = vessel.working_volume_ml / ref_vessel.working_volume_ml
            feed_config["volume_ml"] = round(feed_config["volume_ml"] * scale_factor, 1)
        
        # Fill in defaults
        config = {
            "media": feed_config.get("media", cell_config.get("growth_media", "mtesr_plus_kit")),
            "volume_ml": feed_config.get("volume_ml", vessel.working_volume_ml),
            "schedule": feed_config.get("schedule", {"interval_days": 1})
        }
        
        return config

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
            # Try generic resolution using T75 template structure
            vessel_id = f"flask_{vessel_type.lower()}"
            # Note: We use T75 template as the generic structure for now
            return self._resolve_protocol(cell_line_name, vessel_type, vessel_id, PASSAGE_T75_TEMPLATE)

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
        cell_config = self.config_store.get_config(cell_line_name)
        
        # Get vessel spec
        vessel = self.vessels.get(vessel_id)
        
        # Get passaging params
        if "passage" not in cell_config:
            raise ValueError(f"No passaging config for {cell_line_name}")
            
        passage_config = cell_config["passage"]
        enable_scaling = False
        
        if vessel_key in passage_config:
            passage_params = passage_config[vessel_key]
        elif "reference_vessel" in passage_config:
            # Fallback to reference vessel
            ref_vessel_name = passage_config["reference_vessel"]
            if ref_vessel_name not in passage_config:
                raise ValueError(f"Reference vessel {ref_vessel_name} config not found")
            passage_params = passage_config[ref_vessel_name]
            enable_scaling = True
        else:
            raise ValueError(f"No {vessel_key} passaging config for {cell_line_name}")
        
        # Inject reference_vessel if present in parent passage block
        if "reference_vessel" in passage_config:
            passage_params = passage_params.copy()
            passage_params["reference_vessel"] = passage_config["reference_vessel"]
        
        # Resolve each step in the template
        unit_ops = []
        for step in template:
            uo = self._instantiate_step(step, cell_config, passage_params, vessel_id, enable_scaling)
            unit_ops.append(uo)
        
        return unit_ops
    
    def _instantiate_step(
        self,
        step: Dict[str, Any],
        cell_config: Dict[str, Any],
        passage_params: Dict[str, Any],
        vessel_id: str,
        enable_scaling: bool = False
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
            volume = self._resolve_volume_ml(passage_params, vessel, volume_key, enable_scaling)
        
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

    def _resolve_volume_ml(
        self, 
        passage_cfg: Dict[str, Any], 
        vessel: Any, 
        volume_key: str,
        enable_scaling: bool = False
    ) -> float:
        """
        Resolve a volume in mL for a given step.
        
        If enable_scaling is True, scales volumes_mL_reference based on vessel size relative to reference.
        Otherwise, treats volumes_mL_reference as literal.
        """
        if volume_key == "working_volume":
            return vessel.working_volume_ml
            
        # 1. Check volumes_mL_absolute
        if "volumes_mL_absolute" in passage_cfg:
            if volume_key in passage_cfg["volumes_mL_absolute"]:
                return passage_cfg["volumes_mL_absolute"][volume_key]
        
        # 2. Check volumes_mL_reference
        if "volumes_mL_reference" in passage_cfg:
            if volume_key in passage_cfg["volumes_mL_reference"]:
                vol = passage_cfg["volumes_mL_reference"][volume_key]
                
                if enable_scaling and "reference_vessel" in passage_cfg:
                    ref_vessel_name = passage_cfg["reference_vessel"]
                    ref_vessel_id = f"flask_{ref_vessel_name.lower()}"
                    try:
                        ref_vessel = self.vessels.get(ref_vessel_id)
                        scale = vessel.working_volume_ml / ref_vessel.working_volume_ml
                        return vol * scale
                    except ValueError:
                        pass # Fallback to literal if ref vessel not found
                
                return vol
        
        # 3. Legacy fallback
        if "volumes_mL" in passage_cfg:
            if volume_key in passage_cfg["volumes_mL"]:
                return passage_cfg["volumes_mL"][volume_key]
        
        raise KeyError(f"Volume key '{volume_key}' not found in passage config")
