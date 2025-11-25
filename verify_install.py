#!/usr/bin/env python
"""
Verify that cell_OS is properly installed and imports work.

Run this after: pip install -e .

Expected output:
  ✓ All imports successful
  ✓ cell_OS version: 0.1.0
"""

import sys

def test_imports():
    """Test that all core modules can be imported."""
    print("Testing imports...")
    
    try:
        # Test basic imports
        import cell_os
        print(f"✓ cell_os package found (version {cell_os.__version__})")
        
        # Test core modules
        from cell_os.lab_world_model import LabWorldModel, Campaign
        print("✓ lab_world_model imports")
        
        from cell_os.posteriors import DoseResponsePosterior, SliceKey
        print("✓ posteriors imports")
        
        from cell_os.modeling import DoseResponseGP
        print("✓ modeling imports")
        
        from cell_os.acquisition import AcquisitionFunction
        print("✓ acquisition imports")
        
        from cell_os.campaign import PotencyGoal, SelectivityGoal
        print("✓ campaign imports")
        
        print("\n✅ All imports successful!")
        print(f"✅ cell_OS version: {cell_os.__version__}")
        return True
        
    except ImportError as e:
        print(f"\n❌ Import failed: {e}")
        print("\nMake sure you've run: pip install -e .")
        return False

def test_basic_functionality():
    """Test that basic functionality works."""
    print("\nTesting basic functionality...")
    
    try:
        from cell_os.lab_world_model import LabWorldModel
        from cell_os.posteriors import SliceKey
        
        # Create empty world model
        wm = LabWorldModel.empty()
        print("✓ Can create LabWorldModel")
        
        # Create SliceKey
        key = SliceKey("A549", "Drug1", 24.0, "viability")
        print(f"✓ Can create SliceKey: {key}")
        
        print("\n✅ Basic functionality works!")
        return True
        
    except Exception as e:
        print(f"\n❌ Functionality test failed: {e}")
        return False

if __name__ == "__main__":
    imports_ok = test_imports()
    
    if imports_ok:
        func_ok = test_basic_functionality()
        sys.exit(0 if func_ok else 1)
    else:
        sys.exit(1)
