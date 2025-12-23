"""
Unit tests for deterministic design_id generation (Phase 5 insurance).

These tests prevent someone from "helpfully" reintroducing UUIDs later.
"""

import re
import ast
from pathlib import Path

from cell_os.epistemic_agent.agent.policy_rules import deterministic_design_id, design_hash


def test_deterministic_design_id_is_reproducible():
    """
    Assert deterministic_design_id() produces same output on same inputs.

    This is the core insurance: if someone breaks determinism, test screams.
    """
    # Same inputs → same output
    spec = {"n_reps": 12}
    id1 = deterministic_design_id("baseline", cycle=1, spec=spec)
    id2 = deterministic_design_id("baseline", cycle=1, spec=spec)
    assert id1 == id2, f"Non-deterministic! {id1} != {id2}"

    # Different inputs → different output
    id3 = deterministic_design_id("baseline", cycle=2, spec=spec)
    assert id1 != id3, "Different cycles should produce different IDs"

    id4 = deterministic_design_id("edge_test", cycle=1, spec=spec)
    assert id1 != id4, "Different templates should produce different IDs"


def test_design_id_does_not_look_like_uuid():
    """
    Assert design_id format is NOT UUID-shaped (prevents UUID reintroduction).

    UUID format: 8-4-4-4-12 hex digits (e.g., "550e8400-e29b-41d4-a716-446655440000")
    Our format: "template_c0001_12hexdigits" (e.g., "baseline_c0001_a1b2c3d4e5f6")
    """
    spec = {"n_reps": 12}
    design_id = deterministic_design_id("baseline", cycle=1, spec=spec)

    # Assert format is "template_cNNNN_hexhash" not UUID
    pattern = r'^[a-z_]+_c\d{4}_[0-9a-f]{12}$'
    assert re.match(pattern, design_id), \
        f"design_id format wrong: {design_id} (should be 'template_cNNNN_hexhash')"

    # Assert it's NOT UUID-shaped (8-4-4-4-12 pattern with dashes)
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    assert not re.match(uuid_pattern, design_id), \
        f"design_id looks like UUID! {design_id}"


def test_design_id_includes_all_meaningful_inputs():
    """
    Assert design_id changes when any meaningful input changes.

    Ensures we're actually hashing the design content, not just the template name.
    """
    spec1 = {"n_reps": 12}
    base = deterministic_design_id("baseline", cycle=1, spec=spec1)

    # Changing cycle should change ID
    cycle2 = deterministic_design_id("baseline", cycle=2, spec=spec1)
    assert base != cycle2, "Cycle change should affect design_id"

    # Changing spec should change ID
    spec2 = {"n_reps": 24}
    spec_change = deterministic_design_id("baseline", cycle=1, spec=spec2)
    assert base != spec_change, "Spec change should affect design_id"

    # Changing template should change ID
    template2 = deterministic_design_id("edge_test", cycle=1, spec=spec1)
    assert base != template2, "Template change should affect design_id"


def test_policy_rules_never_imports_uuid():
    """
    Assert policy_rules.py does NOT import uuid module (prevents regression).

    This is the strongest insurance: if uuid import returns, test fails loudly.
    """
    policy_rules_path = Path(__file__).parent.parent.parent / "src" / "cell_os" / "epistemic_agent" / "agent" / "policy_rules.py"

    with open(policy_rules_path, 'r', encoding='utf-8') as f:
        source = f.read()

    # Parse AST to find all imports
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend([alias.name for alias in node.names])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    # Assert 'uuid' is NOT imported
    assert 'uuid' not in imports, \
        "❌ REGRESSION: policy_rules.py imports 'uuid' module! " \
        "This breaks determinism. Use deterministic_design_id() instead."

    # Also check for string pattern "import uuid" in case AST misses something
    assert 'import uuid' not in source, \
        "❌ REGRESSION: Found 'import uuid' in policy_rules.py source"


def test_design_id_collision_resistance():
    """
    Assert design_id has low collision probability for typical inputs.

    12 hex digits = 48 bits = ~281 trillion combinations.
    For realistic agent runs (< 1000 cycles), collision probability is negligible.
    """
    # Generate 3000 different design IDs (covers typical agent run)
    ids = set()
    spec = {"n_reps": 12}
    for cycle in range(1, 1001):
        for template in ["baseline", "edge_test", "dose_ladder"]:
            design_id = deterministic_design_id(template, cycle, spec=spec)
            ids.add(design_id)

    # Assert no collisions in 3000 IDs
    # (If we saw collisions here, we'd need more bits)
    assert len(ids) == 3000, \
        f"Collision detected! Expected 3000 unique IDs, got {len(ids)}"


def test_design_hash_stable_serialization():
    """
    Assert design_hash is stable across dict order, float formatting, sets, etc.

    This is the core stability guarantee that prevents determinism regressions.
    """
    # Dict order shouldn't matter
    spec1 = {"n_reps": 12, "compound": "tBHQ", "dose_uM": 1.0}
    spec2 = {"compound": "tBHQ", "dose_uM": 1.0, "n_reps": 12}
    h1 = design_hash("baseline", spec1)
    h2 = design_hash("baseline", spec2)
    assert h1 == h2, f"Dict order affected hash! {h1} != {h2}"

    # Float representation should be stable
    spec3 = {"dose_uM": 1.0}
    spec4 = {"dose_uM": 1.00000000000}
    h3 = design_hash("baseline", spec3)
    h4 = design_hash("baseline", spec4)
    assert h3 == h4, f"Float representation affected hash! {h3} != {h4}"

    # List order should matter (deterministic)
    spec5 = {"doses": [0.01, 0.1, 1.0]}
    spec6 = {"doses": [1.0, 0.1, 0.01]}
    h5 = design_hash("baseline", spec5)
    h6 = design_hash("baseline", spec6)
    assert h5 != h6, "List order should affect hash (it's meaningful)"

    # Set order shouldn't matter (sorted internally)
    spec7 = {"compounds": {"tBHQ", "DMSO", "Paclitaxel"}}
    spec8 = {"compounds": {"Paclitaxel", "DMSO", "tBHQ"}}
    h7 = design_hash("baseline", spec7)
    h8 = design_hash("baseline", spec8)
    assert h7 == h8, f"Set order affected hash! {h7} != {h8}"


def test_design_id_separates_content_from_cycle():
    """
    Assert design_id format separates content hash from cycle.

    Same content in different cycles → different IDs (includes cycle).
    Same content in same cycle → same ID (idempotent).
    """
    spec = {"n_reps": 12}

    # Same spec, same cycle → same ID
    id1 = deterministic_design_id("baseline", cycle=1, spec=spec)
    id2 = deterministic_design_id("baseline", cycle=1, spec=spec)
    assert id1 == id2, "Same spec + cycle should give same ID"

    # Same spec, different cycle → different ID (cycle in output)
    id3 = deterministic_design_id("baseline", cycle=5, spec=spec)
    assert id1 != id3, "Different cycle should give different ID"
    assert "_c0001_" in id1, "ID should contain cycle c0001"
    assert "_c0005_" in id3, "ID should contain cycle c0005"

    # Different spec, same cycle → different ID (content hash differs)
    spec2 = {"n_reps": 24}
    id4 = deterministic_design_id("baseline", cycle=1, spec=spec2)
    assert id1 != id4, "Different spec should give different ID"


def test_design_hash_edge_cases():
    """
    Assert design_hash handles tricky edge cases (floating point, mixed types).

    This is the "cheap insurance" test: if canonicalization breaks, this screams.
    """
    # Floating point rounding edge case (0.1 + 0.2 != 0.3 in binary)
    # Our normalize should make these equivalent if they print the same
    spec1 = {"dose": 0.3}
    spec2 = {"dose": 0.1 + 0.2}  # Slightly different in binary
    h1 = design_hash("test", spec1)
    h2 = design_hash("test", spec2)
    # Both should normalize to same representation
    assert h1 == h2, f"Floating point rounding affected hash! {h1} != {h2}"

    # Mixed types in same spec (dict, list, set, float)
    spec_complex = {
        "compounds": {"DMSO", "tBHQ"},  # Set
        "doses": [0.1, 1.0, 10.0],      # List
        "meta": {"cell_line": "A549"},  # Nested dict
        "dose_uM": 1.0,                 # Float
    }
    # Should be reproducible across multiple calls
    h3 = design_hash("test", spec_complex)
    h4 = design_hash("test", spec_complex)
    assert h3 == h4, "Complex spec not reproducible!"

    # Reordered set should give same hash
    spec_complex2 = {
        "compounds": {"tBHQ", "DMSO"},  # Different set order
        "doses": [0.1, 1.0, 10.0],
        "meta": {"cell_line": "A549"},
        "dose_uM": 1.0,
    }
    h5 = design_hash("test", spec_complex2)
    assert h3 == h5, f"Set order affected hash! {h3} != {h5}"


def test_deterministic_design_id_assertions():
    """
    Assert design_id raises on invalid inputs (cheap insurance against misuse).
    """
    spec = {"n_reps": 12}

    # cycle must be int
    try:
        deterministic_design_id("baseline", cycle=1.5, spec=spec)
        assert False, "Should have raised on non-int cycle"
    except AssertionError as e:
        assert "cycle must be int" in str(e)

    # hash_len must be >= 8
    try:
        deterministic_design_id("baseline", cycle=1, spec=spec, hash_len=4)
        assert False, "Should have raised on hash_len < 8"
    except AssertionError as e:
        assert "hash_len must be >= 8" in str(e)


def test_design_id_exact_format_locked():
    """
    Lock down the exact format string shape (tripwire for log parsing, dashboards, tooling).

    Format contract: {template}_c{cycle:04d}_{hash}
    - template: snake_case (lowercase letters + underscores, NO DIGITS)
    - cycle: exactly 4 digits, zero-padded
    - hash: exactly hash_len hex digits (default 12)

    Template naming governance:
    - MUST use snake_case: baseline, dose_ladder, scrna_probe
    - NO digits allowed: "cp_screen_v2" is FORBIDDEN (use template_version instead)
    - NO camelCase: "scrnaProbe" is FORBIDDEN (use scrna_probe)
    - NO dashes: "cp-screen" is FORBIDDEN (use cp_screen)

    This is intentional. If you need versioning, use template_version parameter.
    If someone "cleans this up" later, test screams and forces discussion.
    """
    spec = {"n_reps": 12}

    # Test default hash_len=12
    id_default = deterministic_design_id("baseline", cycle=5, spec=spec)
    pattern_default = r'^[a-z_]+_c\d{4}_[0-9a-f]{12}$'
    assert re.match(pattern_default, id_default), \
        f"\nDesign ID format violated! Got: {id_default}\n" \
        f"Expected pattern: {pattern_default}\n\n" \
        f"Template naming governance: snake_case only (lowercase + underscores)\n" \
        f"  ✅ Allowed: baseline, dose_ladder, scrna_probe\n" \
        f"  ❌ Forbidden: cp-screen-v2, scrnaProbe, cpScreen2\n\n" \
        f"This format is load-bearing for log parsing and dashboards.\n" \
        f"If you need versioning, use template_version parameter."

    # Verify cycle is zero-padded to 4 digits
    assert "_c0005_" in id_default, f"Cycle not zero-padded: {id_default}"

    # Test custom hash_len (verify hash_len actually controls suffix)
    id_short = deterministic_design_id("baseline", cycle=5, spec=spec, hash_len=8)
    pattern_short = r'^[a-z_]+_c\d{4}_[0-9a-f]{8}$'
    assert re.match(pattern_short, id_short), \
        f"Custom hash_len=8 format violated! Got: {id_short}"

    id_long = deterministic_design_id("baseline", cycle=5, spec=spec, hash_len=16)
    pattern_long = r'^[a-z_]+_c\d{4}_[0-9a-f]{16}$'
    assert re.match(pattern_long, id_long), \
        f"Custom hash_len=16 format violated! Got: {id_long}"

    # Verify hash_len actually changes the hash suffix (not just truncation)
    assert len(id_short.split('_')[-1]) == 8, "hash_len=8 didn't produce 8-char hash"
    assert len(id_long.split('_')[-1]) == 16, "hash_len=16 didn't produce 16-char hash"


def test_hash_schema_version_stability():
    """
    Assert hash_schema version is baked into hash (prevents cross-version confusion).

    If normalization semantics change (float formatting, dict ordering, etc.),
    bump hash_schema in design_hash() and this test will document the change.
    """
    spec = {"n_reps": 12}

    # Generate hash with current schema
    h1 = design_hash("baseline", spec)

    # If someone changes hash_schema from "v1" to "v2", all hashes change
    # This test locks down that we're currently on v1
    # (Future: if you bump to v2, update this test and document why)

    # Verify current hash is stable (regression test)
    # This specific hash is for {"hash_schema":"v1","spec":{"n_reps":12},"template":"baseline","template_version":1}
    expected_hash = "88d15c028c0b"
    assert h1 == expected_hash, \
        f"\n{'='*70}\n" \
        f"HASH STABILITY CONTRACT VIOLATED\n" \
        f"{'='*70}\n" \
        f"Expected hash: {expected_hash}\n" \
        f"Got hash:      {h1}\n\n" \
        f"This is a LOAD-BEARING CONTRACT. If you changed:\n" \
        f"  - hash_schema (policy_rules.py line 62)\n" \
        f"  - _normalize_for_hash() semantics\n" \
        f"  - Float formatting, dict ordering, or set handling\n\n" \
        f"Then this failure is EXPECTED and INTENTIONAL.\n\n" \
        f"TO FIX:\n" \
        f"  1. Update expected_hash in this test to: {h1}\n" \
        f"  2. Add a comment explaining WHY you changed it:\n" \
        f"     # Changed 2025-12-23: Bumped hash_schema to v2 because [reason]\n" \
        f"  3. Coordinate with anyone using old hashes (logs, dashboards, etc.)\n" \
        f"{'='*70}\n"


if __name__ == "__main__":
    # Run tests manually for quick validation
    test_deterministic_design_id_is_reproducible()
    print("✅ test_deterministic_design_id_is_reproducible")

    test_design_id_does_not_look_like_uuid()
    print("✅ test_design_id_does_not_look_like_uuid")

    test_design_id_includes_all_meaningful_inputs()
    print("✅ test_design_id_includes_all_meaningful_inputs")

    test_policy_rules_never_imports_uuid()
    print("✅ test_policy_rules_never_imports_uuid")

    test_design_id_collision_resistance()
    print("✅ test_design_id_collision_resistance")

    test_design_hash_stable_serialization()
    print("✅ test_design_hash_stable_serialization")

    test_design_id_separates_content_from_cycle()
    print("✅ test_design_id_separates_content_from_cycle")

    test_design_hash_edge_cases()
    print("✅ test_design_hash_edge_cases")

    test_deterministic_design_id_assertions()
    print("✅ test_deterministic_design_id_assertions")

    test_design_id_exact_format_locked()
    print("✅ test_design_id_exact_format_locked")

    test_hash_schema_version_stability()
    print("✅ test_hash_schema_version_stability")

    print("\n✅ All tripwire tests passed")
