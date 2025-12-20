"""
Integration test: Verify lognormal noise in biological_virtual.py preserves positivity.
"""

import sys
from src.cell_os.hardware.biological_virtual import BiologicalVirtualMachine


def test_measurement_noise_stays_positive():
    """Test that count_cells measurements stay positive."""
    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("test_well", "A549", 1e6)

    # Run 1000 measurements
    negative_count = 0
    for _ in range(1000):
        result = vm.count_cells("test_well")
        if result["count"] < 0 or result["viability"] < 0:
            negative_count += 1

    print(f"Negative measurements: {negative_count}/1000")
    if negative_count > 0:
        print("❌ FAIL: Found negative measurements")
        return False
    else:
        print("✓ PASS: All measurements positive")
        return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Lognormal Integration")
    print("=" * 70)
    print()

    passed = test_measurement_noise_stays_positive()

    print()
    print("=" * 70)
    print(f"Result: {'✓ PASS' if passed else '❌ FAIL'}")
    print("=" * 70)

    sys.exit(0 if passed else 1)
