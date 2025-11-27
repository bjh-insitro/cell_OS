"""Smoketest for POSH campaign demo script."""

import os
import subprocess
import pytest
import pandas as pd


def test_posh_campaign_demo_runs():
    """Test that the POSH campaign demo runs and writes a non-empty hits CSV."""
    # Run the demo script via subprocess
    result = subprocess.run(
        ["venv/bin/python", "scripts/run_posh_campaign_demo.py"],
        cwd=os.getcwd(),
        capture_output=True,
        text=True,
    )
    
    # Check that script ran successfully
    assert result.returncode == 0, f"Script failed with: {result.stderr}"
    
    # Check that output file was created
    output_path = "results/posh_demo_hits.csv"
    assert os.path.exists(output_path), f"Output file not found: {output_path}"
    
    # Check that it has content
    df = pd.read_csv(output_path)
    assert len(df) > 0, "CSV should have at least one row"
    
    # Check required columns
    required_columns = [
        "gene",
        "phenotype_score",
        "distance_to_centroid",
        "embedding_norm",
        "rank_by_distance",
    ]
    for col in required_columns:
        assert col in df.columns, f"Missing required column: {col}"
    
    # Check that distance_to_centroid is non-negative
    assert (df["distance_to_centroid"] >= 0).all()
    
    # Check that rank_by_distance starts at 1
    assert df["rank_by_distance"].min() == 1
    
    print(f"✓ Demo produced {len(df)} hits")
    print(f"✓ Top hit: {df.iloc[0]['gene']}")


if __name__ == "__main__":
    pytest.main([__file__, "-vv"])
