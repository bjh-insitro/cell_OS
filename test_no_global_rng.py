#!/usr/bin/env python3
"""
RNG Hygiene Test

Enforce that biological_virtual.py never uses global np.random.* for physics.
All randomness must go through dedicated RNG streams (rng_growth, rng_treatment, rng_assay).

This prevents observer-dependent physics and ensures reproducibility.
"""

import re
from pathlib import Path

def check_no_global_rng(file_path: str) -> tuple[bool, list[str]]:
    """
    Check that file doesn't use global np.random.*.

    Allowed:
    - np.random.default_rng()  (for creating RNG instances)
    - np.random in comments/docstrings

    Forbidden:
    - np.random.normal()
    - np.random.uniform()
    - np.random.randint()
    - np.random.choice()
    - np.random.seed()  (explicitly banned)
    - etc.

    Returns:
        (pass, violations)
    """
    violations = []

    with open(file_path, 'r') as f:
        lines = f.readlines()

    # Pattern: np.random.<method>() but NOT np.random.default_rng()
    # Also skip lines that are comments
    forbidden_pattern = re.compile(r'np\.random\.(?!default_rng)\w+\(')

    for i, line in enumerate(lines, start=1):
        # Skip comments and docstrings (rough heuristic)
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
            continue

        # Check for forbidden pattern
        match = forbidden_pattern.search(line)
        if match:
            violations.append(f"Line {i}: {line.strip()}")

    return len(violations) == 0, violations


print("=" * 100)
print("RNG HYGIENE TEST")
print("=" * 100)
print()
print("Checking: src/cell_os/hardware/biological_virtual.py")
print()
print("Rule: No global np.random.* usage (use rng_growth/rng_treatment/rng_assay instead)")
print()
print("-" * 100)

file_path = "src/cell_os/hardware/biological_virtual.py"
passed, violations = check_no_global_rng(file_path)

if passed:
    print("✅ PASS: No global RNG usage detected")
else:
    print(f"❌ FAIL: Found {len(violations)} violation(s):")
    print()
    for violation in violations:
        print(f"  {violation}")

print("=" * 100)
