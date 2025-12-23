#!/bin/bash
# Try seed 5003 to find clean calibration plate

set -e

echo "=========================================================================="
echo "Testing seed 5003..."
echo "=========================================================================="

PYTHONPATH=$PWD:$PYTHONPATH timeout 600 python3 scripts/run_v4_phase1.py --seeds 5003

echo ""
echo "Checking if seed 5003 is clean..."
echo ""

python3 scripts/check_seed_clean.py 5003
