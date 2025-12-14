# Standalone Cell Thalamus - Quick Start

Run Cell Thalamus on JupyterHub with just **one file** - no repo clone needed!

## Quick Start (3 steps)

### 1. Upload File to JupyterHub

1. Go to [jupyterhub.aws.insitro.com](https://jupyterhub.aws.insitro.com)
2. Create server: **32-64 vCPUs**, 16-32 GB RAM, `scipy-notebook` image
3. Upload `standalone_cell_thalamus.py` via file browser

### 2. Install Dependencies

Open a terminal:

```bash
pip install numpy pyyaml tqdm
```

That's it! Only 3 lightweight packages needed.

### 3. Run Simulation

```bash
# Full campaign (2304 wells) with all available CPUs
python standalone_cell_thalamus.py --mode full

# Or specify worker count
python standalone_cell_thalamus.py --mode full --workers 64

# Quick demo (4 wells, ~10 seconds)
python standalone_cell_thalamus.py --mode demo --workers 4
```

## What You Get

**Full mode (2304 wells):**
- **16 CPUs**: ~4.5 minutes
- **32 CPUs**: ~2.2 minutes
- **64 CPUs**: ~1.1 minutes

vs. local serial execution: ~2 hours

**Output:**
- SQLite database with all results: `cell_thalamus_results.db`
- 2304 rows × 17 columns (well metadata + 5 morphology channels + ATP)

## View Results

```python
import sqlite3
import pandas as pd

# Load results
conn = sqlite3.connect('cell_thalamus_results.db')
df = pd.read_sql('SELECT * FROM results', conn)
conn.close()

# Summary
print(f"Total wells: {len(df)}")
print(f"Cell lines: {df['cell_line'].unique()}")
print(f"Compounds: {df['compound'].unique()}")

# Export
df.to_csv('results.csv', index=False)
```

## Customize

Edit the file to change:

**Cell lines** (line ~280):
```python
cell_lines = ['A549', 'HepG2', 'U2OS']  # Add your cell lines
```

**Compounds** (line ~282):
```python
compounds = ['tBHQ', 'tunicamycin']  # Use fewer compounds
```

**Design** (line ~130):
```python
doses = [0.1, 1.0, 10.0]  # Change dose levels
timepoints = [12.0, 48.0, 72.0]  # Add timepoints
```

## File Size

- Script: ~13 KB
- Database (2304 wells): ~250 KB
- Total storage: <1 MB

Compare to full repo: ~100 MB with git history

## Troubleshooting

**Import error:**
```bash
pip install numpy pyyaml tqdm
```

**Out of memory:**
- Increase server memory to 32 GB
- Or reduce workers: `--workers 16`

**Slow performance:**
- Check CPU allocation in server settings
- View usage: [grafana dashboard](https://grafana.aws.insitro.com)

## Next Steps

Once you verify it works, you can:
1. Customize the simulation parameters
2. Add your own analysis code
3. Export results to `/home/shared` for team access
4. Run multiple designs in parallel on different named servers

---

Questions? Reach out to #compute-core on Slack.
