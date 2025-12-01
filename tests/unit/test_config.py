"""
Test configuration management.
"""
import os
from unittest import mock
from cell_os.config.settings import CellOSSettings, defaults

def test_defaults():
    """Test default values are loaded correctly."""
    settings = CellOSSettings()
    assert settings.db_path == defaults.DEFAULT_DB_PATH
    assert settings.default_cell_line == "HEK293T"
    assert settings.use_virtual_hardware is True

def test_env_override():
    """Test environment variables override defaults."""
    with mock.patch.dict(os.environ, {
        "CELLOS_DEFAULT_CELL_LINE": "CHO-K1",
        "CELLOS_USE_VIRTUAL_HARDWARE": "false",
        "CELLOS_SIMULATION_DURATION_DAYS": "30"
    }):
        settings = CellOSSettings.load_from_env()
        assert settings.default_cell_line == "CHO-K1"
        assert settings.use_virtual_hardware is False
        assert settings.simulation_duration_days == 30

def test_load_yaml(tmp_path):
    """Test loading settings from YAML."""
    from cell_os.config.loader import load_settings_from_yaml
    
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
default_cell_line: "HeLa"
simulation_duration_days: 7
unknown_key: "should be ignored"
    """)
    
    settings = load_settings_from_yaml(str(config_file))
    assert settings.default_cell_line == "HeLa"
    assert settings.simulation_duration_days == 7
    # Should fall back to defaults for missing keys
    assert settings.use_virtual_hardware is True

