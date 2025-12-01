"""
Configuration settings using dataclasses.
"""
import os
from dataclasses import dataclass, field
from typing import Optional
from . import defaults

@dataclass
class CellOSSettings:
    """Central configuration for Cell OS."""
    
    # Database settings
    db_path: str = field(default=defaults.DEFAULT_DB_PATH)
    executions_db_path: str = field(default=defaults.DEFAULT_EXECUTIONS_DB_PATH)
    
    # Simulation settings
    default_cell_line: str = field(default=defaults.DEFAULT_CELL_LINE)
    simulation_duration_days: int = field(default=defaults.DEFAULT_SIMULATION_DURATION_DAYS)
    
    # Hardware settings
    use_virtual_hardware: bool = field(default=defaults.DEFAULT_USE_VIRTUAL_HARDWARE)
    
    # Paths
    data_dir: str = field(default=defaults.DATA_DIR)
    
    @classmethod
    def load_from_env(cls) -> 'CellOSSettings':
        """Load settings from environment variables."""
        return cls(
            db_path=os.getenv("CELLOS_DB_PATH", defaults.DEFAULT_DB_PATH),
            executions_db_path=os.getenv("CELLOS_EXECUTIONS_DB_PATH", defaults.DEFAULT_EXECUTIONS_DB_PATH),
            default_cell_line=os.getenv("CELLOS_DEFAULT_CELL_LINE", defaults.DEFAULT_CELL_LINE),
            simulation_duration_days=int(os.getenv("CELLOS_SIMULATION_DURATION_DAYS", defaults.DEFAULT_SIMULATION_DURATION_DAYS)),
            use_virtual_hardware=os.getenv("CELLOS_USE_VIRTUAL_HARDWARE", str(defaults.DEFAULT_USE_VIRTUAL_HARDWARE)).lower() == "true",
            data_dir=os.getenv("CELLOS_DATA_DIR", defaults.DATA_DIR)
        )

# Global settings instance
settings = CellOSSettings.load_from_env()
