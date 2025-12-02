#!/usr/bin/env python3
"""
Quick test to verify BOM items are populated in workflow operations.
"""
import sys
sys.path.insert(0, 'src')

from cell_os.workflows.zombie_posh import build_zombie_posh_workflow
from cell_os.unit_ops.base import VesselLibrary
from cell_os.inventory import Inventory

# Initialize dependencies
vessel_lib = VesselLibrary()
inv = Inventory()

# Build a simple workflow
workflow = build_zombie_posh_workflow(
    cell_line="HeLa",
    vessel_lib=vessel_lib,
    pricing_inv=inv
)

# Check if BOM items are populated
print("=" * 60)
print("BOM TRACKING VERIFICATION")
print("=" * 60)

total_ops = 0
ops_with_items = 0
total_items = 0

def check_op(op, depth=0):
    global total_ops, ops_with_items, total_items
    total_ops += 1
    
    indent = "  " * depth
    has_items = hasattr(op, 'items') and len(op.items) > 0
    
    if has_items:
        ops_with_items += 1
        total_items += len(op.items)
        print(f"{indent}✓ {op.name}: {len(op.items)} BOM items")
        # Show first few items
        for item in op.items[:3]:
            print(f"{indent}  - {item.resource_id}: {item.quantity}")
        if len(op.items) > 3:
            print(f"{indent}  ... and {len(op.items) - 3} more")
    else:
        print(f"{indent}✗ {op.name}: No BOM items")
    
    # Recursively check sub-steps
    if hasattr(op, 'sub_steps'):
        for sub_op in op.sub_steps:
            check_op(sub_op, depth + 1)

# Check all operations in workflow
for op in workflow.operations:
    check_op(op)
    print()

print("=" * 60)
print(f"SUMMARY:")
print(f"  Total operations: {total_ops}")
print(f"  Operations with BOM items: {ops_with_items}")
print(f"  Coverage: {ops_with_items/total_ops*100:.1f}%")
print(f"  Total BOM items: {total_items}")
print("=" * 60)

# Verify we have good coverage
if ops_with_items / total_ops >= 0.5:
    print("✅ BOM tracking is working! Good coverage.")
    sys.exit(0)
else:
    print("⚠️  Low BOM coverage. Some operations may not be refactored yet.")
    sys.exit(1)
