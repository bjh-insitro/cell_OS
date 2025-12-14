# Cell Thalamus on JupyterHub

## Overview

Run the full Cell Thalamus Phase 0 simulation (2304 wells) in **~2 minutes** using parallel processing on JupyterHub.

**Performance Comparison:**
- Local (1 CPU): ~111 minutes (1.8 hours)
- JupyterHub (16 CPUs): ~4.5 minutes
- JupyterHub (32 CPUs): ~2.2 minutes
- JupyterHub (64 CPUs): ~1.1 minutes

**Speedup: 50-100x faster!**

---

## Setup on JupyterHub

### 1. Access JupyterHub

Go to [jupyterhub.aws.insitro.com](https://jupyterhub.aws.insitro.com) and log in with Okta.

### 2. Create Server

**Recommended Settings:**
- **Image**: `ijupyterhub-scipy-notebook:latest`
- **CPU**: 32-64 vCPUs (more = faster)
- **Memory**: 16-32 GB

For the full 2304-well campaign, we recommend at least 32 vCPUs.

### 3. Upload Code

Once your server starts, open a terminal and clone your repository:

```bash
cd /home/jovyan
git clone <your-repo-url> cell_OS
cd cell_OS
```

Or upload the code files directly via the JupyterLab file browser.

### 4. Install Package

```bash
pip install -e .
```

This installs `cell_os` in editable mode with all dependencies.

---

## Running the Simulation

### Option A: Jupyter Notebook (Recommended)

1. Open `notebooks/cell_thalamus_jupyterhub.ipynb`
2. Run all cells
3. Results are saved to your home directory

The notebook includes:
- Automatic CPU detection
- Progress updates every 100 wells
- Summary statistics
- Quick visualizations
- CSV export

### Option B: Command Line

Run from terminal:

```bash
# Full campaign with all available CPUs
python -m cell_os.cell_thalamus.parallel_runner --mode full

# Specify number of workers
python -m cell_os.cell_thalamus.parallel_runner --mode full --workers 32

# Quick test (fewer wells)
python -m cell_os.cell_thalamus.parallel_runner --mode quick --workers 16

# Demo mode (4 wells, very fast)
python -m cell_os.cell_thalamus.parallel_runner --mode demo
```

---

## Understanding the Output

### Progress Updates

```
Progress: 100/2304 wells (4.3%) - Rate: 52.3 wells/sec - ETA: 42.1s
Progress: 200/2304 wells (8.7%) - Rate: 51.8 wells/sec - ETA: 40.6s
...
```

### Final Statistics

```
✓ PARALLEL SIMULATION COMPLETE!
======================================================================
Total wells: 2304
Successful results: 2304
Total time: 132.45 seconds (2.21 minutes)
Time per well: 0.057 seconds
Throughput: 17.4 wells/second
Speedup: 50.7x vs serial
Design ID: 6b814d41-5505-406e-8fe1-59fc1578f49a
Database: /home/jovyan/cell_thalamus_results.db
======================================================================
```

---

## Results and Analysis

### Database Location

Results are saved to SQLite database:
- Default: `/home/jovyan/cell_thalamus_results.db`
- This persists in your home directory across sessions

### Loading Results

```python
from cell_os.database.cell_thalamus_db import CellThalamusDB
import pandas as pd

db = CellThalamusDB(db_path='/home/jovyan/cell_thalamus_results.db')
results = db.get_results(design_id)
df = pd.DataFrame(results)
```

### Exporting Data

```python
# Export to CSV
df.to_csv('/home/jovyan/cell_thalamus_results.csv', index=False)

# Export to shared folder (accessible by other users)
df.to_csv('/home/shared/cell_thalamus_results.csv', index=False)
```

---

## Troubleshooting

### Out of Memory

If you get memory errors:
1. Increase memory allocation in server settings (32GB or more)
2. Reduce number of workers (e.g., `--workers 16` instead of 64)

### Import Errors

If `import cell_os` fails:
```bash
pip install -e /home/jovyan/cell_OS
```

### Slow Performance

- Check CPU allocation in server settings
- Reduce workers if CPU usage is low: `--workers 16`
- Monitor usage at [grafana dashboard](https://grafana.aws.insitro.com)

### Results Not Saving

Check that the database path is writable:
```python
import os
db_path = '/home/jovyan/cell_thalamus_results.db'
os.path.exists(os.path.dirname(db_path))  # Should be True
```

---

## Advanced Usage

### Custom Cell Lines / Compounds

```python
from cell_os.cell_thalamus.parallel_runner import run_parallel_simulation

design_id = run_parallel_simulation(
    cell_lines=['A549', 'HepG2', 'U2OS'],
    compounds=['tBHQ', 'tunicamycin', 'etoposide'],
    mode='full',
    workers=64,
    db_path='/home/jovyan/custom_results.db'
)
```

### Benchmarking

Test different CPU counts to find optimal performance:

```bash
# Test with different worker counts
for workers in 8 16 32 64; do
    echo "Testing with $workers workers..."
    python -m cell_os.cell_thalamus.parallel_runner \
        --mode quick \
        --workers $workers \
        --db-path /home/jovyan/bench_${workers}.db
done
```

### Running Multiple Experiments

You can run multiple simulations in parallel on different named servers:
1. Create multiple named servers (up to 5 additional)
2. Run different experiments on each server
3. Results are stored in separate databases

---

## Cost Optimization

- **Start small**: Test with `--mode demo` first (4 wells, <10 seconds)
- **Scale up**: Use `--mode quick` for development (~few minutes)
- **Full run**: Only use `--mode full` when ready (2304 wells, ~2 minutes)
- **Stop servers**: Remember to stop your server when done to save costs

---

## Questions?

Reach out to #compute-core on Slack for JupyterHub questions or issues.
