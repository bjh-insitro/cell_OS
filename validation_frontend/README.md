# cell_OS Frontend

This directory contains the React-based frontend for cell_OS.

## Setup

1.  Navigate to this directory:
    ```bash
    cd frontend
    ```

2.  Install dependencies:
    ```bash
    npm install
    ```

## Development

Start the development server:

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

## Build

Build for production:

```bash
npm run build
```

## Structure

*   `src/components`: Reusable UI components
*   `src/pages`: Top-level page components
*   `src/types`: TypeScript type definitions
*   `src/data`: Mock data (will be replaced by API calls)
*   `src/utils`: Helper functions

## Epistemic Provenance Demo

The `/epistemic-provenance` route visualizes epistemic agent runs with decision provenance, gate events, and calibration metrics.

### Quick Start (Demo Mode)

The repo includes a committed demo dataset in `public/demo_results/epistemic_agent/` with one successful run and one aborted run. Just start the dev server:

```bash
npm run dev
```

Navigate to `http://localhost:5173/epistemic-provenance` to see the demo.

### Using Local Real Runs

To visualize your own epistemic agent runs:

1. **Generate local runs** (from repo root):
   ```bash
   python3 scripts/run_epistemic_agent.py --cycles 20 --budget 384 --seed 42
   ```

2. **Generate manifest**:
   ```bash
   node scripts/make_runs_manifest.mjs
   ```
   This creates `results/epistemic_agent/runs_manifest.json` listing all local runs.

3. **Configure base path**:
   ```bash
   cp .env.local.example .env.local
   # Edit .env.local and uncomment:
   # VITE_RESULTS_BASE=/results/epistemic_agent
   ```

4. **Symlink results into public/** (one-time setup):
   ```bash
   ln -s ../../results public/results
   ```

5. **Restart dev server**:
   ```bash
   npm run dev
   ```

The run picker will now list your local runs instead of the demo dataset.

### Architecture Notes

- **No filename guessing**: All artifact paths come from `run.paths.*` in the JSON metadata
- **Hostile JSONL parsing**: Parse errors are counted and surfaced, never silently ignored
- **Backward compatible**: Legacy runs without `decisions.jsonl` render with warnings
- **Gate events from explicit prefixes**: Only `gate_event:*` and `gate_loss:*` beliefs count as gate transitions
