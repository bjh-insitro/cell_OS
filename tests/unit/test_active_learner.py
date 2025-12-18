"""
Unit tests for ActiveLearner.

Tests posterior rebuilding and update logic.

NOTE: These tests are currently skipped because run_loop.py has been archived
to scripts/archive/demos/run_loop.py. If ActiveLearner functionality is needed
in production, it should be extracted from the archive into a proper module
(e.g., src/cell_os/active_learning/learner.py), and these tests should be updated.
"""


import importlib.util
from pathlib import Path

import pytest
import pandas as pd


pytestmark = pytest.mark.skip(reason="run_loop.py archived to scripts/archive/demos/")


def _load_run_loop_module():
    """Helper to import scripts/demos/run_loop.py for tests."""
    repo_root = Path(__file__).resolve().parents[2]
    run_loop_path = repo_root / "scripts" / "demos" / "run_loop.py"
    spec = importlib.util.spec_from_file_location("run_loop", run_loop_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_active_learner_initialization():
    """Test ActiveLearner can be initialized."""
    # This would require importing from scripts/demos/run_loop.py
    # Since that's an entry point script, we'll create a minimal test
    
    run_loop = _load_run_loop_module()
    learner = run_loop.ActiveLearner()
    
    assert learner is not None
    assert len(learner.history) == 0
    assert learner.posterior is not None


def test_active_learner_update():
    """Test updating ActiveLearner with new records."""
    run_loop = _load_run_loop_module()
    learner = run_loop.ActiveLearner()
    
    # Create mock experiment records
    records = [
        {
            'cell_line': 'HepG2',
            'compound': 'CompoundA',
            'time_h': 24.0,
            'dose': 1.0,
            'viability': 0.50
        },
        {
            'cell_line': 'HepG2',
            'compound': 'CompoundA',
            'time_h': 24.0,
            'dose': 0.1,
            'viability': 0.90
        }
    ]
    
    initial_len = len(learner.history)
    learner.update(records)
    
    assert len(learner.history) == initial_len + 2


def test_active_learner_posterior_rebuild():
    """Test that posterior rebuilds after update."""
    run_loop = _load_run_loop_module()
    learner = run_loop.ActiveLearner()
    
    # Add sufficient records to build a GP
    records = []
    for dose in [0.01, 0.1, 0.5, 1.0, 2.0, 5.0]:
        records.append({
            'cell_line': 'HepG2',
            'compound': 'CompoundA',
            'time_h': 24.0,
            'dose': dose,
            'viability': 1.0 / (1.0 + dose)  # Simple inverse relationship
        })
    
    learner.update(records)
    
    # Check that GP was created
    assert len(learner.gp_models) > 0


def test_active_learner_multiple_slices():
    """Test that ActiveLearner creates separate GPs for different slices."""
    run_loop = _load_run_loop_module()
    learner = run_loop.ActiveLearner()
    
    records = []
    
    # Add records for two different compounds
    for compound in ['CompoundA', 'CompoundB']:
        for dose in [0.1, 1.0, 10.0]:
            records.append({
                'cell_line': 'HepG2',
                'compound': compound,
                'time_h': 24.0,
                'dose': dose,
                'viability': 0.5
            })
    
    learner.update(records)
    
    # Should have at least 2 GPs (one per compound)
    assert len(learner.gp_models) >= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
