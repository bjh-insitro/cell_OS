"""
Test Database Migration

Tests that BiologicalVirtualMachine can load parameters from database.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def main():
    print("=" * 80)
    print("Testing Database Migration")
    print("=" * 80)
    print()

    # Test 1: Create VM with database loading enabled
    print("Test 1: Create VM with use_database=True")
    print("-" * 80)
    try:
        vm = BiologicalVirtualMachine(use_database=True)
        print("✅ VM created successfully")
        print(f"   Cell lines loaded: {len(vm.cell_line_params)}")
        print(f"   Compounds loaded: {len(vm.compound_sensitivity)}")
        print()
    except Exception as e:
        print(f"❌ Failed to create VM: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 2: Check cell line parameters
    print("Test 2: Cell Line Parameters")
    print("-" * 80)
    for cell_line_id in ['A549', 'HepG2', 'Jurkat', 'CHO', 'iPSC']:
        if cell_line_id in vm.cell_line_params:
            params = vm.cell_line_params[cell_line_id]
            print(f"✅ {cell_line_id:15s}: dt={params.get('doubling_time_h')}h, "
                  f"conf={params.get('max_confluence')}, "
                  f"eff={params.get('seeding_efficiency')}")
        else:
            print(f"⚠️  {cell_line_id}: Not found in database")
    print()

    # Test 3: Check compound sensitivity
    print("Test 3: Compound Sensitivity")
    print("-" * 80)
    test_compounds = ['staurosporine', 'doxorubicin', 'paclitaxel']
    for compound in test_compounds:
        if compound in vm.compound_sensitivity:
            data = vm.compound_sensitivity[compound]
            cell_lines = [k for k in data.keys() if k != 'hill_slope']
            print(f"✅ {compound:20s}: {len(cell_lines)} cell lines, "
                  f"Hill={data.get('hill_slope', 'N/A')}")
            # Show a few IC50s
            for cell_line in list(cell_lines)[:3]:
                ic50 = data[cell_line]
                print(f"   {cell_line:15s}: IC50 = {ic50} µM")
        else:
            print(f"⚠️  {compound}: Not found")
    print()

    # Test 4: Verify vs YAML
    print("Test 4: Compare Database vs YAML")
    print("-" * 80)
    print("Creating second VM with YAML fallback...")
    vm_yaml = BiologicalVirtualMachine(use_database=False)
    print(f"Database: {len(vm.cell_line_params)} cell lines")
    print(f"YAML: {len(vm_yaml.cell_line_params)} cell lines")
    print()

    # Check for differences
    for cell_line in set(vm.cell_line_params.keys()) | set(vm_yaml.cell_line_params.keys()):
        db_dt = vm.cell_line_params.get(cell_line, {}).get('doubling_time_h')
        yaml_dt = vm_yaml.cell_line_params.get(cell_line, {}).get('doubling_time_h')

        if db_dt and yaml_dt:
            if db_dt == yaml_dt:
                print(f"✅ {cell_line:15s}: {db_dt}h (match)")
            else:
                print(f"⚠️  {cell_line:15s}: DB={db_dt}h, YAML={yaml_dt}h (differ)")
        elif db_dt:
            print(f"🆕 {cell_line:15s}: {db_dt}h (only in database)")
        elif yaml_dt:
            print(f"📄 {cell_line:15s}: {yaml_dt}h (only in YAML)")
    print()

    # Test 5: Test seeding
    print("Test 5: Test Seeding with Database")
    print("-" * 80)
    seeding_worked = False
    try:
        vm.seed_vessel(
            vessel_id="test_well",
            cell_line="A549",
            vessel_type="384-well",
            density_level="NOMINAL"
        )
        # Check if vessel was created (use internal dict)
        if hasattr(vm, '_vessels') and "test_well" in vm._vessels:
            vessel = vm._vessels["test_well"]
            seeding_worked = True
            print(f"✅ Seeded A549 in 384-well")
            print(f"   Initial count: {vessel.count:.0f} cells")
            print(f"   Doubling time: {vessel.doubling_time}h")
            print(f"   Max confluence: {vessel.max_confluence}")
        else:
            print(f"⚠️  Seeding completed but vessel not found in _vessels")
        print()
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        # Don't print full traceback, just the error
        print()

    print("=" * 80)
    print("✅ Database Migration Test Complete")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"  - Database loading: {'✅ Working' if len(vm.cell_line_params) > 0 else '❌ Failed'}")
    print(f"  - Cell lines: {len(vm.cell_line_params)}")
    print(f"  - Compounds: {len(vm.compound_sensitivity)}")
    print(f"  - Seeding: {'✅ Working' if seeding_worked else '❌ Failed'}")


if __name__ == "__main__":
    main()
