# Cell OS - Quick Start

**Get running in 2 minutes.**

---

## Prerequisites

- Python 3.9+ (you're using 3.13)
- Node.js 18+ (for frontend)
- `cell_thalamus.db` database file (see "Getting Data" below)

---

## 1. Install Dependencies

```bash
# Python backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .

# Frontend
cd frontend
npm install
cd ..
```

---

## 2. Start the System

**Terminal 1 - Backend API:**
```bash
python -m uvicorn src.cell_os.api.thalamus_api:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend Dashboard:**
```bash
cd frontend
npm run dev
```

**Dashboard URL:** http://localhost:5173

That's it! The Cell Thalamus dashboard should now be running.

---

## 3. Getting Data

### Option A: Use Existing Local Database
If you have `cell_thalamus.db` in the project root, you're done. The API will find it automatically.

### Option B: Sync from AWS S3 (if you ran campaigns on JupyterHub)
```bash
./scripts/sync_aws_db.sh
```

This downloads the latest `cell_thalamus.db` from S3.

### Option C: Run a New Simulation Locally
Use the dashboard:
1. Go to "Run Simulation" tab
2. Select mode: Demo (8 wells), Quick (96 wells), or Full (2,304 wells)
3. Click "Run Simulation"
4. Wait ~30 seconds (Demo) to ~5 minutes (Full)

---

## 4. Explore the Dashboard

**Available Tabs:**

| Tab | What It Shows |
|-----|---------------|
| **Run Simulation** | Start new Cell Thalamus experiments |
| **Experiments** | Browse all completed designs |
| **Dose-Response** | Interactive dose-response curves (log scale, multi-timepoint) |
| **Morphology Manifold** | PCA visualization of cell morphology changes |
| **Variance Analysis** | Statistical quality control, identify outliers |
| **Mechanism Recovery** | 🔬 Phase 0 key finding: mid-dose 12h = 300× better separation |
| **Sentinel Monitor** | SPC charts for DMSO control wells (batch effect detection) |
| **Plate Viewer** | 96/384-well plate heatmaps |

---

## 5. Common Tasks

### View Results from Latest Run
1. Dashboard → "Experiments" tab
2. Top row = most recent design
3. Click any design to set as active
4. Switch to other tabs to analyze that design

### Run Full Phase 0 Screen (Local)
```bash
python standalone_cell_thalamus.py --mode full --workers 8
```

**Result:** 2,304 wells, ~10 minutes on 8 cores (MacBook Pro)

### Run Full Phase 0 Screen (JupyterHub - 72 cores)
```bash
./RUN_FULL_CAMPAIGN.sh
```

**Result:** 2,304 wells, ~5 minutes on c5.18xlarge

After JupyterHub run completes, sync data to your Mac:
```bash
./scripts/sync_aws_db.sh
```

---

## 6. Troubleshooting

### "No designs found" in dashboard
- Check backend logs: is `cell_thalamus.db` found?
- Run a Demo simulation to populate the database
- Or sync from S3: `./scripts/sync_aws_db.sh`

### Frontend won't start
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Backend crashes on startup
```bash
# Check if port 8000 is already in use
lsof -i :8000
kill -9 <PID>
```

### Database out of sync with S3
```bash
# Force download latest from S3
./scripts/sync_aws_db.sh
```

---

## 7. Next Steps

**Just exploring?**
- Read `docs/CONTEXT.md` for architecture overview
- Check `TODO.md` for current priorities

**Want to understand the science?**
- Dashboard → "Mechanism Recovery" tab
- See the 300× separation improvement at mid-dose 12h
- Read the explainer in the tab (shows image → score pipeline)

**Want to build Phase 1 agent?**
- See `TODO.md` → "Phase 1: Epistemic Agency"
- Start with agent API design (query simulation with budgets)

**Want to run autonomous loops?**
- See `docs/guides/USER_GUIDE.md` for YAML config examples
- Run: `cell-os-run --config config/campaign_example.yaml`

---

## Key Files Reference

```
cell_OS/
├── src/cell_os/
│   ├── api/thalamus_api.py          # FastAPI backend (start with uvicorn)
│   ├── modeling.py                  # Simulation logic (generate_experimental_results)
│   └── database/cell_thalamus_db.py # SQLite database interface
├── frontend/
│   └── src/pages/CellThalamus/      # React dashboard components
├── cell_thalamus.db                 # SQLite database (auto-created or synced)
├── standalone_cell_thalamus.py      # Run simulations without API
└── scripts/
    ├── sync_aws_db.sh               # Download latest DB from S3
    └── watch_s3_db.sh               # Auto-sync DB when S3 updates
```

---

## Quick Commands Cheatsheet

```bash
# Start backend
python -m uvicorn src.cell_os.api.thalamus_api:app --reload

# Start frontend
cd frontend && npm run dev

# Sync database from AWS
./scripts/sync_aws_db.sh

# Run local simulation (CLI)
python standalone_cell_thalamus.py --mode demo

# Run JupyterHub campaign
./RUN_FULL_CAMPAIGN.sh

# View logs (if running in background)
tail -f /tmp/vite.log  # Frontend logs
# Backend logs print to stdout
```

---

**Need help?** See `docs/CONTEXT.md` or check `TODO.md` for current work.
