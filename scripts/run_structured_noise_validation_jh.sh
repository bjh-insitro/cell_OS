#!/bin/bash
# Run structured noise validation on JupyterHub
# This script should be run ON JH directly from cell_OS repo root

set -e

# Get the directory where the script lives and go to repo root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."

echo "=== Pulling latest changes ==="
git pull origin main
echo ""

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║              STRUCTURED NOISE VALIDATION - V4 PHASE 1                       ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Testing persistent per-well biology with coupled stain/focus factors"
echo "Seeds: 4000, 4100, 4200 (post-keying-fix seeds)"
echo ""
echo "Fixes applied:"
echo "  1. Key well_biology to well_position+cell_line (not vessel_id)"
echo "  2. Per-channel deterministic seeding for well_factor (not sequential RNG)"
echo ""

# Run Phase 1 with 3 seeds
REPO_ROOT=$(pwd)
for seed in 4000 4100 4200; do
    echo "=========================================================================="
    echo "Running seed $seed..."
    echo "=========================================================================="
    PYTHONPATH=$REPO_ROOT:$PYTHONPATH timeout 600 python3 scripts/run_v4_phase1.py --seeds $seed

    if [ $? -eq 0 ]; then
        echo "✅ Seed $seed complete"
    elif [ $? -eq 124 ]; then
        echo "⏱️  Seed $seed timeout (10min)"
    else
        echo "❌ Seed $seed failed"
    fi
    echo ""
done

echo "=========================================================================="
echo "Running Validation Analysis"
echo "=========================================================================="
echo ""

PYTHONPATH=$REPO_ROOT:$PYTHONPATH python3 scripts/validate_structured_noise.py 4000 4100 4200

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                        VALIDATION COMPLETE                                   ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Critical checks:"
echo "  1. Vehicle CV: Should be 8-12% (was 2-4%)"
echo "  2. Channel correlations: Should drop from ~0.96 to 0.3-0.5"
echo "  3. Well persistence: Should improve to <15% CV across seeds (was 26%)"
echo "  4. Outlier fingerprints: Should show clear stain/focus signatures"
echo ""
echo "If Check 3 passes → wells have identity → agent can learn instrument trust"
echo ""
