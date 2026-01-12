#!/bin/bash

# =================================================================
#  Plate Generator Launcher
#  
#  1. Edit the "Configuration" section below.
#  2. Run this script: ./scripts/run_plate_generator.sh
# =================================================================

# --- Configuration -----------------------------------------------

# Output Location
OUTPUT_FILE="data/designs/Experiment_001/design.json"

# Plate Settings
FORMAT=384               # 96 or 384
NUM_PLATES=1             # Number of replicate plates
INCLUDE_EDGES=true       # true or false (lowercase)

# Experiment Details
# Note: Use space separation for arrays
CELL_LINES=("A549" "HepG2")
COMPOUNDS=("tunicamycin" "oligomycin")
SEEDING_DENSITIES=(2000 4000)

# Dose Settings
START_DOSE=10.0
DILUTION_FACTOR=3.0
NUM_DOSES=6
REPS=8
VEHICLE_REPS=12

# --- Execution Logic (Do not edit below) -------------------------

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$(dirname "$DIR")"

# Construct the edge flag
EDGE_FLAG=""
if [ "$INCLUDE_EDGES" = "true" ]; then
    EDGE_FLAG="--include-edges"
fi

echo "🚀 Launching Plate Generator..."
echo "   Output: $OUTPUT_FILE"
echo "   Format: $FORMAT-well"

# Run the python script
python3 "$REPO_ROOT/scripts/generate_custom_plate.py" \
  --output "$OUTPUT_FILE" \
  --format "$FORMAT" \
  --num-plates "$NUM_PLATES" \
  $EDGE_FLAG \
  --cell-lines "${CELL_LINES[@]}" \
  --compounds "${COMPOUNDS[@]}" \
  --seeding-densities "${SEEDING_DENSITIES[@]}" \
  --start-dose "$START_DOSE" \
  --dilution-factor "$DILUTION_FACTOR" \
  --num-doses "$NUM_DOSES" \
  --reps "$REPS" \
  --vehicle-reps "$VEHICLE_REPS"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Done!"
else
    echo "❌ Error: Script failed with exit code $EXIT_CODE"
fi
