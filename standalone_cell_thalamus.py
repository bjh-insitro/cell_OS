"""
Standalone Cell Thalamus Parallel Runner for AWS/JupyterHub
Last Updated: December 17, 2025 @ 12:30 AM PST

This is a self-contained script with all compound parameters embedded.
Just upload this file and run it - no dependencies on external YAML files!

HARDENING (December 2025):
- Stable hashing: Deterministic across machines/processes (no Python hash salt)
- RNG stream isolation: Observation cannot perturb physics (observer-independent)
- Death accounting: Complete partition with death_unknown bucket (honest causality)
- Seed contract: --seed=0 (default) for fully deterministic runs

Simulation Realism Features (Matches Main Codebase):
1. Cell-Line-Specific Sensitivity:
   - A549 (lung cancer): NRF2-primed (oxidative resistant), faster cycling (microtubule drug sensitive)
   - HepG2 (hepatoma): High ER load (ER stress sensitive), OXPHOS-dependent (mito stress sensitive),
     high proteostasis burden (proteasome sensitive), peroxide detox capacity (H2O2 resistant)

2. LDH Cytotoxicity (Replaces ATP):
   - LDH = baseline × (1 - viability)  # Inverse relationship
   - LDH rises when cells die (membrane rupture releases LDH)
   - Orthogonal to Cell Painting (supernatant vs cellular morphology)
   - NOT confounded by mitochondrial stress (CCCP/oligomycin)
   - True cytotoxicity measurement (membrane integrity)

3. Proliferation-Coupled Microtubule Sensitivity:
   - Faster cycling cells (A549) more sensitive to nocodazole/paclitaxel
   - Sensitivity scales with proliferation index (not arbitrary IC50 shifts)

4. Realistic Noise Model (2-3% CV for DMSO controls):
   - Biological variation: 2% CV (intrinsic cell-to-cell differences)
   - Technical noise: 1-1.5% CV per factor (plate, day, operator, well)
   - Total CV matches Cell Painting Consortium benchmarks

5. Batch Effects (Consistent Within Batch):
   - Plate/day/operator factors deterministic (same batch = same offset)
   - Enables batch correction and SPC monitoring

6. Edge Effects (12% Signal Reduction):
   - Wells on plate edges (rows A/H, columns 1/12) show reduced signal
   - Real artifacts: evaporation, temperature gradients

7. Random Well Failures (2% Rate):
   - Bubbles (40% of failures): near-zero signal
   - Contamination (25%): 5-20× higher signal (bacteria/yeast)
   - Pipetting errors (20%): 5-30% of normal (wrong volume)
   - Prevents agent overfitting, teaches robust replicate allocation

Full Mode Specifications:
- 2 cell lines (A549, HepG2)
- 10 compounds (oxidative, ER stress, mitochondrial, DNA damage, proteasome, microtubule)
- 4 doses per compound: vehicle, low (0.1×), mid (1×), high (10×) relative to BASE compound EC50
  * Doses are in µM: tBHQ (0, 3, 30, 300), paclitaxel (0, 0.001, 0.01, 0.1), etc.
  * IMPORTANT: "1× base EC50" ≠ "50% viability" due to cell-line-specific IC50 shifts
    Example: tBHQ 30 µM gives ~33% viability in HepG2 (IC50=21µM) but ~69% in A549 (IC50=45µM)
- Sentinels per plate: 4 DMSO, 2 tBHQ (10µM), 2 tunicamycin (2µM) × 2 cell lines = 16 total
- 2 timepoints (12h, 48h)
- 2 days, 2 operators, 3 replicates
- Total: 2,304 wells (1,920 experimental + 384 sentinels)
- MATCHES the design_generator.py Full mode exactly!

Usage:
    # Full campaign with 64 workers (~5 minutes on c5.18xlarge)
    python standalone_cell_thalamus.py --mode full --workers 64

    # Quick demo test (4 wells)
    python standalone_cell_thalamus.py --mode demo --workers 4

Requirements (install on AWS/JupyterHub):
    pip install numpy tqdm

Output:
    - SQLite database: cell_thalamus_results.db
    - Compatible with Cell Thalamus React dashboard
"""

import argparse
import sys
import time
import logging
import uuid
import sqlite3
import os
import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from multiprocessing import Pool, cpu_count
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from dataclasses import dataclass

import numpy as np
from tqdm import tqdm

# Pacific timezone for timestamps
PACIFIC_TZ = ZoneInfo("America/Los_Angeles")

logger = logging.getLogger(__name__)

# Debug flag: set to True to log dose ratios for sentinel compounds
DEBUG_DOSE_RATIOS = False


# ============================================================================
# RNG HARDENING (Cross-Machine Determinism + Stream Isolation)
# ============================================================================

def stable_u32(s: str) -> int:
    """
    Stable 32-bit seed from string. Cross-process and cross-machine deterministic.

    Unlike Python's hash(), this is NOT salted per process, so it gives
    consistent seeds across runs, machines, and Python versions.
    Critical for reproducibility in distributed environments (AWS, JupyterHub).

    Args:
        s: String to hash

    Returns:
        Unsigned 32-bit integer suitable for RNG seeding
    """
    h = hashlib.blake2s(s.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(h, byteorder="little", signed=False)


@dataclass
class RNGStreams:
    """
    Isolated RNG streams for observer-independent physics.

    Three dedicated streams ensure that observation (assay calls) cannot
    perturb physics (growth, treatment effects).

    Seed contract:
    - seed=0 → Fully deterministic (physics + measurements)
    - seed=N → Independent run with seed N
    - ALWAYS pass explicitly (never rely on random seed)

    IMPORTANT: rng_assay is kept for non-well-addressable randomness (e.g., QC
    subsampling, progress jitter, optional diagnostics). For per-well measurements
    that land in the DB, use assay_rng_for_well() to ensure workers=1 equals workers=N.
    """
    seed: int = 0

    def __post_init__(self):
        base = int(self.seed) & 0x7FFFFFFF
        self.rng_growth = np.random.default_rng(base + 1)      # Growth dynamics, cell count
        self.rng_treatment = np.random.default_rng(base + 2)   # Treatment variability
        self.rng_assay = np.random.default_rng(base + 3)       # Non-well-addressable assay randomness


# Global RNG streams (will be initialized in main())
_RNG_STREAMS = None

def get_rng() -> RNGStreams:
    """Get global RNG streams."""
    global _RNG_STREAMS
    if _RNG_STREAMS is None:
        _RNG_STREAMS = RNGStreams(seed=0)
    return _RNG_STREAMS

# ============================================================================
# RNG Usage Rules (Treat rng_assay Like Radioactive Waste)
# ============================================================================
#
# CRITICAL: For any measurement that lands in the database, use assay_rng_for_well()
# NOT the global rng_assay stream. Otherwise workers=1 will differ from workers=N.
#
# ✅ OK to use rng_assay for:
#    - Optional diagnostics (progress jitter, logging noise)
#    - QC subsampling (random selection of wells for spot checks)
#    - Non-deterministic features (if explicitly requested by user)
#
# ❌ NOT OK to use rng_assay for:
#    - Per-well morphology noise (use assay_rng_for_well with "morph_bio" tag)
#    - Per-well LDH noise (use assay_rng_for_well with "ldh_bio" tag)
#    - Any measurement that lands in thalamus_results table
#    - Any value that affects physics or downstream analysis
#
# Rule of thumb: If it's addressable by (design_id, plate_id, cell_line, well_id),
# it MUST use assay_rng_for_well(). No exceptions.
#
# Future guardrail: In debug mode, consider wrapping rng_assay to refuse usage
# when IN_DB_WRITE_SECTION flag is true. Slightly annoying, massively future-proof.
# ============================================================================

# Plate ID semantics: plate_id represents a conceptual experimental unit
# (day, operator, replicate, timepoint) that contains TWO physical plates
# (one per cell line). The cell_line field distinguishes physical plates.
# Result: (plate_id, cell_line, well_id) uniquely identifies a physical well.


# ============================================================================
# Database Module
# ============================================================================

class CellThalamusDB:
    """Lightweight database for Cell Thalamus results."""

    SCHEMA_VERSION = 1  # Increment when schema changes

    def __init__(self, db_path: str = "cell_thalamus_results.db"):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".", exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)

        # Set pragmas for reliability and performance
        # WAL mode: Better concurrency, prevents "database is locked" errors
        # NORMAL synchronous: Balance safety vs performance (safe enough for JH)
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")

        self._create_schema()
        self._check_schema_version()

        # Log DB info at startup
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Connected to DB: {self.db_path}")
        logger.info(f"Tables: {', '.join(tables)}")
        logger.info(f"Schema version: {self.SCHEMA_VERSION}")

    def _create_schema(self):
        """Create database tables."""
        cursor = self.conn.cursor()

        # Schema version tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS thalamus_designs (
                design_id TEXT PRIMARY KEY,
                phase INTEGER,
                cell_lines TEXT,
                compounds TEXT,
                doses TEXT,
                timepoints TEXT,
                created_at TEXT,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS thalamus_results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                design_id TEXT,
                well_id TEXT,
                cell_line TEXT,
                compound TEXT,
                dose_uM REAL,
                timepoint_h REAL,
                plate_id TEXT,
                day INTEGER,
                operator TEXT,
                is_sentinel INTEGER,
                morph_er REAL,
                morph_mito REAL,
                morph_nucleus REAL,
                morph_actin REAL,
                morph_rna REAL,
                atp_signal REAL,  -- Actually LDH cytotoxicity (kept name for backward compat)
                viability REAL,  -- Final viability after compound effects
                death_compound REAL,  -- Fraction killed by compounds
                death_confluence REAL,  -- Fraction killed by overconfluence
                death_unknown REAL,  -- Fraction killed by unknown causes (seeding stress, etc.)
                death_mode TEXT,  -- "compound", "confluence", "mixed", "unknown", or NULL
                transport_dysfunction_score REAL,  -- Cytoskeletal disruption score (0-1)
                timestamp TEXT
            )
        """)

        # Enforce physical well uniqueness within a design
        # This is the primary integrity constraint - prevents duplicate wells in a single run
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_thalamus_physical_well
            ON thalamus_results (design_id, plate_id, cell_line, well_id)
        """)

        # Note: We do NOT enforce cross-design uniqueness to allow intentional repeats
        # (e.g., running same benchmark twice for drift tracking, or merging multiple runs)
        # If you want "one DB = one run forever", add this constraint:
        #   CREATE UNIQUE INDEX ux_thalamus_condition
        #   ON thalamus_results (plate_id, cell_line, well_id, compound, dose_uM, timepoint_h, day, operator)

        # Performance indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_thalamus_plate
            ON thalamus_results (design_id, plate_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_thalamus_compound
            ON thalamus_results (design_id, compound, dose_uM, timepoint_h, cell_line)
        """)

        self.conn.commit()

    def _check_schema_version(self):
        """Check and update schema version."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        row = cursor.fetchone()

        if row is None:
            # Fresh DB - insert current version
            cursor.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (self.SCHEMA_VERSION, datetime.now(PACIFIC_TZ).isoformat())
            )
            self.conn.commit()
        elif row[0] != self.SCHEMA_VERSION:
            # Version mismatch
            logger.warning(
                f"Schema version mismatch: DB has v{row[0]}, code expects v{self.SCHEMA_VERSION}. "
                f"This may cause errors. Consider migrating or using --force to proceed anyway."
            )

    def save_design(self, design_id: str, phase: int, cell_lines: List[str],
                   compounds: List[str], metadata: Dict):
        """Save design metadata."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO thalamus_designs (design_id, phase, cell_lines, compounds, doses, timepoints, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (design_id, phase, str(cell_lines), str(compounds),
              str([0.0, 0.1, 1.0, 10.0]), str([12.0, 48.0]),
              datetime.now(PACIFIC_TZ).isoformat(), str(metadata)))
        self.conn.commit()

    def insert_results_batch(self, results: List[Dict], commit: bool = True):
        """Batch insert results. Set commit=False for transaction batching."""
        if not results:
            return

        cursor = self.conn.cursor()
        timestamp = datetime.now(PACIFIC_TZ).isoformat()

        data = []
        for r in results:
            m = r['morphology']
            data.append((
                r['design_id'], r['well_id'], r['cell_line'], r['compound'],
                r['dose_uM'], r['timepoint_h'], r['plate_id'], r['day'],
                r['operator'], r['is_sentinel'],
                m['er'], m['mito'], m['nucleus'], m['actin'], m['rna'],
                r['atp_signal'], r['viability'], r['death_compound'], r['death_confluence'],
                r['death_unknown'], r['death_mode'], r['transport_dysfunction_score'], timestamp
            ))

        cursor.executemany("""
            INSERT INTO thalamus_results
            (design_id, well_id, cell_line, compound, dose_uM, timepoint_h,
             plate_id, day, operator, is_sentinel,
             morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna,
             atp_signal, viability, death_compound, death_confluence, death_unknown,
             death_mode, transport_dysfunction_score, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)

        if commit:
            self.conn.commit()
        logger.info(f"Batch inserted {len(results)} results")

    def close(self):
        self.conn.close()


# ============================================================================
# Experimental Design
# ============================================================================

@dataclass
class WellAssignment:
    """Single well assignment."""
    well_id: str
    cell_line: str
    compound: str
    dose_uM: float
    timepoint_h: float
    plate_id: str
    day: int
    operator: str
    is_sentinel: bool


def generate_design(cell_lines: List[str], compounds: List[str],
                   mode: str = "full") -> List[WellAssignment]:
    """Generate experimental design."""

    if mode == "demo":
        # Minimal 4 wells for testing
        design = []
        well_idx = 0
        for compound in ['tBHQ', 'tunicamycin']:
            for dose in [0.0, 10.0]:
                design.append(WellAssignment(
                    well_id=f"A{well_idx+1:02d}",
                    cell_line='A549',
                    compound=compound,
                    dose_uM=dose,
                    timepoint_h=12.0,
                    plate_id="Demo_Plate_1",
                    day=1,
                    operator="Demo",
                    is_sentinel=False
                ))
                well_idx += 1
        return design

    if mode == "benchmark":
        # Small, fast design for correlation checks
        # 1 day, 1 operator, 1 replicate, 1 timepoint
        dose_levels = [0.0, 0.1, 1.0, 10.0]
        timepoints = [12.0]
        days = [1]
        operators = ['Operator_A']
        replicates = 1

        # Keep compounds representative and diverse
        benchmark_compounds = ['tBHQ', 'tunicamycin', 'CCCP', 'etoposide']
        # If user passed a smaller compounds list, intersect
        benchmark_compounds = [c for c in benchmark_compounds if c in compounds]
        if not benchmark_compounds:
            benchmark_compounds = compounds[:4]

        # Use benchmark subset for design generation
        compounds = benchmark_compounds
    else:
        # Full mode defaults
        dose_levels = [0.0, 0.1, 1.0, 10.0]  # vehicle, low, mid, high (fractions of EC50)
        timepoints = [12.0, 48.0]
        days = [1, 2]
        operators = ['Operator_A', 'Operator_B']
        replicates = 3

    # Full/benchmark design with EC50-relative dosing
    design = []

    # Plate layout helpers
    ROWS = [chr(65 + i) for i in range(8)]   # A-H
    COLS = [f"{i:02d}" for i in range(1, 13)]  # 01-12
    ALL_WELLS = [f"{r}{c}" for r in ROWS for c in COLS]  # 96 wells

    # Sentinel definitions (single source of truth)
    # Format: (compound, dose_uM, well_positions)
    SENTINELS = [
        ('DMSO', 0.0, ['A01', 'A12', 'H01', 'H12']),        # Vehicle control (4 corners)
        ('tBHQ', 10.0, ['A06', 'H06']),                     # Mild oxidative stress
        ('tunicamycin', 2.0, ['D06', 'E06']),               # Strong ER stress
    ]
    # Derive reserved wells from sentinel definitions
    RESERVED_WELLS = set().union(*(wells for _, _, wells in SENTINELS))

    # timepoints/days/operators/replicates now set by mode above

    for day in days:
        for operator in operators:
            for replicate in range(replicates):
                for timepoint in timepoints:
                    plate_id = f"Plate_{replicate+1}_Day{day}_{operator}_T{timepoint}h"

                    # Experimental wells should avoid reserved sentinel positions
                    exp_wells = [w for w in ALL_WELLS if w not in RESERVED_WELLS]
                    exp_well_iter = iter(exp_wells)

                    # Experimental wells (including vehicle = 0 µM for each compound)
                    for cell_line in cell_lines:
                        for compound in compounds:
                            # Get compound-specific EC50
                            ec50 = COMPOUND_PARAMS[compound]['ec50_uM']

                            for dose_level in dose_levels:
                                # Calculate actual dose: dose_level × EC50
                                dose_uM = dose_level * ec50

                                try:
                                    well_id = next(exp_well_iter)
                                except StopIteration:
                                    raise RuntimeError(
                                        f"Ran out of non-reserved wells on {plate_id}. "
                                        f"Design needs > {len(exp_wells)} experimental wells per plate."
                                    )

                                design.append(WellAssignment(
                                    well_id=well_id,
                                    cell_line=cell_line,
                                    compound=compound,
                                    dose_uM=dose_uM,
                                    timepoint_h=timepoint,
                                    plate_id=plate_id,
                                    day=day,
                                    operator=operator,
                                    is_sentinel=False
                                ))

                    # Sentinels (derived from SENTINELS structure)
                    for cell_line in cell_lines:
                        for compound, dose_uM, well_positions in SENTINELS:
                            for sentinel_well in well_positions:
                                design.append(WellAssignment(
                                    well_id=sentinel_well,
                                    cell_line=cell_line,
                                    compound=compound,
                                    dose_uM=dose_uM,
                                    timepoint_h=timepoint,
                                    plate_id=plate_id,
                                    day=day,
                                    operator=operator,
                                    is_sentinel=True
                                ))

    return design


# ============================================================================
# Compound Parameters (embedded from cell_thalamus_params.yaml)
# ============================================================================

COMPOUND_PARAMS = {
    # ec50_uM: base EC50 for viability (before cell-line adjustments)
    # hill_slope: Hill coefficient for viability curve steepness
    # stress_axis: category determining morphology effects
    # intensity: morphology effect magnitude

    'tBHQ': {'ec50_uM': 30.0, 'hill_slope': 2.0, 'stress_axis': 'oxidative', 'intensity': 0.8},
    'H2O2': {'ec50_uM': 100.0, 'hill_slope': 2.0, 'stress_axis': 'oxidative', 'intensity': 1.2},
    'tbhp': {'ec50_uM': 80.0, 'hill_slope': 2.0, 'stress_axis': 'oxidative', 'intensity': 1.0},

    'tunicamycin': {'ec50_uM': 1.0, 'hill_slope': 2.0, 'stress_axis': 'er_stress', 'intensity': 1.2},
    'thapsigargin': {'ec50_uM': 0.5, 'hill_slope': 2.5, 'stress_axis': 'er_stress', 'intensity': 1.5},

    # Mitochondrial drugs: LDH rises when cells die (no early ATP crash confound)
    'CCCP': {'ec50_uM': 5.0, 'hill_slope': 2.5, 'stress_axis': 'mitochondrial', 'intensity': 1.3},  # Steeper hill for sharper transition
    'oligomycin': {'ec50_uM': 1.0, 'hill_slope': 2.3, 'stress_axis': 'mitochondrial', 'intensity': 1.0},
    'two_deoxy_d_glucose': {'ec50_uM': 1000.0, 'hill_slope': 1.5, 'stress_axis': 'mitochondrial', 'intensity': 0.6},

    'etoposide': {'ec50_uM': 10.0, 'hill_slope': 2.0, 'stress_axis': 'dna_damage', 'intensity': 1.0},
    'cisplatin': {'ec50_uM': 5.0, 'hill_slope': 2.0, 'stress_axis': 'dna_damage', 'intensity': 1.2},
    'doxorubicin': {'ec50_uM': 0.5, 'hill_slope': 2.5, 'stress_axis': 'dna_damage', 'intensity': 1.4},
    'staurosporine': {'ec50_uM': 0.1, 'hill_slope': 3.0, 'stress_axis': 'dna_damage', 'intensity': 1.8},

    'MG132': {'ec50_uM': 1.0, 'hill_slope': 2.0, 'stress_axis': 'proteasome', 'intensity': 1.1},

    # Microtubule drugs: sensitivity coupled to proliferation rate (handled separately)
    'nocodazole': {'ec50_uM': 0.5, 'hill_slope': 2.0, 'stress_axis': 'microtubule', 'intensity': 1.3},
    'paclitaxel': {'ec50_uM': 0.01, 'hill_slope': 2.5, 'stress_axis': 'microtubule', 'intensity': 1.5},
}

# ============================================================================
# Morphology Parameters (Adaptive vs Damage Model)
# ============================================================================

# Channel list (explicit ordering)
CHANNELS = ['er', 'mito', 'nucleus', 'actin', 'rna']

# Cell-line-specific baselines (means)
# Keep these interpretable: HepG2 tends to have higher ER/mito/RNA baseline load.
BASELINE_MORPH = {
    'A549':  {'er': 1.00, 'mito': 1.00, 'nucleus': 1.00, 'actin': 1.00, 'rna': 1.00},
    'HepG2': {'er': 1.10, 'mito': 1.20, 'nucleus': 1.00, 'actin': 0.95, 'rna': 1.10},
    'iPSC_NGN2': {'er': 0.85, 'mito': 1.47, 'nucleus': 0.90, 'actin': 1.33, 'rna': 0.78},  # Neurons: low ER, very high mito, high actin (neurites)
    'iPSC_Microglia': {'er': 1.40, 'mito': 1.13, 'nucleus': 0.85, 'actin': 1.25, 'rna': 1.06},  # Immune cells: high ER (cytokines), high actin (phagocytosis)
}

# Channel-specific biological variability (CV). (Not technical noise. Real per-well biology.)
MORPH_CV = {
    'er': 0.020,    # 2% biological variation (realistic)
    'mito': 0.020,
    'nucleus': 0.020,
    'actin': 0.020,
    'rna': 0.020,
}

# Physical floors/ceilings per channel (relative to baseline)
MORPH_FLOOR = {'er': 0.20, 'mito': 0.10, 'nucleus': 0.30, 'actin': 0.20, 'rna': 0.20}
MORPH_CEIL  = {'er': 3.00, 'mito': 2.50, 'nucleus': 1.80, 'actin': 2.00, 'rna': 2.50}

# Axis-specific morphology rules split into:
# - adapt: early reversible stress response (hump-shaped vs dose)
# - damage: late irreversible damage (monotone vs dose, tracks death)
# NOTE: signs are "directional features", not literal intensities.
MORPH_EFFECTS = {
    'oxidative': {
        'mito':    {'adapt': +0.6, 'damage': -0.8},
        'er':      {'adapt': +0.2, 'damage': -0.4},
        'rna':     {'adapt': +0.3, 'damage': -0.6},
        'nucleus': {'adapt':  0.0, 'damage': +0.8},
        'actin':   {'adapt':  0.0, 'damage': -0.4},
    },
    'er_stress': {
        'er':      {'adapt': +2.0, 'damage': -1.5},  # swell then collapse
        'rna':     {'adapt': +0.8, 'damage': -1.0},
        'mito':    {'adapt': +0.3, 'damage': -0.6},
        'nucleus': {'adapt':  0.0, 'damage': +1.2},
        'actin':   {'adapt':  0.0, 'damage': -0.4},
    },
    'mitochondrial': {
        'mito':    {'adapt': +1.0, 'damage': -1.6},  # remodel then fail
        'rna':     {'adapt': +0.2, 'damage': -0.8},
        'er':      {'adapt': +0.1, 'damage': -0.5},
        'nucleus': {'adapt':  0.0, 'damage': +1.0},
        'actin':   {'adapt':  0.0, 'damage': -0.5},
    },
    'dna_damage': {
        'nucleus': {'adapt':  0.0, 'damage': +1.8},
        'rna':     {'adapt': +0.1, 'damage': -0.6},
        'mito':    {'adapt':  0.0, 'damage': -0.4},
        'er':      {'adapt':  0.0, 'damage': -0.3},
        'actin':   {'adapt':  0.0, 'damage': -0.4},
    },
    'proteasome': {
        'er':      {'adapt': +0.7, 'damage': -1.0},
        'rna':     {'adapt': +0.6, 'damage': -0.8},
        'mito':    {'adapt': +0.2, 'damage': -0.7},
        'nucleus': {'adapt':  0.0, 'damage': +0.9},
        'actin':   {'adapt':  0.0, 'damage': -0.4},
    },
    'microtubule': {
        'actin':   {'adapt': +0.8, 'damage': -0.6},
        'nucleus': {'adapt': +0.3, 'damage': +1.0},
        'rna':     {'adapt': +0.1, 'damage': -0.5},
        'mito':    {'adapt':  0.0, 'damage': -0.3},
        'er':      {'adapt':  0.0, 'damage': -0.2},
    },
}

# Optional: small cell-line-specific modulation by axis (keeps A549 vs HepG2 distinct beyond baseline)
# Values >1 amplify response magnitude; <1 dampen.
AXIS_CELL_MULT = {
    'oxidative':      {'A549': 0.85, 'HepG2': 1.10},
    'er_stress':      {'A549': 0.90, 'HepG2': 1.15},
    'mitochondrial':  {'A549': 0.95, 'HepG2': 1.10},
    'dna_damage':     {'A549': 1.10, 'HepG2': 0.95},
    'proteasome':     {'A549': 0.95, 'HepG2': 1.15},
    'microtubule':    {'A549': 1.10, 'HepG2': 0.90},
}

# ============================================================================
# Morphology: correlated bio-noise + channel-specific technical factors
# ============================================================================

# Technical noise parameters (matches main codebase exactly)
# These CVs are applied multiplicatively to ALL channels together (not channel-specific)
# Total CV budget: sqrt(0.010² + 0.015² + 0.008² + 0.015²) ≈ 2.5% ✓
TECH_CV = {
    'plate_cv': 0.010,          # 1% plate-to-plate variation
    'day_cv': 0.015,            # 1.5% day-to-day variation
    'operator_cv': 0.008,       # 0.8% operator-to-operator variation
    'well_cv': 0.015,           # 1.5% well-to-well (measurement noise)
    'edge_effect': 0.12,        # 12% signal reduction for edge wells (evaporation, temperature)
    'well_failure_rate': 0.02,  # 2% of wells randomly fail (bubbles, contamination, pipetting errors)
}

def _get_attr(obj, name, default=None):
    return getattr(obj, name, default)

def assay_rng_for_well(design_id: str, plate_id: str, cell_line: str, well_id: str, tag: str):
    """
    Generate deterministic per-well RNG for assay measurements.

    This ensures workers=1 equals workers=N by making measurement noise addressable
    by stable key, not dependent on consumption order from a shared stream.

    Observer independence is still maintained (physics RNG streams unchanged).
    This just makes measurement noise deterministic per-well.

    IMPORTANT: Includes design_id in seed to avoid correlated measurement noise
    across different designs. Different designs SHOULD have different assay noise.
    Workers=1 vs workers=N comparison works WITHIN a single design_id.

    Args:
        design_id: Design identifier (prevents cross-design correlated noise)
        plate_id: Plate identifier
        cell_line: Cell line name
        well_id: Well position (e.g., 'A01')
        tag: Noise type tag (e.g., 'morph_bio', 'ldh_bio')

    Returns:
        Numpy RNG generator seeded by stable key
    """
    s = f"{tag}|{design_id}|{plate_id}|{cell_line}|{well_id}"
    return np.random.default_rng(stable_u32(s))

def _is_edge_well(well_position: str, plate_format: int = 96) -> bool:
    """Detect if well is on plate edge (evaporation/temperature artifacts)."""
    if not well_position or len(well_position) < 2:
        return False

    row = well_position[0]
    try:
        col = int(well_position[1:])
    except ValueError:
        return False

    if plate_format == 96:
        # 96-well: 8 rows (A-H), 12 columns (1-12)
        edge_rows = ['A', 'H']
        edge_cols = [1, 12]
        return row in edge_rows or col in edge_cols
    elif plate_format == 384:
        # 384-well: 16 rows (A-P), 24 columns (1-24)
        edge_rows = ['A', 'P']
        edge_cols = [1, 24]
        return row in edge_rows or col in edge_cols
    else:
        return False

# Cell-line proliferation index (relative doubling time)
# Higher = faster cycling (more sensitive to cell cycle poisons)
PROLIF_INDEX = {
    'A549': 1.3,           # Faster cycling (lung cancer)
    'HepG2': 0.8,          # Slower cycling (hepatoma)
    'iPSC_NGN2': 0.1,      # Post-mitotic (neurons barely divide)
    'iPSC_Microglia': 0.6, # Moderate proliferation (can divide but slower than cancer)
}

# Cell-line-specific LDH baseline (released from dead/dying cells)
BASELINE_LDH = {
    'A549': 50000.0,
    'HepG2': 50000.0,
    'iPSC_NGN2': 70000.0,       # Very high ATP/LDH (neurons have extreme metabolic rate)
    'iPSC_Microglia': 65000.0,  # High ATP/LDH (active immune cells)
}

# Cell-line-specific sensitivity (IC50 multipliers)
# Values > 1.0 = LESS sensitive (higher IC50 needed)
# Values < 1.0 = MORE sensitive (lower IC50 needed)
# NOTE: Microtubule drugs (nocodazole, paclitaxel) use PROLIF_INDEX instead (see calculation below)
CELL_LINE_SENSITIVITY = {
    # Oxidative stress
    'tBHQ': {'A549': 1.5, 'HepG2': 0.7, 'iPSC_NGN2': 0.5, 'iPSC_Microglia': 1.2},      # Microglia resistant (produce ROS as weapon)
    'H2O2': {'A549': 0.7, 'HepG2': 1.5, 'iPSC_NGN2': 0.4, 'iPSC_Microglia': 1.5},      # Microglia very resistant (high antioxidant capacity)

    # ER stress (HepG2 more sensitive - higher baseline ER load, secretory burden)
    'tunicamycin': {'A549': 1.4, 'HepG2': 0.7, 'iPSC_NGN2': 0.9, 'iPSC_Microglia': 0.8},
    'thapsigargin': {'A549': 1.4, 'HepG2': 0.7, 'iPSC_NGN2': 0.9, 'iPSC_Microglia': 0.8},

    # Mitochondrial stress (Neurons EXTREMELY sensitive - total OXPHOS dependence)
    'CCCP': {'A549': 1.4, 'HepG2': 0.7, 'iPSC_NGN2': 0.3, 'iPSC_Microglia': 0.9},
    'oligomycin': {'A549': 1.4, 'HepG2': 0.7, 'iPSC_NGN2': 0.3, 'iPSC_Microglia': 0.9},

    # DNA damage (A549 more sensitive - cleaner apoptotic response)
    'etoposide': {'A549': 0.7, 'HepG2': 1.3, 'iPSC_NGN2': 0.8, 'iPSC_Microglia': 1.3},  # Immune cells resist DNA damage

    # Proteasome inhibition (Microglia sensitive - high protein turnover for cytokines)
    'MG132': {'A549': 1.4, 'HepG2': 0.7, 'iPSC_NGN2': 0.7, 'iPSC_Microglia': 0.6},
}

# ============================================================================
# Simulation
# ============================================================================

def simulate_well(well: WellAssignment, design_id: str) -> Optional[Dict]:
    """Simulate a single well experiment with realistic compound effects."""

    try:
        # ============= MORPHOLOGY BLOCK (Adaptive vs Damage + Real Tech + Corr Bio) =============

        # Initialize baseline morphology for this cell line
        base = BASELINE_MORPH.get(well.cell_line, BASELINE_MORPH['A549'])
        morph = {ch: float(base[ch]) for ch in CHANNELS}

        # Precompute "true" viability_effect for damage coupling (tracks physics)
        # Keep adaptive A(dose) MOA-shaped using base EC50, but damage D uses this.
        viability_effect_true = 1.0
        stress_axis = None
        intensity = 1.0
        hill_slope = 2.0
        ec50 = None

        if well.compound in COMPOUND_PARAMS:
            params = COMPOUND_PARAMS[well.compound]
            ec50 = float(params['ec50_uM'])
            hill_slope = float(params['hill_slope'])
            intensity = float(params.get('intensity', 1.0))  # morphology magnitude only
            stress_axis = params['stress_axis']

            if well.dose_uM > 0:
                # Cell-line-adjusted IC50 logic (mirror viability section below)
                if stress_axis == 'microtubule':
                    prolif = PROLIF_INDEX.get(well.cell_line, 1.0)

                    # Improved microtubule model: mitosis + functional dependency
                    mitosis_mult = 1.0 / max(prolif, 0.3)
                    functional_dependency = {
                        'A549': 0.2, 'HepG2': 0.2,
                        'iPSC_NGN2': 0.8, 'iPSC_Microglia': 0.5
                    }.get(well.cell_line, 0.3)
                    # Modest functional adjustment (20% max) since morphology fails first
                    ic50_mult = mitosis_mult * (1.0 + functional_dependency * 0.2)
                    ic50_mult = max(0.3, min(5.0, ic50_mult))

                    hill_v = hill_slope * (0.8 + 0.4 * prolif)
                else:
                    ic50_mult = CELL_LINE_SENSITIVITY.get(well.compound, {}).get(well.cell_line, 1.0)
                    hill_v = hill_slope

                ic50_viability = max(1e-9, ec50 * ic50_mult)
                viability_effect_true = 1.0 / (1.0 + (well.dose_uM / ic50_viability) ** hill_v)

        # Apply compound morphology effects (only when dose > 0)
        if stress_axis is not None and well.dose_uM > 0:
            # Adaptive curve A(dose): hump-shaped in base potency space (MOA-shaped)
            x = well.dose_uM / max(ec50, 1e-9)
            A = (x ** hill_slope) / ((1.0 + x ** hill_slope) ** 2)
            A = A / 0.25  # normalize peak to ~1 at x=1

            # Damage curve D(dose): must track true death physics
            D = 1.0 - float(viability_effect_true)

            # Time mixing: early = adaptive-dominant, late = damage-dominant
            if well.timepoint_h <= 12:
                wA, wD = 1.0, 0.30
            else:
                wA, wD = 0.30, 1.0

            axis_mult = AXIS_CELL_MULT.get(stress_axis, {}).get(well.cell_line, 1.0)
            axis_rules = MORPH_EFFECTS.get(stress_axis, {})

            for ch in CHANNELS:
                eff = axis_rules.get(ch, {'adapt': 0.0, 'damage': 0.0})
                delta = intensity * axis_mult * (wA * eff['adapt'] * A + wD * eff['damage'] * D)
                morph[ch] = base[ch] * (1.0 + delta)

            # Special handling for microtubule drugs: morphology disruption precedes viability loss
            # Neurons show cytoskeletal disruption (actin, mito distribution) even when viable
            if stress_axis == 'microtubule':
                # Morphology EC50: Lower than viability EC50 (morphology fails first)
                # Set at 30% of viability EC50 for neurons (transport disruption happens fast)
                morph_ec50_fraction = {
                    'iPSC_NGN2': 0.3,       # Morphology fails at 30% of viability dose
                    'iPSC_Microglia': 0.5,  # Moderate
                    'A549': 1.0,            # Morphology and viability fail together
                    'HepG2': 1.0
                }.get(well.cell_line, 1.0)

                morph_ec50 = ec50 * morph_ec50_fraction

                # Smooth saturating Hill equation (not sharp min() clamp)
                morph_penalty = well.dose_uM / (well.dose_uM + morph_ec50)  # 0 to 1, smooth

                if well.cell_line == 'iPSC_NGN2':
                    # Neurons: major actin/mito disruption at doses below viability IC50
                    morph['actin'] *= (1.0 - 0.6 * morph_penalty)  # Up to 60% reduction
                    morph['mito'] *= (1.0 - 0.5 * morph_penalty)   # Mito distribution severely disrupted
                elif well.cell_line == 'iPSC_Microglia':
                    # Microglia: moderate actin disruption (migration/phagocytosis impaired)
                    morph['actin'] *= (1.0 - 0.4 * morph_penalty)

        # CRITICAL: Compute transport dysfunction from STRUCTURAL morphology
        # Do this BEFORE adding noise and BEFORE applying viability scaling (if any)
        # This prevents measurement contamination from creating runaway feedback loops
        transport_dysfunction_score = 0.0
        if stress_axis == 'microtubule' and well.cell_line == 'iPSC_NGN2':
            # Measure actual STRUCTURAL disruption (after drug effects, before noise/attenuation)
            actin_disruption = max(0.0, 1.0 - morph['actin'] / base['actin'])
            mito_disruption = max(0.0, 1.0 - morph['mito'] / base['mito'])
            # Average disruption (0 = no disruption, 1 = complete loss)
            transport_dysfunction_score = 0.5 * (actin_disruption + mito_disruption)
            # Clamp to [0, 1]
            transport_dysfunction_score = min(1.0, max(0.0, transport_dysfunction_score))

        # Add dose-dependent biological noise (matches main codebase)
        # Note: Noise is added AFTER computing dysfunction to avoid measurement contamination
        # Stressed cells show higher variability (heterogeneous death timing)
        stress_level = 1.0 - float(viability_effect_true)  # 0 (healthy) to 1 (dead)
        stress_multiplier = 2.0  # Stressed cells have 2× higher CV
        effective_bio_cv = MORPH_CV['er'] * (1.0 + stress_level * (stress_multiplier - 1.0))

        # CRITICAL: Use per-well deterministic RNG for measurement noise
        # This ensures workers=1 equals workers=N (not dependent on shared stream consumption order)
        # Observer independence still maintained (physics RNG streams unchanged)
        if effective_bio_cv > 0:
            rng_well_morph = assay_rng_for_well(design_id, well.plate_id, well.cell_line, well.well_id, "morph_bio")
            for ch in CHANNELS:
                morph[ch] *= rng_well_morph.normal(1.0, effective_bio_cv)

        # Technical noise (batch effects) - MATCHES MAIN CODEBASE EXACTLY
        # Extract batch information
        plate_id = _get_attr(well, 'plate_id', None) or _get_attr(well, 'plate_name', None)
        day_id = _get_attr(well, 'day', None) or _get_attr(well, 'day_index', None)
        op_id = _get_attr(well, 'operator', None) or _get_attr(well, 'operator_id', None)
        well_id = _get_attr(well, 'well_id', 'A1')
        cell_line = _get_attr(well, 'cell_line', 'A549')

        # Consistent batch effects per plate/day/operator (deterministic seeding)
        # Only apply if CV > 0 (prevents RNG consumption when noise disabled)
        plate_factor = 1.0
        if TECH_CV['plate_cv'] > 0:
            rng_plate = np.random.default_rng(stable_u32(f"plate_{plate_id}"))
            plate_factor = rng_plate.normal(1.0, TECH_CV['plate_cv'])

        day_factor = 1.0
        if TECH_CV['day_cv'] > 0:
            rng_day = np.random.default_rng(stable_u32(f"day_{day_id}"))
            day_factor = rng_day.normal(1.0, TECH_CV['day_cv'])

        operator_factor = 1.0
        if TECH_CV['operator_cv'] > 0:
            rng_operator = np.random.default_rng(stable_u32(f"operator_{op_id}"))
            operator_factor = rng_operator.normal(1.0, TECH_CV['operator_cv'])

        # Well factor MUST be deterministic (seed by well ID for workers=1 to match workers=N)
        # Using rng.rng_assay would be nondeterministic across worker scheduling
        well_factor = 1.0
        if TECH_CV['well_cv'] > 0:
            rng_well = np.random.default_rng(stable_u32(f"well_{plate_id}_{cell_line}_{well_id}"))
            well_factor = rng_well.normal(1.0, TECH_CV['well_cv'])

        # Edge effect: wells on plate edges show reduced signal
        is_edge = _is_edge_well(well_id)
        edge_factor = (1.0 - TECH_CV['edge_effect']) if is_edge else 1.0

        # Combine all technical factors into one
        total_tech_factor = plate_factor * day_factor * operator_factor * well_factor * edge_factor

        # Apply single tech factor to ALL channels (not channel-specific)
        for ch in CHANNELS:
            morph[ch] *= total_tech_factor
            morph[ch] = max(0.0, morph[ch])  # No negative signals

        # Apply random well failures (2% of wells fail with extreme outliers)
        # NOTE: Deterministic per-well (not per-design) for workers=1 vs workers=N comparison
        well_failure = None
        rng_failure = np.random.default_rng(stable_u32(f"failure_{plate_id}_{cell_line}_{well_id}"))
        if rng_failure.random() < TECH_CV['well_failure_rate']:
            # Well failed - apply random extreme multiplier
            failure_type = rng_failure.choice(['bubble', 'contamination', 'pipetting_error'])
            if failure_type == 'bubble':
                # Bubble in well → near-zero signal
                for ch in CHANNELS:
                    morph[ch] = rng_failure.uniform(0.1, 2.0)
            elif failure_type == 'contamination':
                # Contamination → 5-20× higher signal
                for ch in CHANNELS:
                    morph[ch] *= rng_failure.uniform(5.0, 20.0)
            elif failure_type == 'pipetting_error':
                # Wrong volume → 5-30% of normal
                for ch in CHANNELS:
                    morph[ch] *= rng_failure.uniform(0.05, 0.3)
            well_failure = failure_type

        # ============= END MORPHOLOGY BLOCK =============

        # LDH cytotoxicity signal (replaces ATP)
        # LDH is released when cells die and membranes rupture
        # Orthogonal to Cell Painting morphology
        baseline_ldh = BASELINE_LDH.get(well.cell_line, 50000.0)

        # DMSO vehicle control: high viability, low LDH
        if well.compound == 'DMSO':
            viability_effect = 1.0
            ldh_signal = baseline_ldh * (1.0 - viability_effect) * 0.05  # Minimal LDH from healthy cells
        elif well.compound in COMPOUND_PARAMS and well.dose_uM > 0:
            params = COMPOUND_PARAMS[well.compound]
            ic50_base = params['ec50_uM']
            hill_slope = params['hill_slope']
            stress_axis = params['stress_axis']

            # Apply cell-line-specific IC50 adjustment
            # For microtubule drugs, use improved model with mitosis + functional dependency
            if stress_axis == 'microtubule':
                prolif = PROLIF_INDEX.get(well.cell_line, 1.0)

                # Microtubule toxicity has TWO components:
                # 1. Mitosis-driven (cancer cells die from mitotic catastrophe)
                # 2. Functional transport dependency (neurons have different failure mode: transport collapse)

                # Mitosis-driven component (dominant for cycling cells)
                mitosis_mult = 1.0 / max(prolif, 0.3)  # Clamp at 0.3 to prevent infinite resistance

                # Functional dependency modifies the VIABILITY IC50 modestly
                # High functional dependency means: "morphology collapses early, death follows later"
                # It does NOT mean "protected from death" - that's handled by morphology-to-viability feedback
                functional_dependency = {
                    'A549': 0.2,           # Low functional dependency (mainly mitotic)
                    'HepG2': 0.2,          # Low functional dependency
                    'iPSC_NGN2': 0.8,      # High functional dependency (axonal transport critical)
                    'iPSC_Microglia': 0.5, # Moderate (migration, phagocytosis)
                }.get(well.cell_line, 0.3)

                # IC50 multiplier: mostly mitosis-driven, with modest functional adjustment
                # For neurons: high mitosis_mult (3.3×) slightly reduced by functional dependency
                # For cancer: low mitosis_mult (0.77-1.25×) dominates
                # Functional dependency adds a *small* protective factor (20%) since morphology fails first
                ic50_mult = mitosis_mult * (1.0 + functional_dependency * 0.2)

                # Clamp to reasonable bounds
                ic50_mult = max(0.3, min(5.0, ic50_mult))

                hill_slope = hill_slope * (0.8 + 0.4 * prolif)  # Slightly steeper for faster cycling
            else:
                ic50_mult = CELL_LINE_SENSITIVITY.get(well.compound, {}).get(well.cell_line, 1.0)

            ic50_viability = ic50_base * ic50_mult

            # Viability curve (4PL dose-response)
            # At IC50: viability = 50%, At 10×IC50: viability = ~1%
            viability_effect = 1.0 / (1.0 + (well.dose_uM / ic50_viability) ** hill_slope)

            # Time-dependent death continuation for high stress conditions
            # ER stress and proteostasis stress cause cumulative attrition at high doses
            # (tunicamycin, thapsigargin, MG132 should kill more cells by 48h)
            if well.timepoint_h > 12 and viability_effect < 0.5:  # High stress threshold
                # Calculate stress severity (how far past IC50)
                dose_ratio = well.dose_uM / ic50_viability

                # Time scaling: more death accumulation between 12h → 48h
                time_factor = (well.timepoint_h - 12.0) / 36.0  # 0 at 12h, 1 at 48h

                # Stress-axis-specific attrition rates
                # ER/proteostasis stressors cause persistent unfolded protein accumulation
                # Base attrition rates per stress axis
                base_attrition_rates = {
                    'er_stress': 0.40,      # Strong cumulative effect
                    'proteasome': 0.35,     # Strong cumulative effect
                    'oxidative': 0.20,      # Moderate (some adaptation possible, but ROS accumulates)
                    'mitochondrial': 0.18,  # Moderate (bioenergetic collapse accumulates)
                    'dna_damage': 0.20,     # Moderate (apoptosis cascade)
                    'microtubule': 0.05,    # Weak (rapid commitment for cancer)
                }

                # Microtubule-specific: neurons get higher attrition (slow burn death after transport collapse)
                if stress_axis == 'microtubule' and well.cell_line == 'iPSC_NGN2':
                    # Base attrition for microtubule in neurons
                    base_mt_attrition = 0.25

                    # Scale attrition by ACTUAL morphology disruption (not dose proxy!)
                    # transport_dysfunction_score computed earlier from real actin/mito disruption
                    # This creates the true "morphology → attrition → viability" causal arc
                    dys = transport_dysfunction_score

                    # Nonlinear scaling: mild disruption has ceiling (allows recovery)
                    # dys^2 means: 20% disruption → 4% scale, 50% disruption → 25% scale
                    # This prevents low doses from causing inevitable death
                    attrition_scale = 1.0 + 2.0 * (dys ** 2.0)  # 1× at no disruption, up to 3× at complete disruption
                    attrition_rate = base_mt_attrition * attrition_scale
                else:
                    attrition_rate = base_attrition_rates.get(stress_axis, 0.10)

                # Additional death at high stress over time
                # Only applies when dose >= IC50 (dose_ratio >= 1.0)
                if dose_ratio >= 1.0:
                    # Sigmoid function: starts at 0.5 at IC50, approaches 1.0 at high dose
                    # dose_ratio=1.0 → 0.5, dose_ratio=2.0 → 0.67, dose_ratio=10.0 → 0.91
                    stress_multiplier = dose_ratio / (1.0 + dose_ratio)
                    additional_death = attrition_rate * stress_multiplier * time_factor

                    # Apply additional death (reduce viability further)
                    viability_effect = viability_effect * (1.0 - additional_death)
                    viability_effect = max(0.01, viability_effect)  # Floor at 1% viable

            # Debug logging: dose ratios for sentinel compounds (set DEBUG_DOSE_RATIOS=True to enable)
            if DEBUG_DOSE_RATIOS and well.compound in ['tBHQ', 'CCCP'] and well.dose_uM > 0 and well.is_sentinel:
                dose_base_ratio = well.dose_uM / ic50_base
                dose_adjusted_ratio = well.dose_uM / ic50_viability
                logger.info(f"{well.compound} {well.cell_line} {well.dose_uM}µM: "
                            f"{dose_base_ratio:.2f}×base_EC50, {dose_adjusted_ratio:.2f}×adjusted_IC50, "
                            f"viability={viability_effect:.1%}")

            # LDH signal (INVERSE of viability - rises when cells die)
            # High viability (0.95) → Low LDH (only 5% dead cells releasing LDH)
            # Low viability (0.30) → High LDH (70% dead cells releasing LDH)
            death_fraction = 1.0 - viability_effect
            ldh_signal = baseline_ldh * death_fraction
        else:
            viability_effect = 1.0
            ldh_signal = baseline_ldh * (1.0 - viability_effect) * 0.05

        # Add biological noise (15% CV) - Use per-well deterministic RNG
        # CRITICAL: Per-well RNG ensures workers=1 equals workers=N
        ldh_cv = 0.15
        if ldh_cv > 0:
            rng_well_ldh = assay_rng_for_well(design_id, well.plate_id, well.cell_line, well.well_id, "ldh_bio")
            ldh_signal *= rng_well_ldh.normal(1.0, ldh_cv)

        # Add technical noise: reuse same batch factors as morphology (matches main codebase)
        # LDH is also affected by plate/day/operator/well variation
        ldh_signal *= total_tech_factor

        # Clamp LDH to non-negative
        ldh_signal = max(0.0, ldh_signal)

        # Keep variable name as atp_signal for backward compatibility with database
        atp_signal = ldh_signal

        # ============= DEATH ACCOUNTING (Honest Causality) =============
        # Track death fractions to enforce complete partition
        # Initial seeding: cells start at 98% viability (2% seeding stress)
        initial_viability = 0.98
        death_seeding = 1.0 - initial_viability  # 0.02 baseline

        # Compute final viability after treatment
        final_viability = initial_viability * viability_effect

        # Track compound-induced death (instant + attrition combined)
        # viability_effect represents survival fraction after all compound effects
        death_compound = initial_viability * (1.0 - viability_effect)

        # Unknown death = seeding stress (never reassign this to compound!)
        death_unknown = death_seeding

        # No confluence death in standalone (single timepoint snapshot)
        death_confluence = 0.0

        # Clamp all death fractions to [0, 1]
        death_compound = min(1.0, max(0.0, death_compound))
        death_confluence = min(1.0, max(0.0, death_confluence))
        death_unknown = min(1.0, max(0.0, death_unknown))

        # Enforce partition: death_compound + death_confluence + death_unknown = 1 - viability
        total_dead = 1.0 - final_viability
        tracked = death_compound + death_confluence + death_unknown
        untracked = max(0.0, total_dead - tracked)

        # If untracked > 0.1%, warn (accounting bug)
        if untracked > 0.001:
            logger.warning(
                f"Well {well.well_id}: Untracked death ({untracked:.1%}). "
                f"Total dead: {total_dead:.1%}, tracked: {tracked:.1%}"
            )
            # Fold untracked into death_unknown (don't invent compound causality)
            death_unknown += untracked
            death_unknown = min(1.0, max(0.0, death_unknown))

        # Determine death mode (threshold = 5%)
        threshold = 0.05
        unknown_threshold = 0.01 if death_compound == 0 and death_confluence == 0 else threshold

        if death_compound > threshold and death_confluence > threshold:
            death_mode = "mixed"
        elif death_compound > threshold:
            death_mode = "compound"
        elif death_confluence > threshold:
            death_mode = "confluence"
        elif death_unknown > unknown_threshold:
            death_mode = "unknown"
        elif final_viability < 0.5:
            death_mode = "unknown"  # Significant death but no clear cause
        else:
            death_mode = None  # Healthy

        return {
            'design_id': design_id,
            'well_id': well.well_id,
            'cell_line': well.cell_line,
            'compound': well.compound,
            'dose_uM': well.dose_uM,
            'timepoint_h': well.timepoint_h,
            'plate_id': well.plate_id,
            'day': well.day,
            'operator': well.operator,
            'morphology': morph,
            'atp_signal': atp_signal,
            'viability': final_viability,
            'death_compound': death_compound,
            'death_confluence': death_confluence,
            'death_unknown': death_unknown,
            'death_mode': death_mode,
            'transport_dysfunction_score': transport_dysfunction_score,
            'is_sentinel': well.is_sentinel
        }

    except Exception as e:
        logger.error(f"Error simulating well {well.well_id}: {e}")
        return None


def worker_function(args) -> Optional[Dict]:
    """Worker function for multiprocessing."""
    well, design_id = args
    return simulate_well(well, design_id)


# ============================================================================
# Design ID Canonicalization (Handle Numpy, Tuples, Sets)
# ============================================================================

def canonicalize_for_json(obj):
    """
    Canonicalize Python objects for stable JSON serialization.

    Handles numpy arrays, numpy scalars, tuples, sets, and nested structures
    to prevent silent stringification or runtime errors when hashing design parameters.

    Args:
        obj: Object to canonicalize (dict, list, numpy scalar, etc.)

    Returns:
        JSON-safe canonical representation

    Raises:
        TypeError: If object cannot be canonicalized
    """
    # Numpy arrays → lists (then recurse)
    # CRITICAL: Check this BEFORE hasattr(obj, 'item') since arrays also have .item()
    if isinstance(obj, np.ndarray):
        return [canonicalize_for_json(item) for item in obj.tolist()]

    # Numpy scalars → Python native types
    # Check for numpy scalar types explicitly (not just hasattr which can be surprising)
    if isinstance(obj, (np.integer, np.floating, np.bool_, np.complexfloating)):
        return obj.item()

    # Sets → sorted lists (stable order)
    if isinstance(obj, set):
        return sorted(canonicalize_for_json(item) for item in obj)

    # Tuples → lists
    if isinstance(obj, tuple):
        return [canonicalize_for_json(item) for item in obj]

    # Dicts → recurse on values (keys already handled by sort_keys=True in JSON)
    if isinstance(obj, dict):
        return {k: canonicalize_for_json(v) for k, v in obj.items()}

    # Lists → recurse on items
    if isinstance(obj, list):
        return [canonicalize_for_json(item) for item in obj]

    # Plain types pass through (str, int, float, bool, None)
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj

    # If we reach here, it's something unexpected
    raise TypeError(f"Cannot canonicalize type {type(obj).__name__}: {obj!r}")


# ============================================================================
# Main Runner
# ============================================================================

def run_parallel_simulation(
    cell_lines: Optional[List[str]] = None,
    compounds: Optional[List[str]] = None,
    mode: str = "full",
    workers: Optional[int] = None,
    db_path: str = "cell_thalamus_results.db",
    seed: int = 0,
    design_id: Optional[str] = None
) -> str:
    """Run parallel simulation."""

    if workers is None:
        workers = cpu_count()

    # Default parameters
    if cell_lines is None:
        cell_lines = ['A549', 'HepG2']
    if compounds is None:
        # Original 10 compounds from Cell Thalamus Phase 0
        compounds = ['tBHQ', 'H2O2', 'tunicamycin', 'thapsigargin', 'CCCP',
                    'oligomycin', 'etoposide', 'MG132', 'nocodazole', 'paclitaxel']

    # Generate deterministic design_id from ALL run-defining parameters
    # This prevents accidental design_id collisions when parameters vary
    design_id_overridden = False
    if design_id is None:
        # Build canonical dict of all parameters that affect outputs
        # CRITICAL: Hash the full VALUES, not just keys (changing IC50 must change design_id)
        design_params = {
            "mode": mode,
            "seed": seed,
            "cell_lines": sorted(cell_lines),
            "compounds": sorted(compounds),
            # Hash full values of all constants (not just keys!)
            # Changing CCCP IC50 or baseline morph values → different design_id
            "tech_cv": TECH_CV,
            "morph_cv": MORPH_CV,
            "baseline_morph": BASELINE_MORPH,  # Full values, not just keys
            "compound_params": COMPOUND_PARAMS,  # Full values, not just keys
            # Version marker (bump if simulation logic changes)
            # Human gate for non-parameter changes (algorithm tweaks, etc.)
            "sim_version": "2025-12-17-hash-values-not-keys"
        }

        # Canonicalize to handle numpy scalars, tuples, sets before JSON
        # Prevents silent stringification and ensures stable serialization
        canonical_params = canonicalize_for_json(design_params)

        # JSON dump with stable separators and sorted keys
        # CRITICAL: allow_nan=False → fail loudly on NaN/Infinity instead of cursed hash
        design_key = json.dumps(
            canonical_params,
            sort_keys=True,
            separators=(',', ':'),
            allow_nan=False  # Crash on non-finite floats (better than silent corruption)
        )
        design_hash = hashlib.blake2s(design_key.encode('utf-8'), digest_size=16).hexdigest()
        design_id = f"{design_hash[:8]}-{design_hash[8:12]}-{design_hash[12:16]}-{design_hash[16:20]}-{design_hash[20:]}"
    else:
        # User provided custom design_id (for intentional replicate separation)
        design_id_overridden = True

    logger.info("=" * 70)
    logger.info("PARALLEL CELL THALAMUS SIMULATION")
    logger.info("=" * 70)
    logger.info(f"Mode: {mode}")
    logger.info(f"Workers: {workers} CPUs")
    if design_id_overridden:
        logger.info(f"Design ID: {design_id} (OVERRIDE - intentional replicate separation)")
        logger.warning("⚠️  Custom design_id provided via --design-id flag")
        logger.warning("   This creates a new namespace with independent assay noise")
        logger.warning("   Same parameters will produce different results than deterministic run")
    else:
        logger.info(f"Design ID: {design_id} (deterministic from parameters)")

    # Generate design
    design = generate_design(cell_lines, compounds, mode)

    logger.info(f"Total wells: {len(design)}")

    # Save design
    db = CellThalamusDB(db_path=db_path)
    db.save_design(design_id, 0, cell_lines, compounds,
                   {'mode': mode, 'workers': workers})

    BATCH_SIZE = 5000
    # Prepare worker args
    worker_args = [(well, design_id) for well in design]

    # Execute in parallel
    logger.info(f"\nStarting parallel execution with {workers} workers...")
    start_time = time.time()

    # Wrap all inserts in a single transaction for maximum throughput
    # Sharp edge: If ANY duplicate well slips through, entire run rolls back (nothing inserted)
    # This is correct behavior - enforces all-or-nothing integrity via UNIQUE constraint
    logger.info(f"Beginning single transaction for all {len(design)} inserts (all-or-nothing commit)...")
    db.conn.execute("BEGIN")

    try:
        with Pool(processes=workers) as pool:
            batch = []
            saved = 0
            total_staged = 0  # Track total results staged in transaction (for rollback logging)

            # CRITICAL: Use imap() not imap_unordered() to preserve deterministic order
            # imap_unordered would insert results in completion order (nondeterministic)
            # imap preserves input order, ensuring workers=1 matches workers=64
            for i, result in enumerate(pool.imap(worker_function, worker_args), 1):
                if result:
                    batch.append(result)

                # Stream inserts (without committing each time)
                if len(batch) >= BATCH_SIZE:
                    # CRITICAL: Sort batch by stable key before insert
                    # Even with imap(), batch order depends on buffering, so sort explicitly
                    # Stable key matches UNIQUE INDEX: (design_id, plate_id, cell_line, well_id)
                    # Extra fields (compound, dose, timepoint) included for clarity, but redundant
                    # float() coercion prevents type instability (10 vs 10.0)
                    batch.sort(key=lambda r: (
                        r['design_id'],
                        r['plate_id'],
                        r['cell_line'],
                        r['well_id'],
                        r['compound'],
                        float(r['dose_uM']),
                        float(r['timepoint_h'])
                    ))
                    db.insert_results_batch(batch, commit=False)
                    saved += len(batch)
                    total_staged += len(batch)
                    batch.clear()

                if i % 100 == 0:
                    elapsed = time.time() - start_time
                    rate = i / elapsed
                    remaining = (len(design) - i) / rate
                    logger.info(f"Progress: {i}/{len(design)} ({i/len(design)*100:.1f}%) - "
                              f"Rate: {rate:.1f} wells/sec - ETA: {remaining:.1f}s")

            # Flush remainder
            if batch:
                # CRITICAL: Sort final batch too
                batch.sort(key=lambda r: (
                    r['design_id'],
                    r['plate_id'],
                    r['cell_line'],
                    r['well_id'],
                    r['compound'],
                    float(r['dose_uM']),
                    float(r['timepoint_h'])
                ))
                db.insert_results_batch(batch, commit=False)
                saved += len(batch)
                total_staged += len(batch)
                batch.clear()

        # Commit entire transaction at the end
        logger.info(f"Committing transaction with {total_staged} results...")
        db.conn.commit()
        logger.info(f"✓ Transaction committed successfully")
    except Exception as e:
        db.conn.rollback()
        logger.error(
            f"Transaction FAILED and rolled back: {e}\n"
            f"  Results staged before failure: {total_staged}\n"
            f"  Wells processed before failure: {i}/{len(design)}\n"
            f"  All results discarded - no partial data written to DB"
        )
        raise

    elapsed = time.time() - start_time

    logger.info(f"\nSaved {saved} results total.")
    db.close()

    # Statistics
    logger.info("=" * 70)
    logger.info("✓ SIMULATION COMPLETE!")
    logger.info("=" * 70)
    logger.info(f"Total wells: {len(design)}")
    logger.info(f"Successful: {saved}")
    logger.info(f"Total time: {elapsed:.2f}s ({elapsed/60:.2f} min)")
    logger.info(f"Per well: {elapsed/len(design):.3f}s")
    logger.info(f"Throughput: {len(design)/elapsed:.1f} wells/sec")
    logger.info(f"Design ID: {design_id}")
    logger.info(f"Database: {db_path}")
    logger.info("=" * 70)

    return design_id


def run_stream_isolation_self_test(seed: int = 0):
    """
    Self-test: prove that RNG streams are isolated (assay doesn't perturb physics).

    This calls the ACTUAL simulation code path (simulate_well) TWICE to verify:
    1. RNG streams don't couple (bit_generator.state check)
    2. Physics outputs are identical (adversarial check - cell fate unchanged)

    This catches regressions where someone accidentally uses rng_growth in measurement code.
    """
    print("\n" + "=" * 80)
    print("STREAM ISOLATION SELF-TEST (ADVERSARIAL)")
    print("=" * 80)
    print(f"Testing observer-independent physics with seed={seed}...\n")

    # Test 1: Run simulation, check RNG streams don't couple
    print("Test 1/2: RNG stream coupling check...")
    global _RNG_STREAMS
    _RNG_STREAMS = RNGStreams(seed=seed)

    # Snapshot initial state
    growth_state_before = _RNG_STREAMS.rng_growth.bit_generator.state
    treatment_state_before = _RNG_STREAMS.rng_treatment.bit_generator.state
    assay_state_before = _RNG_STREAMS.rng_assay.bit_generator.state

    # Call ACTUAL simulation code (not just rng_assay.normal)
    test_well = WellAssignment(
        well_id='A01',
        cell_line='A549',
        compound='tBHQ',
        dose_uM=10.0,
        timepoint_h=12.0,
        plate_id='TestPlate',
        day=1,
        operator='TestOp',
        is_sentinel=False
    )

    # Run the actual simulation (this consumes RNG for morphology, LDH, etc.)
    result1 = simulate_well(test_well, design_id='self_test')

    if result1 is None:
        print("❌ FAIL: simulate_well() returned None (simulation error)")
        sys.exit(1)

    # Snapshot final state
    growth_state_after = _RNG_STREAMS.rng_growth.bit_generator.state
    treatment_state_after = _RNG_STREAMS.rng_treatment.bit_generator.state
    assay_state_after = _RNG_STREAMS.rng_assay.bit_generator.state

    # Check isolation
    growth_changed = (growth_state_before != growth_state_after)
    treatment_changed = (treatment_state_before != treatment_state_after)
    assay_changed = (assay_state_before != assay_state_after)

    print(f"  rng_growth changed:    {growth_changed}")
    print(f"  rng_treatment changed: {treatment_changed}")
    print(f"  rng_assay changed:     {assay_changed}")

    if growth_changed or treatment_changed:
        print("❌ FAIL: simulate_well() perturbed physics RNG streams!")
        print("   Likely cause: someone used rng_growth or rng_treatment in assay code")
        sys.exit(1)

    # NOTE: rng_assay may not change because we use per-well deterministic RNG for measurements
    # This is correct - measurement noise is addressable by well key, not consumption order
    print("  ✓ Physics RNG streams properly isolated")
    print("  Note: Measurement noise uses per-well RNG (not global rng_assay)")
    print()

    # Test 2: Run AGAIN with same physics seed, check physics outputs match
    print("Test 2/2: Physics output stability check (adversarial)...")
    _RNG_STREAMS = RNGStreams(seed=seed)  # Reset to same seed

    # Run second simulation (same well, same seed, fresh RNG state)
    result2 = simulate_well(test_well, design_id='self_test')

    if result2 is None:
        print("❌ FAIL: Second simulate_well() returned None")
        sys.exit(1)

    # Compare PHYSICS outputs (viability, death accounting)
    # These must be bit-identical since we reset RNG to same seed
    viability_match = (result1['viability'] == result2['viability'])
    death_compound_match = (result1['death_compound'] == result2['death_compound'])
    death_unknown_match = (result1['death_unknown'] == result2['death_unknown'])

    print(f"  viability match:      {viability_match} ({result1['viability']:.6f})")
    print(f"  death_compound match: {death_compound_match} ({result1['death_compound']:.6f})")
    print(f"  death_unknown match:  {death_unknown_match} ({result1['death_unknown']:.6f})")

    if not (viability_match and death_compound_match and death_unknown_match):
        print("❌ FAIL: Physics outputs differ despite same seed!")
        print("   This means cell fate is nondeterministic (RNG coupling or hidden state)")
        sys.exit(1)

    print("  ✓ Physics outputs bit-identical (cell fate deterministic)")
    print()

    print("✅ PASS: Stream isolation verified (adversarial)")
    print("   ✓ RNG streams don't couple (bit_generator.state)")
    print("   ✓ Physics outputs identical (cell fate unchanged)")
    print()
    print("Actual simulation code path tested with adversarial check.")
    print("Ready for production deployment with observer-independent physics guarantee.")
    print("=" * 80)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Cell Thalamus Parallel Simulation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full campaign with all CPUs
  python standalone_cell_thalamus.py --mode full --seed 0

  # Use 32 workers
  python standalone_cell_thalamus.py --mode full --workers 32 --seed 0

  # Quick test
  python standalone_cell_thalamus.py --mode demo --workers 4 --seed 0

  # Self-test stream isolation
  python standalone_cell_thalamus.py --self-test
        """
    )

    parser.add_argument('--mode', choices=['demo', 'benchmark', 'full', 'portfolio'], default='full')
    parser.add_argument('--workers', type=int, default=None)
    parser.add_argument('--db-path', default='cell_thalamus_results.db')
    parser.add_argument('--out', type=str, default=None,
                        help='Output directory for deterministic artifact comparison')
    parser.add_argument('--portfolio-json', type=str, help='JSON string with portfolio configuration for autonomous loop')
    parser.add_argument('--seed', type=int, default=0,
                        help='RNG seed for reproducibility (default: 0 for fully deterministic)')
    parser.add_argument('--design-id', type=str, default=None,
                        help='Override design_id (for intentional replicate separation). Default: deterministic from parameters.')
    parser.add_argument('--self-test', action='store_true',
                        help='Run stream isolation self-test and exit')

    args = parser.parse_args()

    # Startup logging (receipts for debugging cross-machine issues)
    print("=" * 80)
    print("STANDALONE CELL THALAMUS")
    print("=" * 80)
    print(f"Script:       {__file__}")
    print(f"Python:       {sys.version.split()[0]}")
    print(f"NumPy:        {np.__version__}")
    print(f"Platform:     {os.uname().sysname} {os.uname().release} {os.uname().machine}")
    print(f"Seed:         {args.seed}")
    print(f"Workers:      {args.workers or 'auto'}")
    print(f"Mode:         {args.mode}")
    if args.out:
        print(f"Output dir:   {args.out}")
    print("=" * 80)
    print()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Self-test mode (stream isolation check)
    if args.self_test:
        run_stream_isolation_self_test(args.seed)
        sys.exit(0)

    # Initialize global RNG streams with explicit seed (cross-machine determinism)
    global _RNG_STREAMS
    _RNG_STREAMS = RNGStreams(seed=args.seed)
    logger.info(f"Initialized RNG streams with seed={args.seed}")

    # Handle output directory
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        args.db_path = os.path.join(args.out, os.path.basename(args.db_path))

    design_id = run_parallel_simulation(
        mode=args.mode,
        workers=args.workers,
        db_path=args.db_path,
        seed=args.seed,
        design_id=args.design_id
    )

    print(f"\n✓ Complete! Design ID: {design_id}")
    print(f"Results saved to: {args.db_path}")

    # Auto-upload to S3 if running on JupyterHub/AWS
    try:
        import boto3
        S3_BUCKET = 'insitro-user'
        S3_KEY = 'brig/cell_thalamus_results.db'

        print(f"\n📤 Auto-uploading to S3...")
        s3 = boto3.client('s3')
        s3.upload_file(args.db_path, S3_BUCKET, S3_KEY)
        print(f"✅ Uploaded to s3://{S3_BUCKET}/{S3_KEY}")
        print(f"\n🔄 On your Mac, run: ./scripts/sync_aws_db.sh")
        print(f"   Then view at: http://localhost:5173/cell-thalamus")
    except ImportError:
        # boto3 not available - probably running locally
        print(f"\nNext steps:")
        print(f"1. Open Cell Thalamus dashboard: http://localhost:5173/cell-thalamus")
        print(f"2. Select this run to visualize results across all tabs")
    except Exception as e:
        print(f"\n⚠️  S3 upload failed: {e}")
        print(f"   Manual upload: aws s3 cp {args.db_path} s3://insitro-user/brig/cell_thalamus_results.db")


if __name__ == "__main__":
    main()
