"""
Contracts enforcing continuous heterogeneity (no discrete subpops).

These tests MUST fail initially and turn green after deletion.
"""

import pytest
import inspect
import ast
import textwrap


def test_vessel_state_has_no_subpopulations_field():
    """VesselState must not have 'subpopulations' in default mode."""
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]

    assert not hasattr(vessel, 'subpopulations'), \
        "FAIL: VesselState still has 'subpopulations' field (must be deleted)"


def test_no_mixture_properties():
    """Mixture properties must not exist (viability is authoritative)."""
    from cell_os.hardware.biological_virtual import VesselState

    # Check class doesn't have these properties
    forbidden = ['viability_mixture', 'er_stress_mixture', 'mito_dysfunction_mixture',
                 'transport_dysfunction_mixture', 'get_mixture_width',
                 'get_artifact_inflated_mixture_width']

    for prop in forbidden:
        assert not hasattr(VesselState, prop), \
            f"FAIL: VesselState still has '{prop}' (must be deleted)"


def test_no_recompute_from_subpops():
    """_recompute_vessel_from_subpops must not exist."""
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine

    vm = BiologicalVirtualMachine(seed=42)

    assert not hasattr(vm, '_recompute_vessel_from_subpops'), \
        "FAIL: _recompute_vessel_from_subpops still exists (must be deleted)"


def test_scRNA_signature_has_no_fractions():
    """scRNA measure() must not accept subpop_fractions parameter."""
    from cell_os.hardware.assays.scrna_seq import ScRNASeqAssay

    sig = inspect.signature(ScRNASeqAssay.measure)
    param_names = list(sig.parameters.keys())

    forbidden = ['subpop_fractions', 'subpopulations', 'mixture_fractions']
    for forbidden_param in forbidden:
        assert forbidden_param not in param_names, \
            f"FAIL: scRNA.measure() has privileged parameter '{forbidden_param}'"


class SubpopAccessVisitor(ast.NodeVisitor):
    """AST visitor to detect vessel.subpopulations access."""

    def __init__(self):
        self.violations = []

    def visit_Attribute(self, node):
        # Check for vessel.subpopulations
        if (isinstance(node.value, ast.Name) and
            node.value.id == 'vessel' and
            node.attr == 'subpopulations'):
            lineno = getattr(node, 'lineno', '?')
            self.violations.append(f"vessel.subpopulations access at line {lineno}")
        self.generic_visit(node)

    def visit_Call(self, node):
        # Check for function calls with subpop_fractions keyword
        for keyword in node.keywords:
            if keyword.arg in ['subpop_fractions', 'mixture_fractions', 'subpopulations']:
                lineno = getattr(node, 'lineno', '?')
                self.violations.append(
                    f"Call with '{keyword.arg}=' keyword at line {lineno}"
                )
        self.generic_visit(node)


def test_scRNA_code_does_not_access_subpopulations():
    """scRNA source code must not access vessel.subpopulations (AST-based)."""
    from cell_os.hardware.assays import scrna_seq as scrna_module

    source = inspect.getsource(scrna_module)
    source = textwrap.dedent(source)

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        pytest.fail(f"Could not parse scRNA source: {e}")

    visitor = SubpopAccessVisitor()
    visitor.visit(tree)

    if visitor.violations:
        violations_str = '\n  '.join(visitor.violations)
        pytest.fail(
            f"FAIL: scRNA code accesses privileged subpopulation structure:\n  {violations_str}"
        )


def test_propose_hazard_validates_death_field():
    """_propose_hazard must validate death field names."""
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine, TRACKED_DEATH_FIELDS

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]

    # Valid death fields should work
    for field in TRACKED_DEATH_FIELDS:
        vessel._step_hazard_proposals = {}
        vm._propose_hazard(vessel, 0.01, field)

    # Invalid fields should raise
    invalid_fields = [
        'er_stress',
        'mito_dysfunction',
        'viability',
        'death_typo',
        'subpopulations',
        'death_unattributed',  # Residual, not proposable
    ]

    for invalid_field in invalid_fields:
        vessel._step_hazard_proposals = {}
        with pytest.raises(ValueError, match="Unknown death_field"):
            vm._propose_hazard(vessel, 0.01, invalid_field)


def test_tracked_death_fields_are_vessel_attributes():
    """All TRACKED_DEATH_FIELDS must exist as VesselState attributes."""
    from cell_os.hardware.biological_virtual import BiologicalVirtualMachine, TRACKED_DEATH_FIELDS

    vm = BiologicalVirtualMachine(seed=42)
    vm.seed_vessel("P1_A01", "A549", initial_count=1e6, vessel_type='96-well')
    vessel = vm.vessel_states["P1_A01"]

    for death_field in TRACKED_DEATH_FIELDS:
        assert hasattr(vessel, death_field), \
            f"TRACKED_DEATH_FIELDS contains '{death_field}' but VesselState has no such attribute"

        value = getattr(vessel, death_field)
        assert isinstance(value, (int, float)), \
            f"Death field '{death_field}' is not numeric (got {type(value)})"

        # Note: Fields may be >0 due to seeding stress (death_unknown) or other causes
        # We only verify they exist and are numeric, not that they're zero


def test_unattributed_is_not_proposable():
    """death_unattributed is residual, never a proposal target."""
    from cell_os.hardware.biological_virtual import TRACKED_DEATH_FIELDS

    assert "death_unattributed" not in TRACKED_DEATH_FIELDS, \
        "death_unattributed must NOT be in TRACKED_DEATH_FIELDS (it's residual, computed not proposed)"
