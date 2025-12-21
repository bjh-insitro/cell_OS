# Running 5-Seed Governance Test on JH

## Prerequisites

1. **Python 3.13** (or compatible version with the codebase)
2. **Required packages** (check requirements.txt or pyproject.toml)
3. **Git** (to sync the latest changes)

## Step 1: Sync Code to JH

### Option A: Git Push/Pull (Recommended)
```bash
# On this machine (bjh laptop):
cd /Users/bjh/cell_OS
git add -A
git commit -m "feat: optimize beam search - calibrator caching and reduced action space"
git push origin main

# On JH machine:
cd <path_to_cell_OS>
git pull origin main
```

### Option B: Direct File Transfer
```bash
# On this machine, rsync modified files to JH:
rsync -av --include='*.py' \
    /Users/bjh/cell_OS/src/cell_os/hardware/beam_search.py \
    /Users/bjh/cell_OS/src/cell_os/hardware/confidence_calibrator.py \
    /Users/bjh/cell_OS/test_5seed_governance.py \
    jh:<path_to_cell_OS>/
```

## Step 2: Verify Required Files Exist on JH

Ensure these files are present:
- `data/confidence_calibrator_v1.pkl` (required by beam search)
- `src/cell_os/hardware/masked_compound_phase5.py` (PHASE5_LIBRARY)
- `src/cell_os/hardware/beam_search.py` (modified with caching)
- `src/cell_os/hardware/confidence_calibrator.py` (modified with silent loading)
- `test_5seed_governance.py` (the test script)

## Step 3: Check Python Environment

```bash
# On JH machine:
cd <path_to_cell_OS>

# Verify Python version
python3 --version  # Should be 3.10+

# Test imports
python3 -c "
from src.cell_os.hardware.beam_search import BeamSearch
from src.cell_os.hardware.confidence_calibrator import ConfidenceCalibrator
print('✓ Imports successful')
"
```

## Step 4: Run the Test

```bash
# On JH machine:
cd <path_to_cell_OS>

# Run with timing
time PYTHONPATH=. python3 test_5seed_governance.py

# Or run in background with output saved
nohup python3 test_5seed_governance.py > test_5seed_output.log 2>&1 &

# Monitor progress
tail -f test_5seed_output.log
```

## Step 5: Review Results

Expected output format:
```
5-Seed Governance Check (Optimized)
====================================================================================================
Seed   Terminal        Time_h   Nuisance   Posterior  Cal_Conf   Correct  Reason
====================================================================================================
0      HORIZON_END     48.0     0.225      0.734      0.962      False    reached_horizon
1      HORIZON_END     48.0     0.120      0.867      0.978      False    reached_horizon
...
====================================================================================================

✓ No pathologies detected

Summary:
  HORIZON_END: 5/5
  Correct predictions: X/5
```

## Key Metrics to Check

1. **No pathologies detected** - Governance constraints respected
2. **Terminal type distribution** - Should all be HORIZON_END (48h)
3. **Calibrated confidence** - High confidence predictions
4. **Correctness** - Whether predictions match true mechanism (ER stress)
5. **Posterior vs Calibrated Conf** - Calibration effectiveness

## Performance Optimizations Applied

- **Calibrator caching**: Loads once per seed instead of 100+ times
- **Reduced dose levels**: [0.0, 0.5, 1.0] instead of 4 levels
- **Silent loading**: No verbose log spam

Expected runtime on JH: **10-15 minutes** (vs 25+ minutes on laptop)

## Troubleshooting

### If calibrator file not found:
```bash
# Check if file exists
ls -lh data/confidence_calibrator_v1.pkl

# If missing, may need to copy from laptop or regenerate
```

### If imports fail:
```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH=/path/to/cell_OS:$PYTHONPATH

# Or use absolute imports
```

### If test hangs:
```bash
# Check process is running
ps aux | grep test_5seed_governance

# Check memory usage
top -p <pid>

# Cancel if needed
pkill -f test_5seed_governance.py
```

## Post-Run: Retrieve Results

```bash
# On this machine, copy results back:
scp jh:<path_to_cell_OS>/test_5seed_output.log ~/Downloads/

# Or if using git:
# On JH, commit results to a branch
git checkout -b results/5seed-governance-$(date +%Y%m%d)
git add test_5seed_output.log
git commit -m "results: 5-seed governance check"
git push origin HEAD
```
