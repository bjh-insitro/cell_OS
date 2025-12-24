"""
Tripwire Test: No Ground Truth Leakage

Enforces STATE_MAP.md Section 3: Observability Surface

FAILURE MODE: If this test fails, ground truth is leaking to agent.
"""

import pytest
from cell_os.hardware.run_context import RunContext
from tests.tripwire._harness import make_world, run_world


# Forbidden substrings that MUST NOT appear in observation keys
# Blunt bat: catch any field name that smells like ground truth
FORBIDDEN_SUBSTRINGS = {
    'viability',
    'death_',
    'stress',  # er_stress, mito_dysfunction, etc.
    'latent',
    'ic50',
    'gamma',
    'ground_truth',
    '_debug',
    'volume_mult',
}


def test_debug_truth_disabled_by_default():
    """
    Verify debug_truth_enabled is False in production runs.

    Debug truth is ONLY allowed in tests with explicit opt-in.
    """
    run_context = RunContext.sample(seed=42)
    assert not getattr(run_context, 'debug_truth_enabled', False), \
        "debug_truth_enabled must be False by default"


def test_no_forbidden_keys_in_observations():
    """
    Verify RawWellResult does not contain forbidden ground truth keys.

    Uses blunt substring matching to catch any oracle leakage.
    """
    world = make_world(seed=0, budget_wells=10)

    # Run minimal experiment
    wells = [
        {
            'cell_line': 'A549',
            'compound': None,
            'dose_uM': None,
            'assay': 'cell_count',
            'duration_h': 72.0
        }
    ]

    results = run_world(world, wells)

    # Check each observation
    for obs in results:
        obs_dict = obs.__dict__

        # Check top-level keys
        for key in obs_dict.keys():
            for forbidden in FORBIDDEN_SUBSTRINGS:
                assert forbidden not in key.lower(), \
                    f"Forbidden substring '{forbidden}' in observation key: {key}"

        # Check readouts dict
        if 'readouts' in obs_dict and obs_dict['readouts']:
            readouts = obs_dict['readouts']
            for key in readouts.keys():
                for forbidden in FORBIDDEN_SUBSTRINGS:
                    assert forbidden not in key.lower(), \
                        f"Forbidden substring '{forbidden}' in readout: {key}"

        # Check qc dict
        if 'qc' in obs_dict and obs_dict['qc']:
            qc = obs_dict['qc']
            for key in qc.keys():
                for forbidden in FORBIDDEN_SUBSTRINGS:
                    assert forbidden not in key.lower(), \
                        f"Forbidden substring '{forbidden}' in QC: {key}"


def test_observations_only_contain_known_keys():
    """
    Verify observations contain only a known allowlist of top-level keys.

    Fail if new keys appear (requires review).
    """
    world = make_world(seed=0, budget_wells=10)

    wells = [
        {
            'cell_line': 'A549',
            'compound': None,
            'dose_uM': None,
            'assay': 'cell_count',
            'duration_h': 72.0
        }
    ]

    results = run_world(world, wells)

    # Known safe keys
    allowed_keys = {
        'location',
        'cell_line',
        'treatment',
        'assay',
        'observation_time_h',
        'readouts',
        'qc',
    }

    for obs in results:
        obs_dict = obs.__dict__
        actual_keys = set(obs_dict.keys())

        # Check for unexpected keys
        unexpected = actual_keys - allowed_keys
        assert not unexpected, \
            f"Unexpected keys in observation (review for ground truth): {unexpected}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
