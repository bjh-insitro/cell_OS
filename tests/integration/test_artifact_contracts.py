"""
Integration test enforcing instrument artifact contracts.

This test prevents artifact sprawl by ensuring:
1. Every artifact declares ARTIFACT_SPEC
2. Required fields are present
3. Domain-specific constraints are respected
4. Separation of concerns is maintained
5. Ledger term naming conventions are followed

If this test fails, the artifact violates the contract.
"""

import pytest
from src.cell_os.hardware import aspiration_effects, evaporation_effects, carryover_effects


# List of all artifact modules
ARTIFACT_MODULES = [
    ('aspiration_effects', aspiration_effects),
    ('evaporation_effects', evaporation_effects),
    ('carryover_effects', carryover_effects),
]


def test_all_artifacts_expose_spec():
    """Every artifact module must expose ARTIFACT_SPEC."""
    for name, module in ARTIFACT_MODULES:
        assert hasattr(module, 'ARTIFACT_SPEC'), \
            f"{name} must declare ARTIFACT_SPEC at module level"
        assert isinstance(module.ARTIFACT_SPEC, dict), \
            f"{name}.ARTIFACT_SPEC must be a dict"


def test_required_fields_present():
    """ARTIFACT_SPEC must contain all required fields."""
    required_fields = [
        'domain',
        'state_mutations',
        'affected_observables',
        'epistemic_prior',
        'ledger_terms',
        'correlation_groups',
        'forbidden_dependencies',
        'version',
        'implemented',
        'tests'
    ]

    for name, module in ARTIFACT_MODULES:
        spec = module.ARTIFACT_SPEC
        for field in required_fields:
            assert field in spec, \
                f"{name}.ARTIFACT_SPEC missing required field: {field}"


def test_domain_is_valid():
    """Domain must be one of: spatial, sequence, temporal, global."""
    valid_domains = {'spatial', 'sequence', 'temporal', 'global'}

    for name, module in ARTIFACT_MODULES:
        spec = module.ARTIFACT_SPEC
        assert spec['domain'] in valid_domains, \
            f"{name} has invalid domain: {spec['domain']} (must be one of {valid_domains})"


def test_epistemic_prior_structure():
    """Epistemic prior must have parameter, distribution, calibration_method."""
    for name, module in ARTIFACT_MODULES:
        spec = module.ARTIFACT_SPEC
        prior = spec['epistemic_prior']

        assert 'parameter' in prior, f"{name} epistemic_prior missing 'parameter'"
        assert 'distribution' in prior, f"{name} epistemic_prior missing 'distribution'"
        assert 'calibration_method' in prior, f"{name} epistemic_prior missing 'calibration_method'"

        assert isinstance(prior['parameter'], str), f"{name} parameter must be string"
        assert isinstance(prior['distribution'], str), f"{name} distribution must be string"
        assert isinstance(prior['calibration_method'], str), f"{name} calibration_method must be string"


def test_exactly_two_ledger_terms():
    """Each artifact must declare exactly 2 ledger terms: modeled + ridge."""
    for name, module in ARTIFACT_MODULES:
        spec = module.ARTIFACT_SPEC
        terms = spec['ledger_terms']

        assert 'modeled' in terms, f"{name} missing 'modeled' ledger term"
        assert 'ridge' in terms, f"{name} missing 'ridge' ledger term"
        assert len(terms) == 2, \
            f"{name} must have exactly 2 ledger terms (modeled + ridge), got {len(terms)}"


def test_ledger_term_naming_conventions():
    """Ledger terms must follow naming conventions."""
    for name, module in ARTIFACT_MODULES:
        spec = module.ARTIFACT_SPEC
        terms = spec['ledger_terms']

        modeled = terms['modeled']
        ridge = terms['ridge']

        assert modeled.startswith('VAR_INSTRUMENT_'), \
            f"{name} modeled term must start with 'VAR_INSTRUMENT_', got: {modeled}"

        assert ridge.startswith('VAR_CALIBRATION_'), \
            f"{name} ridge term must start with 'VAR_CALIBRATION_', got: {ridge}"


def test_correlation_groups_present():
    """Correlation groups must be declared for modeled and ridge."""
    for name, module in ARTIFACT_MODULES:
        spec = module.ARTIFACT_SPEC
        groups = spec['correlation_groups']

        assert 'modeled' in groups, f"{name} missing 'modeled' correlation group"
        assert 'ridge' in groups, f"{name} missing 'ridge' correlation group"

        assert isinstance(groups['modeled'], str), f"{name} modeled correlation group must be string"
        assert isinstance(groups['ridge'], str), f"{name} ridge correlation group must be string"


def test_spatial_artifacts_forbid_sequence_dependencies():
    """Spatial artifacts must NOT depend on sequence."""
    spatial_artifacts = [
        (name, module) for name, module in ARTIFACT_MODULES
        if module.ARTIFACT_SPEC['domain'] == 'spatial'
    ]

    forbidden_sequence_terms = ['dispense_sequence', 'sequence_index', 'sequence_adjacency']

    for name, module in spatial_artifacts:
        spec = module.ARTIFACT_SPEC
        forbidden = spec['forbidden_dependencies']

        # At least one sequence term must be in forbidden list
        has_sequence_forbid = any(term in forbidden for term in forbidden_sequence_terms)
        assert has_sequence_forbid, \
            f"{name} is spatial but doesn't forbid sequence dependencies. " \
            f"Expected one of {forbidden_sequence_terms} in forbidden_dependencies: {forbidden}"


def test_sequence_artifacts_forbid_geometry_dependencies():
    """Sequence artifacts must NOT depend on spatial geometry."""
    sequence_artifacts = [
        (name, module) for name, module in ARTIFACT_MODULES
        if module.ARTIFACT_SPEC['domain'] == 'sequence'
    ]

    forbidden_geometry_terms = ['well_geometry', 'plate_position', 'edge_distance']

    for name, module in sequence_artifacts:
        spec = module.ARTIFACT_SPEC
        forbidden = spec['forbidden_dependencies']

        # At least one geometry term must be in forbidden list
        has_geometry_forbid = any(term in forbidden for term in forbidden_geometry_terms)
        assert has_geometry_forbid, \
            f"{name} is sequence but doesn't forbid geometry dependencies. " \
            f"Expected one of {forbidden_geometry_terms} in forbidden_dependencies: {forbidden}"


def test_aspiration_specific_constraints():
    """Aspiration-specific contract validation."""
    spec = aspiration_effects.ARTIFACT_SPEC

    assert spec['domain'] == 'spatial', "Aspiration must be spatial"
    assert 'dispense_sequence' in spec['forbidden_dependencies'], \
        "Aspiration must forbid dispense_sequence"
    assert spec['epistemic_prior']['parameter'] == 'gamma'
    assert spec['epistemic_prior']['calibration_method'] == 'microscopy'


def test_evaporation_specific_constraints():
    """Evaporation-specific contract validation."""
    spec = evaporation_effects.ARTIFACT_SPEC

    assert spec['domain'] == 'spatial', "Evaporation must be spatial"
    assert 'sequence_index' in spec['forbidden_dependencies'], \
        "Evaporation must forbid sequence_index"
    assert 'aspiration_angle' in spec['forbidden_dependencies'], \
        "Evaporation must forbid aspiration_angle (no double-counting)"
    assert spec['epistemic_prior']['parameter'] == 'base_evap_rate'
    assert spec['epistemic_prior']['calibration_method'] == 'gravimetry'


def test_carryover_specific_constraints():
    """Carryover-specific contract validation."""
    spec = carryover_effects.ARTIFACT_SPEC

    assert spec['domain'] == 'sequence', "Carryover must be sequence"
    assert 'well_geometry' in spec['forbidden_dependencies'], \
        "Carryover must forbid well_geometry"
    assert 'plate_position' in spec['forbidden_dependencies'], \
        "Carryover must forbid plate_position"
    assert spec['epistemic_prior']['parameter'] == 'carryover_fraction'
    assert spec['epistemic_prior']['calibration_method'] == 'blank_after_hot'


def test_version_and_provenance():
    """All artifacts must declare version and provenance."""
    for name, module in ARTIFACT_MODULES:
        spec = module.ARTIFACT_SPEC

        assert 'version' in spec, f"{name} missing version"
        assert 'implemented' in spec, f"{name} missing implemented date"
        assert 'tests' in spec, f"{name} missing tests list"

        assert spec['version'] == '1.0', f"{name} must be version 1.0"
        assert isinstance(spec['tests'], list), f"{name} tests must be a list"
        assert len(spec['tests']) > 0, f"{name} must declare at least one test file"


def test_no_overlap_in_correlation_groups():
    """Spatial and sequence artifacts must use different correlation group names."""
    spatial_groups = set()
    sequence_groups = set()

    for name, module in ARTIFACT_MODULES:
        spec = module.ARTIFACT_SPEC
        domain = spec['domain']
        groups = spec['correlation_groups']

        if domain == 'spatial':
            spatial_groups.add(groups['modeled'])
        elif domain == 'sequence':
            sequence_groups.add(groups['modeled'])

    # No overlap between spatial and sequence correlation groups
    overlap = spatial_groups & sequence_groups
    assert len(overlap) == 0, \
        f"Spatial and sequence artifacts must use different correlation groups. " \
        f"Overlap: {overlap}"


def test_contract_completeness():
    """Meta-test: Ensure this test covers all contract requirements."""
    # This test documents what the contract enforces
    enforced_rules = [
        'ARTIFACT_SPEC exposed',
        'Required fields present',
        'Valid domain',
        'Epistemic prior structure',
        'Exactly 2 ledger terms',
        'Ledger term naming conventions',
        'Correlation groups present',
        'Spatial forbids sequence',
        'Sequence forbids geometry',
        'Aspiration-specific constraints',
        'Evaporation-specific constraints',
        'Carryover-specific constraints',
        'Version and provenance',
        'No overlap in correlation groups'
    ]

    # We have 15 test functions (14 rules + this meta-test)
    # If you add a new rule, add a new test function
    print(f"\n✓ Contract enforces {len(enforced_rules)} rules")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
