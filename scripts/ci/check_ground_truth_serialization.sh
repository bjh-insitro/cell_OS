#!/bin/bash
#
# CI enforcement: Check for forbidden direct vessel serialization patterns.
#
# These patterns risk leaking ground truth if someone adds a convenience
# serializer that dumps internal state without going through measurement contracts.
#
# Scope: src/ and scripts/ excluding tests/, demos/, archive/
# Fail: If any forbidden pattern is found
#
# Exceptions: scripts/demos/ and scripts/archive/ are development tools and may
# access ground truth for visualization or debugging. They must NEVER be exposed
# to agents.

set -euo pipefail

echo "=============================================="
echo "Ground Truth Serialization Check"
echo "=============================================="

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# Forbidden patterns that bypass measurement contracts
# Note: .dict() and .to_dict() are too broad (many legitimate uses on non-vessel objects)
# We only ban vessel-specific patterns
PATTERNS=(
    "vars(vessel"
    "vessel.__dict__"
    "asdict(vessel"
    "json.dump(vessel"
    "pd.DataFrame([vars(vessel)"
    "pd.DataFrame(vars(vessel)"
    "vessel.to_dict()"
    "vessel.dict()"
)

VIOLATIONS=0

for pattern in "${PATTERNS[@]}"; do
    echo ""
    echo "Checking pattern: $pattern"

    # Search in src/ and scripts/ excluding tests/, demos/, archive/
    MATCHES=$(grep -r --include="*.py" \
                   --exclude-dir=tests \
                   --exclude-dir=demos \
                   --exclude-dir=archive \
                   --exclude-dir=__pycache__ \
                   --exclude-dir=.pytest_cache \
                   -n "$pattern" src/ scripts/ 2>/dev/null || true)

    if [ -n "$MATCHES" ]; then
        echo "❌ VIOLATION: Found forbidden serialization pattern"
        echo "$MATCHES"
        VIOLATIONS=$((VIOLATIONS + 1))
    else
        echo "✅ Clean"
    fi
done

echo ""
echo "=============================================="

if [ $VIOLATIONS -gt 0 ]; then
    echo "❌ FAILED: Found $VIOLATIONS forbidden serialization pattern(s)"
    echo ""
    echo "These patterns bypass measurement contracts and risk leaking ground truth."
    echo "Use proper measurement APIs (vm.assays.*.measure()) instead."
    echo ""
    echo "If you need to serialize for debugging:"
    echo "  1. Create a _debug_truth dict with only necessary fields"
    echo "  2. Gate behind debug_truth_enabled flag"
    echo "  3. Never serialize full VesselState objects"
    echo ""
    echo "If this is a development/demo script:"
    echo "  1. Move to scripts/demos/ or scripts/archive/"
    echo "  2. Add explicit warning that it's NOT for agent use"
    echo "  3. Never expose these tools to agents"
    exit 1
else
    echo "✅ PASSED: No forbidden serialization patterns found"
    echo ""
    echo "Note: scripts/demos/ and scripts/archive/ are excluded (dev tools only)"
    exit 0
fi
