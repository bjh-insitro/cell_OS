"""
Default configuration values.
"""
import os

# Base paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Database defaults
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "inventory.db")
DEFAULT_EXECUTIONS_DB_PATH = os.path.join(DATA_DIR, "executions.db")

# Simulation defaults
DEFAULT_CELL_LINE = "HEK293T"
DEFAULT_SIMULATION_DURATION_DAYS = 14

# Hardware defaults
DEFAULT_USE_VIRTUAL_HARDWARE = True
