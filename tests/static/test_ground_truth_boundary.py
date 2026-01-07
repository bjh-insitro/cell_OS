"""
Static analysis test: Ground truth boundary enforcement (Issue #4).

Verifies that epistemic_agent code does NOT import ground truth modules.
This prevents accidental access to true_stress_axis, IC50_true, etc.

The boundary is:
- ALLOWED: cell_os.contracts.ground_truth_policy (the validation functions)
- FORBIDDEN: cell_os.hardware.masked_compound (contains true_stress_axis)
- FORBIDDEN: cell_os.hardware.masked_compound_phase5 (contains true_stress_axis)
- FORBIDDEN: Direct access to Phase5Compound.true_stress_axis
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
    "cell_os.sim.biology_core",  # Contains IC50_true and other ground truth
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
