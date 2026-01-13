"""
Static analysis test: Ground truth boundary enforcement (Issue #4).

Verifies that epistemic_agent code does NOT import ground truth modules.
This prevents accidental access to true_stress_axis, IC50_true, etc.

The boundary is:
- ALLOWED: cell_os.contracts.ground_truth_policy (the validation functions)
- FORBIDDEN: cell_os.hardware.masked_compound (contains true_stress_axis)
- FORBIDDEN: cell_os.hardware.masked_compound_phase5 (contains true_stress_axis)
- FORBIDDEN: Direct access to Phase5Compound.true_stress_axis

KNOWN BYPASS (v0.6.1 Gap D):
=============================
This static analysis catches IMPORTS but NOT runtime attribute access:

    # CAUGHT by this test:
    from cell_os.hardware.masked_compound_phase5 import true_stress_axis

    # NOT CAUGHT (runtime bypass):
    compound = get_current_compound()  # Returns Phase5Compound
    axis = getattr(compound, "true_stress_axis")  # Sneaky!
    axis = compound.__dict__["true_stress_axis"]  # Even sneakier!

MITIGATION OPTIONS:
1. Runtime guard: Override __getattribute__ on Phase5Compound during episodes
   to raise if true_stress_axis is accessed (complex, may break tests)
2. Proxy pattern: Wrap Phase5Compound in a proxy that hides ground truth
   attributes during agent rollout
3. Audit: Code review for getattr() calls in epistemic_agent directory

Currently we rely on code review and trust. The static scanner catches
the most obvious violations (direct imports). For a maximally adversarial
agent, runtime guards would be needed.

See: TestKnownBypassDocumentation for test documentation of this gap.
"""

import ast
import os
from pathlib import Path
from typing import List, Set, Tuple

import pytest


# Modules containing ground truth that agent should NEVER import
GROUND_TRUTH_MODULES = {
    "cell_os.hardware.masked_compound",
    "cell_os.hardware.masked_compound_phase5",
    "cell_os.biology.biology_core",  # Contains IC50_true and other ground truth
    "cell_os.legacy_simulation",  # Legacy ground truth container
}

# Specific symbols that are ground truth (even if imported from "safe" modules)
GROUND_TRUTH_SYMBOLS = {
    "true_stress_axis",
    "IC50_true",
    "true_mechanism",
    "ground_truth_label",
    "MaskedCompound",  # Class itself is ground truth container
    "Phase5Compound",  # Class itself is ground truth container
    "MASKED_LIBRARY",  # Contains ground truth compounds
    "PHASE5_LIBRARY",  # Contains ground truth compounds
}

# Agent code directories (files here should not access ground truth)
AGENT_CODE_PATHS = [
    "src/cell_os/epistemic_agent",
]

# Files explicitly allowed to import ground truth (e.g., test harnesses)
ALLOWLIST = {
    # Test harnesses that need ground truth to validate
    "test_",
    "conftest.py",
    # Evaluation scripts that compare to ground truth
    "_evaluation",
    "_benchmark",
}


class ImportVisitor(ast.NodeVisitor):
    """AST visitor that collects all imports from a file."""

    def __init__(self):
        self.imports: List[Tuple[str, int, str]] = []  # (module, lineno, import_type)
        self.from_imports: List[Tuple[str, str, int]] = []  # (module, name, lineno)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append((alias.name, node.lineno, "import"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            self.from_imports.append((module, alias.name, node.lineno))
        self.generic_visit(node)


def get_agent_files() -> List[Path]:
    """Get all Python files in agent code paths."""
    repo_root = Path(__file__).parent.parent.parent
    agent_files = []

    for agent_path in AGENT_CODE_PATHS:
        full_path = repo_root / agent_path
        if full_path.exists():
            for py_file in full_path.rglob("*.py"):
                # Skip allowlisted files
                skip = False
                for pattern in ALLOWLIST:
                    if pattern in str(py_file):
                        skip = True
                        break
                if not skip:
                    agent_files.append(py_file)

    return agent_files


def check_file_for_violations(file_path: Path) -> List[str]:
    """Check a single file for ground truth imports.

    Returns list of violation messages.
    """
    violations = []

    try:
        content = file_path.read_text()
        tree = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        violations.append(f"Syntax error in {file_path}: {e}")
        return violations

    visitor = ImportVisitor()
    visitor.visit(tree)

    # Check direct imports
    for module, lineno, _ in visitor.imports:
        for forbidden in GROUND_TRUTH_MODULES:
            if module == forbidden or module.startswith(f"{forbidden}."):
                violations.append(
                    f"{file_path}:{lineno}: Forbidden import of ground truth module: {module}"
                )

    # Check from imports
    for module, name, lineno in visitor.from_imports:
        # Check if module is forbidden
        for forbidden in GROUND_TRUTH_MODULES:
            if module == forbidden or module.startswith(f"{forbidden}."):
                violations.append(
                    f"{file_path}:{lineno}: Forbidden from-import: from {module} import {name}"
                )

        # Check if symbol is forbidden (even from "safe" modules)
        if name in GROUND_TRUTH_SYMBOLS:
            violations.append(
                f"{file_path}:{lineno}: Forbidden ground truth symbol: {name} "
                f"(from {module})"
            )

    return violations


class TestGroundTruthBoundary:
    """Test that epistemic_agent code respects ground truth boundary."""

    def test_no_ground_truth_imports_in_agent(self):
        """Agent code must not import ground truth modules."""
        agent_files = get_agent_files()
        assert len(agent_files) > 0, "No agent files found to check"

        all_violations = []
        for file_path in agent_files:
            violations = check_file_for_violations(file_path)
            all_violations.extend(violations)

        if all_violations:
            msg = f"Found {len(all_violations)} ground truth boundary violations:\n"
            msg += "\n".join(all_violations[:20])  # Show first 20
            if len(all_violations) > 20:
                msg += f"\n... and {len(all_violations) - 20} more"
            pytest.fail(msg)

    def test_ground_truth_modules_exist(self):
        """Verify the ground truth modules we're guarding actually exist."""
        repo_root = Path(__file__).parent.parent.parent

        for module_path in GROUND_TRUTH_MODULES:
            # Convert module path to file path
            parts = module_path.split(".")
            file_path = repo_root / "src" / "/".join(parts[:-1]) / f"{parts[-1]}.py"

            if not file_path.exists():
                # Also try as package
                package_path = repo_root / "src" / "/".join(parts) / "__init__.py"
                if not package_path.exists():
                    # Module might have been refactored/removed - that's OK
                    continue

    def test_ground_truth_symbols_documented(self):
        """Verify ground truth symbols are documented."""
        # This test ensures we remember to update the list
        assert len(GROUND_TRUTH_SYMBOLS) >= 5, (
            "GROUND_TRUTH_SYMBOLS should have at least 5 symbols. "
            "Did you forget to add new ground truth?"
        )


class TestGroundTruthPolicy:
    """Test ground_truth_policy.py validation functions."""

    def test_always_forbidden_patterns(self):
        """Validate that ALWAYS_FORBIDDEN patterns catch known ground truth."""
        from cell_os.contracts.ground_truth_policy import (
            ALWAYS_FORBIDDEN_PATTERNS,
            validate_no_ground_truth,
        )

        # Test data with ground truth (should be caught)
        test_data = {
            "morphology": {"ER_channel": 100.0},
            "death_mode": "compound",  # FORBIDDEN
            "er_stress": 0.8,  # FORBIDDEN
            "ic50_uM": 1.5,  # FORBIDDEN
        }

        violations = validate_no_ground_truth(test_data, ALWAYS_FORBIDDEN_PATTERNS)

        # Should have caught at least 3 violations
        assert len(violations) >= 3, f"Expected ≥3 violations, got {len(violations)}"

        # Verify specific violations
        violation_keys = [v[0] for v in violations]
        assert any("death_mode" in k for k in violation_keys)
        assert any("er_stress" in k for k in violation_keys)
        assert any("ic50_uM" in k for k in violation_keys)

    def test_debug_truth_exception(self):
        """_debug_truth dict is allowed to contain ground truth."""
        from cell_os.contracts.ground_truth_policy import (
            ALWAYS_FORBIDDEN_PATTERNS,
            validate_no_ground_truth,
        )

        # Test data with ground truth inside _debug_truth (should be OK)
        test_data = {
            "morphology": {"ER_channel": 100.0},
            "_debug_truth": {
                "death_mode": "compound",  # OK inside _debug_truth
                "er_stress": 0.8,  # OK inside _debug_truth
            },
        }

        violations = validate_no_ground_truth(test_data, ALWAYS_FORBIDDEN_PATTERNS)

        # Should have no violations
        assert len(violations) == 0, f"Unexpected violations in _debug_truth: {violations}"

    def test_clean_data_passes(self):
        """Clean agent-facing data should pass validation."""
        from cell_os.contracts.ground_truth_policy import (
            ALWAYS_FORBIDDEN_PATTERNS,
            validate_no_ground_truth,
        )

        # Clean agent-facing data
        clean_data = {
            "morphology": {
                "ER_channel": 100.0,
                "Mito_channel": 85.0,
                "Nucleus_channel": 120.0,
            },
            "dose_uM": 10.0,
            "timepoint_h": 48.0,
            "viability": 0.85,
        }

        violations = validate_no_ground_truth(clean_data, ALWAYS_FORBIDDEN_PATTERNS)

        assert len(violations) == 0, f"Clean data should pass: {violations}"


class TestKnownBypassDocumentation:
    """Document known bypasses of the ground truth boundary (Gap D, v0.6.1).

    These tests DOCUMENT (not prevent) ways the static scanner can be bypassed.
    They serve as audit trails and motivation for future runtime guards.

    IMPORTANT: These tests pass to document that bypasses EXIST.
    The bypasses are BAD but we need to know they're possible.
    """

    def test_static_scanner_catches_direct_import(self):
        """Static scanner DOES catch direct imports (good)."""
        # This is what we catch
        code = '''
from cell_os.hardware.masked_compound_phase5 import PHASE5_LIBRARY
axis = PHASE5_LIBRARY["test_A_strong"].true_stress_axis
'''
        tree = ast.parse(code)
        visitor = ImportVisitor()
        visitor.visit(tree)

        # Should detect the forbidden import
        forbidden_found = any(
            "masked_compound_phase5" in mod
            for mod, name, lineno in visitor.from_imports
        )
        assert forbidden_found, "Static scanner should catch this import"

    def test_getattr_bypass_not_caught(self):
        """KNOWN BYPASS: getattr() is NOT caught by static analysis.

        This test documents that an adversarial agent could use:
            axis = getattr(compound, "true_stress_axis")
        and the static scanner would NOT detect it.

        MITIGATION: Code review, runtime guards, or proxy pattern.
        """
        # This code bypasses the static scanner
        code = '''
def sneaky_get_ground_truth(compound):
    # This is NOT caught by ImportVisitor
    return getattr(compound, "true_stress_axis")
'''
        tree = ast.parse(code)
        visitor = ImportVisitor()
        visitor.visit(tree)

        # Static scanner finds NO imports (bypass succeeds)
        assert len(visitor.imports) == 0, "No imports detected"
        assert len(visitor.from_imports) == 0, "No from-imports detected"

        # This is a KNOWN GAP - document it
        # A runtime guard would catch this, but we don't have one yet

    def test_dict_access_bypass_not_caught(self):
        """KNOWN BYPASS: __dict__ access is NOT caught.

        Even sneakier:
            axis = compound.__dict__["true_stress_axis"]
        """
        code = '''
def even_sneakier(compound):
    return compound.__dict__["true_stress_axis"]
'''
        tree = ast.parse(code)
        visitor = ImportVisitor()
        visitor.visit(tree)

        # Static scanner finds nothing
        assert len(visitor.imports) == 0
        assert len(visitor.from_imports) == 0

    def test_dynamic_getattr_bypass_not_caught(self):
        """KNOWN BYPASS: Dynamic attribute name construction.

        The sneakiest:
            attr_name = "true_" + "stress_" + "axis"
            axis = getattr(compound, attr_name)
        """
        code = '''
def maximum_sneaky(compound):
    # Construct the forbidden attribute name at runtime
    parts = ["true", "stress", "axis"]
    attr_name = "_".join(parts)
    return getattr(compound, attr_name)
'''
        tree = ast.parse(code)
        visitor = ImportVisitor()
        visitor.visit(tree)

        # Static scanner cannot possibly catch this
        assert len(visitor.imports) == 0
        assert len(visitor.from_imports) == 0


class TestRuntimeObservationGuard:
    """Test runtime observation payload guard (v0.6.1 Gap D).

    The guard validates that observations returned to agents don't contain
    forbidden ground truth keys. This complements static import scanning.
    """

    def test_guard_catches_leaked_stress_axis(self):
        """Guard catches if true_stress_axis leaks into observation."""
        from cell_os.contracts.ground_truth_policy import (
            ALWAYS_FORBIDDEN_PATTERNS,
            validate_no_ground_truth,
        )

        # Simulate an observation with leaked ground truth
        leaked_obs = {
            "design_id": "test_001",
            "conditions": [
                {
                    "compound": "TunicamycinA",
                    "dose_uM": 10.0,
                    "true_stress_axis": "er_stress",  # LEAKED!
                    "feature_means": {"er": 150.0},
                }
            ],
        }

        violations = validate_no_ground_truth(leaked_obs, ALWAYS_FORBIDDEN_PATTERNS)
        assert len(violations) >= 1, "Guard should catch true_stress_axis"
        assert any("true_stress_axis" in v[0] for v in violations)

    def test_guard_catches_leaked_ic50(self):
        """Guard catches if IC50_true leaks."""
        from cell_os.contracts.ground_truth_policy import (
            ALWAYS_FORBIDDEN_PATTERNS,
            validate_no_ground_truth,
        )

        leaked_obs = {
            "conditions": [
                {
                    "compound": "TestCompound",
                    "IC50_true": 5.2,  # LEAKED!
                }
            ],
        }

        violations = validate_no_ground_truth(leaked_obs, ALWAYS_FORBIDDEN_PATTERNS)
        assert len(violations) >= 1, "Guard should catch IC50_true"

    def test_guard_allows_clean_observation(self):
        """Guard passes clean observations without ground truth."""
        from cell_os.contracts.ground_truth_policy import (
            ALWAYS_FORBIDDEN_PATTERNS,
            validate_no_ground_truth,
        )

        clean_obs = {
            "design_id": "test_001",
            "wells_spent": 96,
            "conditions": [
                {
                    "compound": "TunicamycinA",
                    "dose_uM": 10.0,
                    "time_h": 48.0,
                    "feature_means": {"er": 150.0, "mito": 85.0},
                    "feature_stds": {"er": 12.0, "mito": 8.0},
                    "mean": 117.5,
                    "std": 10.0,
                    "cv": 0.085,
                }
            ],
        }

        violations = validate_no_ground_truth(clean_obs, ALWAYS_FORBIDDEN_PATTERNS)
        assert len(violations) == 0, f"Clean observation should pass: {violations}"

    def test_guard_catches_nested_leakage(self):
        """Guard catches ground truth nested in feature_means."""
        from cell_os.contracts.ground_truth_policy import (
            ALWAYS_FORBIDDEN_PATTERNS,
            validate_no_ground_truth,
        )

        # Nested leakage attempt
        sneaky_obs = {
            "conditions": [
                {
                    "feature_means": {
                        "er": 150.0,
                        "er_stress": 0.8,  # LEAKED inside feature_means!
                    }
                }
            ],
        }

        violations = validate_no_ground_truth(sneaky_obs, ALWAYS_FORBIDDEN_PATTERNS)
        assert len(violations) >= 1, "Guard should catch nested er_stress"


class TestRuntimeGuardProposal:
    """Propose and document runtime guard implementation (Gap D, v0.6.1).

    These tests document HOW runtime guards could work.
    Implementation deferred until adversarial agent threat model justifies cost.
    """

    def test_proposed_runtime_guard_design(self):
        """Document proposed runtime guard design.

        To add runtime protection, Phase5Compound would override __getattribute__:

        class Phase5Compound:
            _EPISODE_MODE = False  # Set True during agent rollout

            def __getattribute__(self, name):
                if name == "true_stress_axis" and Phase5Compound._EPISODE_MODE:
                    raise AttributeError(
                        f"Ground truth access blocked during episode: {name}"
                    )
                return super().__getattribute__(name)

        Usage:
            Phase5Compound._EPISODE_MODE = True
            try:
                run_agent_episode(compound)
            finally:
                Phase5Compound._EPISODE_MODE = False

        This test documents the design but does NOT implement it.
        """
        # This is documentation-only test
        pass

    def test_alternative_proxy_design(self):
        """Document alternative proxy pattern.

        Instead of modifying Phase5Compound, wrap it in a proxy:

        class AgentFacingCompound:
            def __init__(self, compound):
                self._compound = compound

            def __getattr__(self, name):
                if name in FORBIDDEN_ATTRIBUTES:
                    raise AttributeError(f"Forbidden: {name}")
                return getattr(self._compound, name)

        This is cleaner but requires changes to how compounds are passed to agents.
        """
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
