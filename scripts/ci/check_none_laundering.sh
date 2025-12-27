#!/bin/bash
# CI Guard: Detect None-laundering patterns in aggregation code
#
# This script prevents future reintroduction of silent None → 0.0 conversions
# that would nullify SNR policy enforcement.
#
# Exit codes:
#   0 = No laundering patterns detected (safe)
#   1 = Laundering patterns found (fail CI)
#
# Run in CI before merge to main.

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "🔍 Checking for None-laundering patterns in aggregation code..."
echo ""

VIOLATIONS=0

# Pattern 1: .get(morphology_key, 0.0) - direct laundering
echo "Checking for .get(..., 0.0) on morphology channels..."
if git grep -n "\.get(['\"]\\(er\\|mito\\|nucleus\\|actin\\|rna\\)['\"],\s*0\.0)" src/cell_os/epistemic_agent/observation_aggregator.py 2>/dev/null; then
    echo -e "${RED}❌ VIOLATION: Found .get(morphology_channel, 0.0) pattern${NC}"
    echo "   This converts None → 0.0 silently, nullifying SNR policy."
    echo "   Use: morph.get('er', None) or morph.get('er')"
    echo ""
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo -e "${GREEN}✓ No .get(..., 0.0) laundering detected${NC}"
fi

# Pattern 2: "or 0.0" on channel values
echo ""
echo "Checking for 'or 0.0' operators on channel values..."
if git grep -n "\(feature_means\|feature_stds\|morphology\)\[['\"][a-z_]*['\"]\]\s*or\s*0\.0" src/cell_os/epistemic_agent/ 2>/dev/null; then
    echo -e "${RED}❌ VIOLATION: Found 'channel_value or 0.0' pattern${NC}"
    echo "   This converts None → 0.0 silently, nullifying SNR policy."
    echo "   Use: if value is not None: use(value)"
    echo ""
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo -e "${GREEN}✓ No 'or 0.0' laundering detected${NC}"
fi

# Pattern 3: np.nan_to_num near aggregation
echo ""
echo "Checking for np.nan_to_num in aggregation code..."
if git grep -n "np\.nan_to_num" src/cell_os/epistemic_agent/observation_aggregator.py 2>/dev/null; then
    echo -e "${YELLOW}⚠️  WARNING: Found np.nan_to_num in aggregation code${NC}"
    echo "   This may convert None/NaN to 0.0. Verify it's not laundering masked channels."
    echo "   If intentional, add comment: '# Intentional: not morphology channels'"
    echo ""
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo -e "${GREEN}✓ No np.nan_to_num detected in aggregation${NC}"
fi

# Pattern 4: fillna on morphology DataFrames
echo ""
echo "Checking for .fillna(0) on morphology data..."
if git grep -n "\.fillna(0)" src/cell_os/epistemic_agent/observation_aggregator.py 2>/dev/null; then
    echo -e "${RED}❌ VIOLATION: Found .fillna(0) in aggregation code${NC}"
    echo "   This converts None/NaN → 0 silently, nullifying SNR policy."
    echo "   Use: .dropna() or explicit None handling"
    echo ""
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo -e "${GREEN}✓ No .fillna(0) laundering detected${NC}"
fi

# Pattern 5: Default argument values on morphology extraction
echo ""
echo "Checking for default=0.0 in morphology extraction..."
if git grep -n "readouts\[.morphology.\]\.get.*,\s*0\." src/cell_os/epistemic_agent/observation_aggregator.py 2>/dev/null; then
    echo -e "${RED}❌ VIOLATION: Found default=0.0 in morphology readout extraction${NC}"
    echo "   This converts None → 0.0 silently at ingestion."
    echo "   Use: readouts['morphology'].get(key, None)"
    echo ""
    VIOLATIONS=$((VIOLATIONS + 1))
else
    echo -e "${GREEN}✓ No default=0.0 in morphology extraction${NC}"
fi

# Summary
echo ""
echo "═══════════════════════════════════════════════════════════"
if [ $VIOLATIONS -eq 0 ]; then
    echo -e "${GREEN}✅ PASS: No None-laundering patterns detected${NC}"
    echo ""
    echo "SNR policy enforcement is intact. Masked channels stay None."
    exit 0
else
    echo -e "${RED}❌ FAIL: Found $VIOLATIONS potential laundering pattern(s)${NC}"
    echo ""
    echo "One or more patterns that convert None → 0.0 were detected."
    echo "These patterns would nullify SNR policy enforcement."
    echo ""
    echo "Review the violations above and either:"
    echo "  1. Fix the laundering (replace with explicit None handling)"
    echo "  2. If false positive, update this script's patterns"
    echo ""
    echo "See: SNR_DOWNSTREAM_AUDIT_CHECKLIST.md for safe patterns"
    exit 1
fi
