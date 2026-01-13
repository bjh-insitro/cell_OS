#!/bin/bash

# Test each unit test file individually to find hanging tests
PYTHONPATH=/Users/bjh/cell_OS:$PYTHONPATH
export PYTHONPATH

OUTPUT_FILE="unit_test_results.txt"
TIMEOUT_SECONDS=45

echo "=== Testing Unit Test Files ===" > "$OUTPUT_FILE"
echo "Started: $(date)" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

cd /Users/bjh/cell_OS

for test_file in tests/unit/test_*.py; do
    basename_file=$(basename "$test_file")
    echo -n "Testing: $basename_file ... "

    # Run test in background
    pytest "$test_file" -q --tb=no > /tmp/test_output.txt 2>&1 &
    TEST_PID=$!

    # Wait for completion or timeout
    ELAPSED=0
    while kill -0 $TEST_PID 2>/dev/null && [ $ELAPSED -lt $TIMEOUT_SECONDS ]; do
        sleep 1
        ELAPSED=$((ELAPSED + 1))
    done

    if kill -0 $TEST_PID 2>/dev/null; then
        echo "❌ HUNG (killed after ${TIMEOUT_SECONDS}s)"
        echo "$basename_file: HUNG" >> "$OUTPUT_FILE"
        kill -9 $TEST_PID 2>/dev/null
    else
        RESULT=$(tail -1 /tmp/test_output.txt)
        if [ $ELAPSED -gt 15 ]; then
            echo "⚠️  SLOW (${ELAPSED}s)"
            echo "$basename_file: SLOW (${ELAPSED}s) - $RESULT" >> "$OUTPUT_FILE"
        else
            echo "✅ OK (${ELAPSED}s)"
            echo "$basename_file: OK (${ELAPSED}s) - $RESULT" >> "$OUTPUT_FILE"
        fi
    fi
done

echo "" >> "$OUTPUT_FILE"
echo "Completed: $(date)" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "=== Summary ===" >> "$OUTPUT_FILE"
echo -n "Hung: " >> "$OUTPUT_FILE"
grep -c "HUNG" "$OUTPUT_FILE" >> "$OUTPUT_FILE"
echo -n "Slow: " >> "$OUTPUT_FILE"
grep -c "SLOW" "$OUTPUT_FILE" >> "$OUTPUT_FILE"
echo -n "OK: " >> "$OUTPUT_FILE"
grep -c "OK" "$OUTPUT_FILE" >> "$OUTPUT_FILE"

echo ""
echo "Results written to: $OUTPUT_FILE"
cat "$OUTPUT_FILE"
