# JupyterHub Quickstart - Testing LDH Changes

Last Updated: December 16, 2025

**✅ RECOMMENDED APPROACH:** This is the current method for testing Cell Thalamus on AWS.

AWS Lambda deployment is blocked due to missing IAM permissions (see `AWS_LAMBDA_SETUP.md`). Use this manual JupyterHub workflow until permissions are granted.

---

## Quick Test Instructions

### 1. Copy Standalone Script to JupyterHub

**Option A: Direct Upload**
1. Open JupyterHub: https://[your-jupyterhub-url]
2. Upload `standalone_cell_thalamus.py` via the file browser
3. Upload `standalone_design_comparison.py` if testing design comparison

**Option B: Git Pull**
```bash
cd ~/cell_OS  # Or wherever you cloned the repo
git pull origin main
```

### 2. Install Dependencies

```bash
pip install --user numpy tqdm scipy
```

### 3. Run Quick Test (Benchmark Mode)

This runs a **fast 48-well test** to verify LDH simulation is working:

```bash
python standalone_cell_thalamus.py --mode benchmark --workers 8
```

**Expected output:**
```
======================================================================
PARALLEL CELL THALAMUS SIMULATION
======================================================================
Mode: benchmark
Workers: 8 CPUs
Total wells: 48
...
✓ SIMULATION COMPLETE!
Total time: 0.5s
Throughput: ~100 wells/sec
```

### 4. Verify LDH Values

```bash
sqlite3 cell_thalamus_results.db "
SELECT compound, dose_uM,
       ROUND(AVG(atp_signal), 1) as avg_ldh,
       COUNT(*) as n
FROM thalamus_results
GROUP BY compound, dose_uM
ORDER BY compound, dose_uM;
"
```

**Expected pattern:**
```
CCCP|0.0|0.0|2          ← Vehicle: no LDH
CCCP|0.5|400|2          ← Low dose: low LDH
CCCP|5.0|19000|2        ← Mid dose: moderate LDH
CCCP|50.0|40000|2       ← High dose: high LDH (cytotoxicity)
```

**Key validation:** LDH should **increase** with dose (inverse of viability).

### 5. Run Full Campaign (Optional)

For the complete 2,304-well Phase 0 screen:

```bash
# Use all CPUs (c5.18xlarge has 72 cores)
python standalone_cell_thalamus.py --mode full --workers 72
```

**Runtime:** ~5 minutes on c5.18xlarge

### 6. Download Results

If running on JupyterHub, download the DB:

```bash
# On JupyterHub: Copy to your home directory
cp cell_thalamus_results.db ~/

# Then download via JupyterHub file browser
# Or use scp if you have SSH access
```

On your Mac, place it in:
```bash
mv ~/Downloads/cell_thalamus_results.db /Users/bjh/cell_OS/data/
```

Then view at: http://localhost:5173/cell-thalamus

---

## What Changed in LDH Update

### Before (ATP):
- ATP signal = baseline × viability × metabolic_penalty
- **Problem:** CCCP/oligomycin crash ATP but cells survive
- **Problem:** Not orthogonal to Cell Painting

### After (LDH):
- LDH signal = baseline × (1 - viability)
- **Fix:** LDH only rises when cells die (membrane rupture)
- **Fix:** Orthogonal to Cell Painting (supernatant vs morphology)
- **Fix:** No mitochondrial confounding

### Key Test Cases

**Test 1: Inverse Relationship**
- Healthy cells (98% viability) → Low LDH (~5)
- Dying cells (2% viability) → High LDH (~250)
- Ratio: **50-80× higher** in dying cells ✅

**Test 2: Mitochondrial Compounds**
- CCCP 2 µM: 95% viability → Low LDH (~10)
- CCCP 20 µM: 70% viability → High LDH (~80)
- **No early ATP crash confounding** ✅

**Test 3: Dose-Response**
- Vehicle (0 µM) → 0 LDH
- Low dose → Low LDH
- High dose → High LDH
- **Monotonic relationship** ✅

---

## Troubleshooting

### Import Error: No module named 'numpy'
```bash
pip install --user numpy tqdm scipy
```

### Permission Denied
```bash
chmod +x standalone_cell_thalamus.py
```

### Out of Memory
Reduce workers:
```bash
python standalone_cell_thalamus.py --mode benchmark --workers 4
```

### Results Look Wrong
Check LDH values:
```bash
sqlite3 cell_thalamus_results.db "
SELECT MIN(atp_signal), MAX(atp_signal), AVG(atp_signal)
FROM thalamus_results;
"
```

Should see:
- MIN: ~0 (vehicle controls)
- MAX: ~50,000 (high cytotoxicity)
- AVG: ~5,000-15,000

---

## Next Steps: AWS Lambda Setup

Once testing is verified on JupyterHub, set up automated Lambda execution:

1. **Create IAM Role** (requires admin):
   - Follow `docs/AWS_LAMBDA_SETUP.md`
   - Grants Lambda → S3 write permissions

2. **Deploy Lambda**:
   ```bash
   ./scripts/deploy_lambda.sh
   ```

3. **Enable in Backend**:
   ```bash
   export USE_LAMBDA=true
   cd src/cell_os/api
   uvicorn thalamus_api:app --reload
   ```

4. **Test from Frontend**:
   - Open: http://localhost:5173/autonomous-loop-tutorial
   - Click "Run Real Experiment"
   - Results appear automatically via S3 sync

---

## Contact

If you hit issues, check:
- `test_ldh_simulation.py` - Comprehensive test suite
- `docs/AWS_LAMBDA_SETUP.md` - Lambda deployment guide
- `docs/IAM_ROLE_REQUEST.md` - IAM permissions needed
