"""
Configuration loading utilities.
"""
import os
import yaml
from typing import Dict, Any, Optional
from .settings import CellOSSettings

def load_yaml_config(path: str) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    if not os.path.exists(path):
        return {}
    
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}

def load_settings_from_yaml(path: str) -> CellOSSettings:
    """Load CellOSSettings from a YAML file."""
    data = load_yaml_config(path)
    # Filter keys that match CellOSSettings fields
    # This is a simple implementation; Pydantic would do this automatically
    valid_keys = CellOSSettings.__annotations__.keys()
    filtered_data = {k: v for k, v in data.items() if k in valid_keys}
    
    # We need to handle defaults if not present in YAML
    # But CellOSSettings has defaults.
    # We can instantiate with **filtered_data
    return CellOSSettings(**filtered_data)
