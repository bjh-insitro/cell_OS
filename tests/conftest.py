"""
Pytest configuration for cell_OS tests.
"""
import sys
import os

# Add src directory to Python path so tests can import cell_os modules
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
sys.path.insert(0, src_path)
