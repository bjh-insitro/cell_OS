#!/bin/bash
# Find a clean calibration plate (no well failures in vehicle islands)
# Run on JupyterHub from cell_OS repo root

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║           FIND CLEAN CALIBRATION PLATE (Philosophy B)                       ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Philosophy B: Calibration plates simulate realistic failures"
echo "  - Well failures (contamination, bubbles) occur at 2% rate"
echo "  - When vehicle islands have failures → reject plate and rerun"
echo "  - This matches real lab workflow: bad QC plates are discarded"
echo ""
echo "Testing seeds 5001, 5002, 5003 to find a clean plate..."
echo ""

REPO_ROOT=$(pwd)

for seed in 5001 5002 5003; do
    echo "=========================================================================="
    echo "Testing seed $seed..."
    echo "=========================================================================="

    # Run plate execution
    PYTHONPATH=$REPO_ROOT:$PYTHONPATH timeout 600 python3 scripts/run_v4_phase1.py --seeds $seed

    if [ $? -ne 0 ]; then
        echo "❌ Seed $seed execution failed"
        continue
    fi

    echo ""
    echo "Checking for well failures in vehicle islands..."

    # Quick check: Are all 5 vehicle islands clean (CV < 20%)?
    PYTHONPATH=$REPO_ROOT:$PYTHONPATH python3 -c "
import json
import numpy as np
from pathlib import Path

VEHICLE_ISLANDS = {
    'CV_NW_HEPG2_VEH': ['D4','D5','D6','E4','E5','E6','F4','F5','F6'],
    'CV_NW_A549_VEH': ['D8','D9','D10','E8','E9','E10','F8','F9','F10'],
    'CV_NE_HEPG2_VEH': ['D15','D16','D17','E15','E16','E17','F15','F16','F17'],
    'CV_NE_A549_VEH': ['D20','D21','D22','E20','E21','E22','F20','F21','F22'],
    'CV_SE_HEPG2_VEH': ['K15','K16','K17','L15','L16','L17','M15','M16','M17']
}

results_dir = Path('validation_frontend/public/demo_results/calibration_plates')
files = sorted(results_dir.glob(f'*seed${seed}.json'), key=lambda p: p.stat().st_mtime, reverse=True)

if not files:
    print('❌ No results found for seed ${seed}')
    exit(1)

data = json.load(open(files[0]))
flat_results = data['flat_results']

print()
print('Vehicle island CVs:')
all_clean = True
island_cvs = []

for island_id, wells in VEHICLE_ISLANDS.items():
    island_data = [r for r in flat_results if r['well_id'] in wells]
    values = [r['morph_er'] for r in island_data if 'morph_er' in r]

    if len(values) > 0:
        cv = 100 * np.std(values) / np.mean(values)
        island_cvs.append(cv)
        status = '✅' if cv < 20 else '❌'
        print(f'  {island_id:20s}: CV={cv:5.1f}% {status}')

        if cv >= 20:
            all_clean = False
            # Find outliers
            mean = np.mean(values)
            std = np.std(values)
            threshold = mean + 2*std
            outliers = [r for r in island_data if r['morph_er'] > threshold]
            if outliers:
                print(f'    Outliers: {[r[\"well_id\"] for r in outliers]}')

print()
if all_clean:
    print('✅ CLEAN PLATE FOUND!')
    print(f'   Seed ${seed} has no well failures in vehicle islands')
    print(f'   Mean CV: {np.mean(island_cvs):.1f}%')
    exit(0)
else:
    print('❌ Plate contaminated (has well failures in vehicle islands)')
    print('   Reject and rerun with new seed (real lab workflow)')
    exit(1)
"

    if [ $? -eq 0 ]; then
        echo ""
        echo "╔══════════════════════════════════════════════════════════════════════════════╗"
        echo "║                     CLEAN PLATE FOUND: seed $seed                             ║"
        echo "╚══════════════════════════════════════════════════════════════════════════════╝"
        echo ""
        echo "Next step: Run full validation on seed $seed"
        echo "  PYTHONPATH=\$PWD:\$PYTHONPATH python3 scripts/validate_structured_noise.py $seed"
        exit 0
    else
        echo ""
        echo "Seed $seed rejected (well failures detected). Trying next seed..."
        echo ""
    fi
done

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                     NO CLEAN PLATE FOUND                                     ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "All 3 seeds (5001-5003) had well failures in vehicle islands."
echo "Options:"
echo "  1. Try more seeds (5004, 5005, ...)"
echo "  2. Accept seed 5000 contamination as a learning experience"
echo "  3. Reduce well_failure_rate in cell_thalamus_params.yaml"
