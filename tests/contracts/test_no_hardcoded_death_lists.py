"""
Contract: No hardcoded death field lists allowed (AST meta-test).

This test scans the codebase AST for any literal list/set/tuple containing
"death_" strings that is NOT the canonical TRACKED_DEATH_FIELDS.

Why this matters:
- New death channels get added to TRACKED_DEATH_FIELDS
- If someone creates a new hardcoded list somewhere, it WILL get out of sync
- This catches the regression BEFORE it ships

Pattern: Surgical meta-test that prevents a specific bad pattern from landing.
"""

import ast
import sys
from pathlib import Path


def test_no_hardcoded_death_field_lists():
    """
    Scan biological_virtual.py for hardcoded death field lists.

    Fail if any literal collection contains "death_" strings and is not
    the TRACKED_DEATH_FIELDS definition itself.
    """
    # Find biological_virtual.py
    repo_root = Path(__file__).parent.parent.parent
    target_file = repo_root / "src" / "cell_os" / "hardware" / "biological_virtual.py"

    assert target_file.exists(), f"Cannot find {target_file}"

    with open(target_file, 'r') as f:
        source = f.read()

    tree = ast.parse(source, filename=str(target_file))

    violations = []

    class DeathFieldListScanner(ast.NodeVisitor):
        def visit_List(self, node):
            self._check_collection(node, "List")
            self.generic_visit(node)

        def visit_Set(self, node):
            self._check_collection(node, "Set")
            self.generic_visit(node)

        def visit_Tuple(self, node):
            self._check_collection(node, "Tuple")
            self.generic_visit(node)

        def visit_BinOp(self, node):
            """Catch TRACKED_DEATH_FIELDS | {...} or + (...) bypasses."""
            # Check if either operand is a literal collection with death_ strings
            if isinstance(node.op, (ast.BitOr, ast.Add)):
                self._check_binop_operands(node)
            self.generic_visit(node)

        def visit_Call(self, node):
            """Catch sorted([...death...]), sum([...death...]), etc."""
            # Check all arguments for literal collections with death_ strings
            for arg in node.args:
                if isinstance(arg, (ast.List, ast.Set, ast.Tuple)):
                    self._check_collection(arg, f"Call({self._get_func_name(node.func)})")
            self.generic_visit(node)

        def visit_ListComp(self, node):
            """Catch ["death_" + x for x in ...] comprehensions."""
            # Check if the comprehension builds death_ strings
            if self._comp_builds_death_strings(node):
                violations.append({
                    "line": node.lineno,
                    "kind": "ListComp",
                    "fields": ["<dynamic death_ construction>"]
                })
            self.generic_visit(node)

        def _get_func_name(self, node):
            """Extract function name for error messages."""
            if isinstance(node, ast.Name):
                return node.id
            elif isinstance(node, ast.Attribute):
                return node.attr
            return "unknown"

        def _check_binop_operands(self, node):
            """Check if binary op operands contain death_ collections."""
            for operand in [node.left, node.right]:
                if isinstance(operand, (ast.List, ast.Set, ast.Tuple)):
                    death_strings = self._extract_death_strings(operand)
                    if death_strings:
                        violations.append({
                            "line": node.lineno,
                            "kind": "BinOp",
                            "fields": death_strings
                        })

        def _comp_builds_death_strings(self, node):
            """Check if comprehension constructs death_ strings."""
            # Pattern: ["death_" + x for x in ...] or similar
            if isinstance(node.elt, ast.BinOp):
                if isinstance(node.elt.op, ast.Add):
                    # Check if either operand is "death_" string
                    for operand in [node.elt.left, node.elt.right]:
                        if isinstance(operand, ast.Constant):
                            if isinstance(operand.value, str) and "death_" in operand.value:
                                return True
            return False

        def _extract_death_strings(self, node):
            """Extract death_ strings from a collection node."""
            death_strings = []
            if hasattr(node, 'elts'):
                for elt in node.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        if elt.value.startswith("death_"):
                            death_strings.append(elt.value)
            return death_strings

        def _check_collection(self, node, kind):
            """Check if this collection contains death_ strings."""
            death_strings = self._extract_death_strings(node)

            # If we found death_ strings, this is a violation
            if death_strings:
                violations.append({
                    "line": node.lineno,
                    "kind": kind,
                    "fields": death_strings
                })

    scanner = DeathFieldListScanner()
    scanner.visit(tree)

    if violations:
        msg_lines = [
            "HARDCODED DEATH FIELD LISTS DETECTED (not allowed!):",
            "",
            "All death field lists must use TRACKED_DEATH_FIELDS from constants.py.",
            "Hardcoded lists WILL get out of sync when new channels are added.",
            "",
            "Violations found:"
        ]

        for v in violations:
            msg_lines.append(f"  Line {v['line']}: {v['kind']} with fields: {v['fields']}")

        msg_lines.extend([
            "",
            "Fix: Replace hardcoded list with:",
            "  for field in TRACKED_DEATH_FIELDS:",
            "      # your code here",
            "",
            "This ensures new death channels are automatically included."
        ])

        raise AssertionError("\n".join(msg_lines))


def test_constants_file_has_no_hardcoded_lists():
    """
    Scan constants.py - allow TRACKED_DEATH_FIELDS definition but nothing else.

    This is the one place where a hardcoded list is REQUIRED (the definition itself).
    But we still want to catch accidental duplicates.
    """
    repo_root = Path(__file__).parent.parent.parent
    target_file = repo_root / "src" / "cell_os" / "hardware" / "constants.py"

    assert target_file.exists(), f"Cannot find {target_file}"

    with open(target_file, 'r') as f:
        source = f.read()

    tree = ast.parse(source, filename=str(target_file))

    violations = []
    tracked_death_fields_line = None

    class DeathFieldListScanner(ast.NodeVisitor):
        def visit_Assign(self, node):
            """Check assignments for TRACKED_DEATH_FIELDS vs other death field lists."""
            nonlocal tracked_death_fields_line

            # Check if this is assigning to TRACKED_DEATH_FIELDS
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "TRACKED_DEATH_FIELDS":
                    tracked_death_fields_line = node.lineno
                    # This is the canonical definition - allow it
                    self.generic_visit(node)
                    return

            # Not TRACKED_DEATH_FIELDS - check if RHS contains death_ strings
            self._check_value(node.value, node.lineno)
            self.generic_visit(node)

        def _check_value(self, node, lineno):
            """Recursively check a node for death_ string collections."""
            if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
                death_strings = []
                for elt in node.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        if elt.value.startswith("death_"):
                            death_strings.append(elt.value)

                if death_strings:
                    violations.append({
                        "line": lineno,
                        "fields": death_strings
                    })
            elif isinstance(node, ast.Call):
                # Check frozenset() calls
                for arg in node.args:
                    self._check_value(arg, lineno)

    scanner = DeathFieldListScanner()
    scanner.visit(tree)

    if violations:
        msg_lines = [
            "DUPLICATE DEATH FIELD LISTS IN CONSTANTS.PY:",
            "",
            f"TRACKED_DEATH_FIELDS is defined at line {tracked_death_fields_line} (correct).",
            "But additional hardcoded death field lists were found:",
            ""
        ]

        for v in violations:
            msg_lines.append(f"  Line {v['line']}: {v['fields']}")

        msg_lines.extend([
            "",
            "There should be EXACTLY ONE death field list: TRACKED_DEATH_FIELDS.",
            "Remove the duplicates."
        ])

        raise AssertionError("\n".join(msg_lines))

    # Verify TRACKED_DEATH_FIELDS was actually found
    assert tracked_death_fields_line is not None, \
        "TRACKED_DEATH_FIELDS definition not found in constants.py"
