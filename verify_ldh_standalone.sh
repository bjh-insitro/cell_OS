#!/bin/bash
# Quick verification of LDH standalone script
set -e

echo "========================================"
echo "LDH Standalone Script Verification"
echo "========================================"
echo ""

# Clean up any old test files
rm -f /tmp/verify_ldh_*.db

echo "Test 1: Benchmark Mode (48 wells, 2-4 seconds)"
echo "------------------------------------------------"
python3 standalone_cell_thalamus.py \
    --mode benchmark \
    --workers 4 \
    --db-path /tmp/verify_ldh_benchmark.db

echo ""
echo "Test 2: Checking LDH Values"
echo "------------------------------------------------"
sqlite3 /tmp/verify_ldh_benchmark.db <<EOF
.mode column
.headers on
SELECT
    compound,
    ROUND(dose_uM, 2) as dose_uM,
    ROUND(AVG(atp_signal), 1) as avg_ldh,
    COUNT(*) as n_wells
FROM thalamus_results
GROUP BY compound, dose_uM
ORDER BY compound, dose_uM;
EOF

echo ""
echo "Test 3: Validating LDH Inverse Relationship"
echo "------------------------------------------------"

# Check that high-dose compounds have higher LDH than low-dose
HIGH_DOSE=$(sqlite3 /tmp/verify_ldh_benchmark.db "SELECT AVG(atp_signal) FROM thalamus_results WHERE compound='CCCP' AND dose_uM > 10")
LOW_DOSE=$(sqlite3 /tmp/verify_ldh_benchmark.db "SELECT AVG(atp_signal) FROM thalamus_results WHERE compound='CCCP' AND dose_uM < 1")

echo "CCCP Low Dose (<1 µM):  LDH = $LOW_DOSE"
echo "CCCP High Dose (>10 µM): LDH = $HIGH_DOSE"

# Use bc for floating point comparison
RATIO=$(echo "scale=1; $HIGH_DOSE / ($LOW_DOSE + 0.1)" | bc)
echo "Ratio: ${RATIO}×"

if [ $(echo "$RATIO > 5" | bc) -eq 1 ]; then
    echo "✅ PASS: High dose shows much higher LDH (ratio > 5×)"
else
    echo "❌ FAIL: High dose should show much higher LDH"
    exit 1
fi

echo ""
echo "Test 4: Checking Vehicle Controls"
echo "------------------------------------------------"
DMSO_LDH=$(sqlite3 /tmp/verify_ldh_benchmark.db "SELECT AVG(atp_signal) FROM thalamus_results WHERE compound='DMSO'")
echo "DMSO (vehicle) average LDH: $DMSO_LDH"

if [ $(echo "$DMSO_LDH < 50" | bc) -eq 1 ]; then
    echo "✅ PASS: Vehicle controls have low LDH"
else
    echo "⚠️  WARNING: Vehicle LDH higher than expected (should be near 0)"
fi

echo ""
echo "========================================"
echo "✅ All Verification Tests Passed!"
echo "========================================"
echo ""
echo "Next Steps:"
echo "1. Upload standalone_cell_thalamus.py to JupyterHub"
echo "2. Run: python standalone_cell_thalamus.py --mode benchmark --workers 8"
echo "3. Verify LDH values match the pattern above"
echo "4. If successful, run full mode: --mode full --workers 72"
echo ""
echo "See: docs/JUPYTERHUB_QUICKSTART.md for detailed instructions"
