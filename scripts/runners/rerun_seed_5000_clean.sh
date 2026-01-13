#!/bin/bash
# Rerun seed 5000 with realistic well_failure_rate (0.013% → 5% plate failure)

set -e

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                RERUN SEED 5000 WITH REALISTIC FAILURE RATE                   ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Previous rate: 0.02 (2% per well) → 99.9% plate failure"
echo "New rate:      0.00013 (0.013% per well) → 5% plate failure"
echo ""
echo "Expected: Seed 5000 should now be CLEAN (95% probability)"
echo ""

echo "=== Pulling latest changes ==="
git pull origin main
echo ""

echo "=========================================================================="
echo "Running seed 5000 with new failure rate..."
echo "=========================================================================="

PYTHONPATH=$PWD:$PYTHONPATH timeout 600 python3 scripts/run_v4_phase1.py --seeds 5000

echo ""
echo "=========================================================================="
echo "Checking if seed 5000 is clean..."
echo "=========================================================================="
echo ""

python3 scripts/check_seed_clean.py 5000

if [ $? -eq 0 ]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                           SUCCESS!                                           ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Seed 5000 is now clean. Ready for full validation:"
    echo "  PYTHONPATH=\$PWD:\$PYTHONPATH python3 scripts/validate_structured_noise.py 5000"
fi
