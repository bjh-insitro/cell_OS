#!/usr/bin/env python3
"""
Scout rotenone doses for Phase 2C.2 mito-dominant regime.

Goal: Find doses that:
1. Bracket mito commitment threshold (0.60)
2. Produce stress range: S_mito ∈ [0.4, 0.8]
3. Generate 10-40 events per 48 wells over 120h

Current design uses: 0.5, 1.0, 2.0, 4.0 µM
This scout validates whether these doses produce the desired stress distribution.
"""

import sys
from pathlib import Path
import numpy as np

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from cell_os.calibration.identifiability_runner import run_dose_scout


def main():
    # Config path
    config_path = str(project_root / "configs" / "calibration" / "identifiability_2c2.yaml")

    # Scout rotenone doses
    # Test range: 0.1 to 10.0 µM (log-spaced)
    # ec50_uM = 1.0, so this spans 0.1× to 10× EC50
    dose_range = (0.1, 10.0)
    n_doses = 12
    n_wells_per_dose = 4

    output_dir = str(project_root / "data" / "identifiability_scout_rotenone")

    print(f"Running rotenone dose scout: {dose_range[0]:.2f}-{dose_range[1]:.1f} µM")
    print(f"Output: {output_dir}")
    print()

    run_dir = run_dose_scout(
        config_path=config_path,
        output_dir=output_dir,
        compound="rotenone",
        dose_range=dose_range,
        n_doses=n_doses,
        n_wells_per_dose=n_wells_per_dose
    )

    print("\n✓ Scout complete. Check dose_analysis.csv and scout_report.md")
    print(f"   {run_dir}/scout_report.md")


if __name__ == "__main__":
    main()
