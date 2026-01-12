---
description: Generate custom plate designs. Edit the "Active Configuration" section and type /generate_plate_design to execute.
---

# Generate Custom Plate Designs

**How to use this file:**
1.  **Edit** the parameters in the **Active Configuration** block below.
2.  **Save** the file.
3.  **Type** `/generate_plate_design` in the chat.
4.  The agent will read your configuration and execute the script.

---

## ✅ Active Configuration

**Edit this block to define your current experiment:**

```bash
# Output Location
OUTPUT_FILE="data/designs/Experiment_001/design.json"

# Plate Settings
FORMAT=384               # 96 or 384
NUM_PLATES=1             # Number of replicate plates
INCLUDE_EDGES=true       # true or false (lowercase)
USE_SCAFFOLD=false       # true or false (lowercase)

# Experiment Details
CELL_LINES=("A549" "HepG2")
COMPOUNDS=("tunicamycin" "oligomycin")
SEEDING_DENSITIES=(2000 4000)

# Control Settings
VEHICLES=("DMSO" "aqueous")
VEHICLE_REPS=12          # Replicates per vehicle type

# Dose Settings
# List of start doses (one per cell line/compound)
START_DOSES=(10.0 1.0) 
DILUTION_FACTOR=3.0
NUM_DOSES=6
REPS=8

# ---------------------------------------------------------
# DO NOT EDIT BELOW THIS LINE (Command Construction)
# ---------------------------------------------------------

# Construct flags
EDGE_FLAG=""
if [ "$INCLUDE_EDGES" = "true" ]; then
    EDGE_FLAG="--include-edges"
fi

SCAFFOLD_FLAG=""
if [ "$USE_SCAFFOLD" = "true" ]; then
    SCAFFOLD_FLAG="--scaffold"
fi

# Run the generator
python3 scripts/generate_custom_plate.py \
  --output "$OUTPUT_FILE" \
  --format "$FORMAT" \
  --num-plates "$NUM_PLATES" \
  $EDGE_FLAG \
  $SCAFFOLD_FLAG \
  --cell-lines "${CELL_LINES[@]}" \
  --compounds "${COMPOUNDS[@]}" \
  --seeding-densities "${SEEDING_DENSITIES[@]}" \
  --vehicles "${VEHICLES[@]}" \
  --vehicle-reps "$VEHICLE_REPS" \
  --start-doses "${START_DOSES[@]}" \
  --dilution-factor "$DILUTION_FACTOR" \
  --num-doses "$NUM_DOSES" \
  --reps "$REPS"
```

---

## 📚 Examples & Reference

### 96-Well Basic
```bash
python3 scripts/generate_custom_plate.py \
  --output data/designs/basic_96.json \
  --format 96 \
  --cell-lines A549 \
  --compounds DMSO \
  --start-dose 10.0 \
  --dilution-factor 3.0 \
  --num-doses 6
```

### 384-Well Advanced (Mixed Doses & Vehicles)
```bash
python3 scripts/generate_custom_plate.py \
  --output data/designs/advanced_384.json \
  --format 384 \
  --num-plates 3 \
  --include-edges \
  --scaffold \
  --cell-lines A549 HepG2 \
  --compounds tunicamycin oligomycin \
  --seeding-densities 2000 4000 \
  --vehicles DMSO aqueous \
  --start-doses 30.0 1.0 \
  --dilution-factor 3.0 \
  --num-doses 6
```
