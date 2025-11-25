"""
Unit tests for ActiveLearner.

Tests posterior rebuilding and update logic.
"""


import pytest
import pandas as pd

# Import ActiveLearner from run_loop since it's defined there
# We'll need to mock or extract it for proper testing
# For now, test the core logic


def test_active_learner_initialization():
    """Test ActiveLearner can be initialized."""
    # This would require importing from scripts/run_loop.py
    # Since that's an entry point script, we'll create a minimal test
    
    from pathlib import Path
    import importlib.util
    
    spec = importlib.util.spec_from_file_location(
        "run_loop",
        Path(__file__).parent.parent.parent / "scripts" / "run_loop.py"
    )
    run_loop = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_loop)
    
    learner = run_loop.ActiveLearner()
    
    assert learner is not None
    assert len(learner.history) == 0
    assert learner.posterior is not None


def test_active_learner_update():
    """Test updating ActiveLearner with new records."""
    from pathlib import Path
    import importlib.util
    
    spec = importlib.util.spec_from_file_location(
        "run_loop",
        Path(__file__).parent.parent.parent / "scripts" / "run_loop.py"
    )
    run_loop = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_loop)
    
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
    from pathlib import Path
    import importlib.util
    
    spec = importlib.util.spec_from_file_location(
        "run_loop",
        Path(__file__).parent.parent.parent / "scripts" / "run_loop.py"
    )
    run_loop = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_loop)
    
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
    from pathlib import Path
    import importlib.util
    
    spec = importlib.util.spec_from_file_location(
        "run_loop",
        Path(__file__).parent.parent.parent / "scripts" / "run_loop.py"
    )
    run_loop = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run_loop)
    
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
