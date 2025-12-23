#!/bin/bash
# Run structured noise validation on JupyterHub
# This script should be run ON JH directly

set -e

cd /home/ubuntu/cell_OS

echo "=== Pulling latest changes ==="
git pull origin main
echo ""

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║              STRUCTURED NOISE VALIDATION - V4 PHASE 1                       ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Testing persistent per-well biology with coupled stain/focus factors"
echo "Seeds: 2000, 2100, 2200 (fresh seeds, post-refactor)"
echo ""

# Run Phase 1 with 3 seeds
for seed in 2000 2100 2200; do
    echo "=========================================================================="
    echo "Running seed $seed..."
    echo "=========================================================================="
    PYTHONPATH=/home/ubuntu/cell_OS:$PYTHONPATH timeout 600 python3 scripts/run_v4_phase1.py --seeds $seed

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

PYTHONPATH=/home/ubuntu/cell_OS:$PYTHONPATH python3 scripts/validate_structured_noise.py 2000 2100 2200

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
