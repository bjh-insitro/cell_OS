#!/usr/bin/env python3
"""Generate synthetic morphology embeddings for testing.

Creates realistic-but-synthetic embeddings with:
- Dose-response relationships
- Compound-specific effects
- Cell line variability
- Deterministic generation
"""

import numpy as np
import pandas as pd
from pathlib import Path


def generate_synthetic_embeddings(
    cell_lines=["A549", "HepG2"],
    compounds=["TBHP", "Staurosporine", "Nocodazole"],
    doses_uM=[0.0, 0.1, 0.5, 1.0, 5.0, 10.0],
    times_h=[24.0],
    n_replicates=3,
    dim=50,
    seed=42,
):
    """Generate synthetic morphology embeddings.
    
    Parameters
    ----------
    cell_lines : list
        Cell line names
    compounds : list
        Compound names
    doses_uM : list
        Doses in micromolar
    times_h : list
        Time points in hours
    n_replicates : int
        Number of replicate wells per condition
    dim : int
        Embedding dimensionality
    seed : int
        Random seed for reproducibility
    
    Returns
    -------
    df : pd.DataFrame
        Embeddings with schema matching RealMorphologyEngine
    """
    rng = np.random.RandomState(seed)
    
    rows = []
    
    for cell_line in cell_lines:
        # Each cell line has a baseline embedding
        cell_baseline = rng.normal(0, 0.5, dim)
        
        for compound in compounds:
            # Each compound has a characteristic effect direction
            compound_effect = rng.normal(0, 1.0, dim)
            compound_effect /= np.linalg.norm(compound_effect)  # Normalize
            
            for time_h in times_h:
                for dose_uM in doses_uM:
                    # Dose-response: sigmoid curve
                    # EC50 varies by compound
                    if compound == "TBHP":
                        ec50 = 1.0
                    elif compound == "Staurosporine":
                        ec50 = 0.5
                    else:  # Nocodazole
                        ec50 = 2.0
                    
                    # Hill equation
                    hill_coef = 2.0
                    response = dose_uM**hill_coef / (ec50**hill_coef + dose_uM**hill_coef)
                    
                    # Embedding = baseline + response * compound_effect + noise
                    for rep in range(n_replicates):
                        plate_id = f"plate_{rep + 1}"
                        well_id = f"well_{cell_line}_{compound}_{dose_uM}_{rep}"
                        
                        # Add biological + technical noise
                        noise = rng.normal(0, 0.1, dim)
                        embedding = cell_baseline + response * compound_effect + noise
                        
                        # Create row
                        row = {
                            "cell_line": cell_line,
                            "compound": compound,
                            "dose_uM": dose_uM,
                            "time_h": time_h,
                            "plate_id": plate_id,
                            "well_id": well_id,
                        }
                        
                        # Add feature columns
                        for i in range(dim):
                            row[f"feat_{i+1:03d}"] = embedding[i]
                        
                        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    # Sort for determinism
    df = df.sort_values(["cell_line", "compound", "dose_uM", "time_h", "plate_id", "well_id"])
    df = df.reset_index(drop=True)
    
    return df


def main():
    """Generate and save synthetic embeddings."""
    print("Generating synthetic morphology embeddings...")
    
    df = generate_synthetic_embeddings(
        cell_lines=["A549", "HepG2"],
        compounds=["TBHP", "Staurosporine", "Nocodazole"],
        doses_uM=[0.0, 0.1, 0.5, 1.0, 5.0, 10.0],
        times_h=[24.0],
        n_replicates=3,
        dim=50,
        seed=42,
    )
    
    # Save to CSV
    output_path = Path("data/morphology/example_embeddings.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    
    print(f"✓ Generated {len(df)} embeddings")
    print(f"✓ Saved to: {output_path}")
    print(f"\nSchema:")
    print(f"  Conditions: {df['cell_line'].nunique()} cell lines, "
          f"{df['compound'].nunique()} compounds, "
          f"{df['dose_uM'].nunique()} doses")
    print(f"  Features: {len([c for c in df.columns if c.startswith('feat_')])} dimensions")
    print(f"  Total rows: {len(df)}")


if __name__ == "__main__":
    main()
