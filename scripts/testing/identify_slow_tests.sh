#!/bin/bash

# Script to identify slow/hanging tests in phase6a
# Tests each file individually with background execution and monitoring

PYTHONPATH=/Users/bjh/cell_OS:$PYTHONPATH
export PYTHONPATH

OUTPUT_FILE="slow_tests_results.txt"
TIMEOUT_SECONDS=30

echo "=== Testing Phase6a Files ===" > "$OUTPUT_FILE"
echo "Started: $(date)" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

cd /Users/bjh/cell_OS

for test_file in tests/phase6a/test_*.py; do
    echo "Testing: $test_file"
    echo "---" >> "$OUTPUT_FILE"
    echo "File: $test_file" >> "$OUTPUT_FILE"

    # Run test in background with output redirected
    pytest "$test_file" -q --tb=no > /tmp/test_output.txt 2>&1 &
    TEST_PID=$!

    # Wait for test to complete or timeout
    ELAPSED=0
    while kill -0 $TEST_PID 2>/dev/null && [ $ELAPSED -lt $TIMEOUT_SECONDS ]; do
        sleep 1
        ELAPSED=$((ELAPSED + 1))
    done

    # Check if test is still running (hung)
    if kill -0 $TEST_PID 2>/dev/null; then
        echo "Status: HUNG (killed after ${TIMEOUT_SECONDS}s)" >> "$OUTPUT_FILE"
        echo "  ❌ HUNG: $test_file"
        kill -9 $TEST_PID 2>/dev/null
    else
        # Test completed
        RESULT=$(tail -1 /tmp/test_output.txt)
        if [ $ELAPSED -gt 10 ]; then
            echo "Status: SLOW (${ELAPSED}s)" >> "$OUTPUT_FILE"
            echo "  ⚠️  SLOW (${ELAPSED}s): $test_file"
        else
            echo "Status: OK (${ELAPSED}s)" >> "$OUTPUT_FILE"
            echo "  ✅ OK (${ELAPSED}s): $test_file"
        fi
        echo "Result: $RESULT" >> "$OUTPUT_FILE"
    fi
    echo "" >> "$OUTPUT_FILE"
done

echo "" >> "$OUTPUT_FILE"
echo "Completed: $(date)" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "=== Summary ===" >> "$OUTPUT_FILE"
grep -c "HUNG" "$OUTPUT_FILE" >> "$OUTPUT_FILE" && echo " files hung" >> "$OUTPUT_FILE"
grep -c "SLOW" "$OUTPUT_FILE" >> "$OUTPUT_FILE" && echo " files slow" >> "$OUTPUT_FILE"

echo ""
echo "Results written to: $OUTPUT_FILE"
