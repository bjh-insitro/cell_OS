#!/bin/bash
# Run v2 vs v3 comparison across 5 seeds

set -e

SEEDS=(42 123 456 789 1000)
V2_PLATE="validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v2.json"
V3_PLATE="validation_frontend/public/plate_designs/CAL_384_RULES_WORLD_v3.json"

echo "=========================================="
echo "V2 vs V3 Comparison (5 seeds)"
echo "=========================================="
echo ""

# Run V2
echo "Running V2 simulations..."
for seed in "${SEEDS[@]}"; do
    echo "  → V2 seed $seed"
    PYTHONPATH=. python3 src/cell_os/plate_executor_v2_parallel.py "$V2_PLATE" --seed "$seed" --auto-commit
done

echo ""
echo "Running V3 simulations..."
for seed in "${SEEDS[@]}"; do
    echo "  → V3 seed $seed"
    PYTHONPATH=. python3 src/cell_os/plate_executor_v2_parallel.py "$V3_PLATE" --seed "$seed" --auto-commit
done

echo ""
echo "=========================================="
echo "All simulations complete"
echo "=========================================="
echo ""
echo "Running comparison analysis..."
python3 scripts/compare_v2_v3_qc.py

echo ""
echo "✓ Done! Results in docs/V2_V3_COMPARISON_RESULTS.md"
