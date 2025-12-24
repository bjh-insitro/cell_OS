"""
Tripwire Tests: Enforcing STATE_MAP.md

These tests enforce the world model contract specified in STATE_MAP.md.
They are designed to fail loudly if the implementation diverges from the specification.

Test Categories:
1. test_no_truth_leak.py: Verifies no ground truth leakage to agent
2. test_concentration_spine_consistency.py: Verifies concentration/volume consistency
3. test_measurement_purity.py: Verifies measurements don't mutate state

These tests run on every commit (CI enforcement).
"""
