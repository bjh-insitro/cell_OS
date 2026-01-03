#!/usr/bin/env python3
"""CLI wrapper for standalone cell thalamus simulator.

This wrapper maintains backwards compatibility for command-line usage
while the module itself has moved to src/cell_os/sim/ for proper packaging.

Usage:
    python scripts/experiments/standalone_cell_thalamus.py --mode full --workers 64
"""

from cell_os.sim.standalone_cell_thalamus import main

if __name__ == "__main__":
    raise SystemExit(main())
