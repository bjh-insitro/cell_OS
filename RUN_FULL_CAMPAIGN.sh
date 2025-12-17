#!/bin/bash
# Full Cell Thalamus Campaign on JupyterHub
# Run this on JupyterHub to execute the complete Phase 0 screen
# Expected runtime: ~5 minutes on c5.18xlarge (72 cores)

echo "========================================"
echo "Cell Thalamus Phase 0 Full Campaign"
echo "========================================"
echo ""
echo "Configuration:"
echo "  - 2 cell lines (A549, HepG2)"
echo "  - 10 compounds (tBHQ, H2O2, tunicamycin, thapsigargin, CCCP, oligomycin, etoposide, MG132, nocodazole, paclitaxel)"
echo "  - 4 doses per compound (0×, 0.1×, 1×, 10× EC50)"
echo "  - 2 timepoints (12h, 48h)"
echo "  - 2 days × 2 operators × 3 replicates"
echo "  - Total: 2,304 wells"
echo ""
echo "Expected runtime: ~5 minutes on c5.18xlarge"
echo ""
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

python standalone_cell_thalamus.py --mode full --workers 72

echo ""
echo "========================================"
echo "✅ Campaign Complete!"
echo "========================================"
echo ""
echo "Results automatically uploaded to S3"
echo ""
echo "Next steps on your Mac:"
echo "  1. Download results: ./scripts/sync_aws_db.sh"
echo "  2. Start backend: npm run api"
echo "  3. View dashboard: http://localhost:5173/cell-thalamus"
echo ""
