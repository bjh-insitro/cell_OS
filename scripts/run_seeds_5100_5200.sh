#!/bin/bash
# Run seeds 5100 and 5200 to test well persistence across runs

set -e

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║              RUN SEEDS 5100, 5200 FOR WELL PERSISTENCE TEST                 ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Check 3: Cross-seed well identity persistence"
echo "  - Same well (e.g., D4) should have similar morphology across seeds"
echo "  - Per-well biology is deterministic (keyed by well_position + cell_line)"
echo "  - Expected within-well CV < 15% across seeds"
echo ""

echo "Seed 5000: ✅ Clean (mean CV 7.9%)"
echo "Seed 5100: Running..."
echo "Seed 5200: Running..."
echo ""

for seed in 5100 5200; do
    echo "=========================================================================="
    echo "Running seed $seed..."
    echo "=========================================================================="

    PYTHONPATH=$PWD:$PYTHONPATH timeout 600 python3 scripts/run_v4_phase1.py --seeds $seed

    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Seed $seed complete"
        echo ""
        echo "Checking if clean..."
        python3 scripts/check_seed_clean.py $seed

        if [ $? -ne 0 ]; then
            echo ""
            echo "⚠️  Seed $seed contaminated - but continuing for persistence test"
            echo "   (We can still check persistence on clean wells)"
        fi
    else
        echo "❌ Seed $seed failed to execute"
    fi
    echo ""
done

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                         SEEDS COMPLETE                                       ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Now run full validation with all 3 seeds:"
echo "  PYTHONPATH=\$PWD:\$PYTHONPATH python3 scripts/validate_structured_noise.py 5000 5100 5200"
echo ""
echo "This will test Check 3: Well persistence across seeds"
