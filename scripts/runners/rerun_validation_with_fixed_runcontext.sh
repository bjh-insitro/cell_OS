#!/bin/bash
# Rerun validation with fixed RunContext factors (±5% instead of ±22%)

set -e

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║           RERUN VALIDATION WITH REALISTIC RUN-TO-RUN VARIANCE                ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Fix: Reduced RunContext factors from ±22% to ±5%"
echo "  - instrument_shift: 0.2 → 0.05 (illumination_bias: ±22% → ±5%)"
echo "  - reagent_lot_shift: 0.15 → 0.05 (channel_biases: ±16% → ±5%)"
echo ""
echo "Expected: Within-well CV drops from 27.7% to ~8-10%"
echo "          Wells now maintain identity (Check 3 passes)"
echo ""

echo "=== Pulling latest changes ==="
git pull origin main
echo ""

for seed in 5000 5100 5200; do
    echo "=========================================================================="
    echo "Running seed $seed with realistic RunContext factors..."
    echo "=========================================================================="

    PYTHONPATH=$PWD:$PYTHONPATH timeout 600 python3 scripts/run_v4_phase1.py --seeds $seed

    if [ $? -eq 0 ]; then
        echo "✅ Seed $seed complete"
    else
        echo "❌ Seed $seed failed"
    fi
    echo ""
done

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                    RUNNING FULL VALIDATION                                   ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

PYTHONPATH=$PWD:$PYTHONPATH python3 scripts/validate_structured_noise.py 5000 5100 5200

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                           EXPECTED RESULTS                                   ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Check 1: Vehicle CV: 8-12% ✅ (should still pass)"
echo "Check 2: Channel correlations: ER-Mito > 0.3, Nucleus-Actin > 0.2 ✅"
echo "Check 3: Well persistence: <15% CV ✅ (SHOULD NOW PASS!)"
echo "Check 4: Fingerprints: stain/focus signatures ✅"
echo ""
echo "Success = All 4 checks pass → Wells have identity → Agent can learn trust"
