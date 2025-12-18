#!/usr/bin/env python3
"""
Standalone Design Comparison for AWS/JupyterHub
Last Updated: December 16, 2025

Self-contained script to run v1, v2, v3 designs head-to-head.
All design data embedded - no external files needed!

Compares:
- v1: Full 96-well, mixed cell lines (2304 wells)
- v2: 88-well with buffer corners, separated cell lines (2112 wells)
- v3: Full 96-well, checkerboard cell lines (1152 wells)

Usage:
    # Run with 64 workers (~8 minutes on c5.18xlarge)
    python standalone_design_comparison.py --workers 64

    # Run single-threaded (for debugging)
    python standalone_design_comparison.py --workers 1

Requirements:
    pip install numpy scipy tqdm

Output:
    - SQLite database: design_comparison_results.db
    - Text report: design_comparison_report.txt
"""

import argparse
import time
import logging
import uuid
import sqlite3
import os
import json
from typing import List, Dict, Any, Optional, Tuple
from multiprocessing import Pool, cpu_count
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

import numpy as np
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# Embedded Design Data (URLs for download from S3/GitHub)
# ============================================================================

DESIGN_FILES = {
    'v1': 'phase0_design_v1_basic.json',
    'v2': 'phase0_design_v2_controls_stratified.json',
    'v3': 'phase0_design_v3_mixed_celllines_checkerboard.json',
}

# For standalone mode, designs should be in same directory or provide S3 URLs
DESIGNS_DIR = Path(__file__).parent / "data" / "designs"


# ============================================================================
# Database Module
# ============================================================================

class ComparisonDB:
    """Lightweight database for design comparison results"""

    def __init__(self, db_path: str = "design_comparison_results.db"):
        self.db_path = os.path.abspath(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self._create_schema()
        logger.info(f"Connected to DB: {self.db_path}")

    def _create_schema(self):
        """Create tables"""
        cursor = self.conn.cursor()

        # Designs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS designs (
                design_id TEXT PRIMARY KEY,
                version TEXT,
                description TEXT,
                n_plates INTEGER,
                n_wells INTEGER,
                created_at TEXT
            )
        """)

        # Results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                design_id TEXT,
                well_id TEXT,
                cell_line TEXT,
                compound TEXT,
                dose_uM REAL,
                timepoint_h REAL,
                plate_id TEXT,
                is_sentinel INTEGER,
                morph_er REAL,
                morph_mito REAL,
                morph_nucleus REAL,
                morph_actin REAL,
                morph_rna REAL,
                atp_signal REAL,  -- Actually LDH cytotoxicity (kept name for backward compat)
                FOREIGN KEY (design_id) REFERENCES designs(design_id)
            )
        """)

        # Metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comparison_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                design_id TEXT,
                metric_name TEXT,
                metric_value REAL,
                timepoint_h REAL,
                FOREIGN KEY (design_id) REFERENCES designs(design_id)
            )
        """)

        self.conn.commit()

    def save_design(self, design_id: str, version: str, description: str, n_plates: int, n_wells: int):
        """Save design metadata"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO designs (design_id, version, description, n_plates, n_wells, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (design_id, version, description, n_plates, n_wells, datetime.now().isoformat()))
        self.conn.commit()

    def insert_results_batch(self, results: List[Dict]):
        """Batch insert results"""
        cursor = self.conn.cursor()
        for r in results:
            cursor.execute("""
                INSERT INTO results (
                    design_id, well_id, cell_line, compound, dose_uM, timepoint_h,
                    plate_id, is_sentinel,
                    morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna, atp_signal
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r['design_id'], r['well_id'], r['cell_line'], r['compound'], r['dose_uM'],
                r['timepoint_h'], r['plate_id'], int(r['is_sentinel']),
                r['morphology']['ER'], r['morphology']['Mito'], r['morphology']['Nucleus'],
                r['morphology']['Actin'], r['morphology']['RNA'], r['atp_signal']
            ))
        self.conn.commit()

    def get_results(self, design_id: str) -> List[Dict]:
        """Get all results for a design"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT well_id, cell_line, compound, dose_uM, timepoint_h, plate_id,
                   is_sentinel, morph_er, morph_mito, morph_nucleus, morph_actin, morph_rna, atp_signal
            FROM results WHERE design_id = ?
        """, (design_id,))

        results = []
        for row in cursor.fetchall():
            results.append({
                'well_id': row[0],
                'cell_line': row[1],
                'compound': row[2],
                'dose_uM': row[3],
                'timepoint_h': row[4],
                'plate_id': row[5],
                'is_sentinel': bool(row[6]),
                'morph_er': row[7],
                'morph_mito': row[8],
                'morph_nucleus': row[9],
                'morph_actin': row[10],
                'morph_rna': row[11],
                'atp_signal': row[12],
            })
        return results

    def save_metric(self, design_id: str, metric_name: str, metric_value: float, timepoint_h: float = None):
        """Save a comparison metric"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO comparison_metrics (design_id, metric_name, metric_value, timepoint_h)
            VALUES (?, ?, ?, ?)
        """, (design_id, metric_name, metric_value, timepoint_h))
        self.conn.commit()

    def close(self):
        self.conn.close()


# ============================================================================
# Biological Simulation (simplified version from standalone)
# ============================================================================

@dataclass
class WellAssignment:
    well_id: str
    cell_line: str
    compound: str
    dose_uM: float
    timepoint_h: float
    plate_id: str
    is_sentinel: bool


# Simplified compound parameters
COMPOUND_PARAMS = {
    'tBHQ': {'ec50_uM': 30.0, 'hill': 2.0},
    'H2O2': {'ec50_uM': 100.0, 'hill': 2.0},
    'tunicamycin': {'ec50_uM': 1.0, 'hill': 2.5},
    'thapsigargin': {'ec50_uM': 0.5, 'hill': 3.0},
    'CCCP': {'ec50_uM': 5.0, 'hill': 2.5},
    'oligomycin': {'ec50_uM': 1.0, 'hill': 2.0},
    'etoposide': {'ec50_uM': 10.0, 'hill': 1.8},
    'MG132': {'ec50_uM': 1.0, 'hill': 2.2},
    'nocodazole': {'ec50_uM': 0.5, 'hill': 2.5},
    'paclitaxel': {'ec50_uM': 0.01, 'hill': 3.0},
    'DMSO': {'ec50_uM': 1e9, 'hill': 1.0},
}


def simulate_well(well: WellAssignment) -> Dict:
    """Simulate a single well (fast version)"""
    # Simplified Hill equation
    params = COMPOUND_PARAMS.get(well.compound, {'ec50_uM': 10.0, 'hill': 2.0})

    if well.compound == 'DMSO' or well.dose_uM == 0:
        viability = 1.0
    else:
        viability = 1.0 / (1.0 + (well.dose_uM / params['ec50_uM']) ** params['hill'])

    # Simplified morphology (5 channels)
    # Add noise proportional to (1 - viability)
    stress_level = 1.0 - viability
    noise_scale = 0.1 + 0.4 * stress_level

    morphology = {
        'ER': np.clip(np.random.normal(0.5 + 0.5 * stress_level, noise_scale), 0, 1),
        'Mito': np.clip(np.random.normal(0.5 + 0.4 * stress_level, noise_scale), 0, 1),
        'Nucleus': np.clip(np.random.normal(0.3 + 0.3 * stress_level, noise_scale), 0, 1),
        'Actin': np.clip(np.random.normal(0.4 + 0.2 * stress_level, noise_scale), 0, 1),
        'RNA': np.clip(np.random.normal(0.5 + 0.3 * stress_level, noise_scale), 0, 1),
    }

    # LDH cytotoxicity signal (inverse of viability)
    # High viability → Low LDH, Low viability → High LDH
    death_fraction = 1.0 - viability
    baseline_ldh = 50000.0
    ldh_signal = baseline_ldh * death_fraction * (0.8 + 0.4 * np.random.random())  # With noise
    atp_signal = ldh_signal  # Keep variable name for backward compat

    return {
        'design_id': '',  # Will be filled in
        'well_id': well.well_id,
        'cell_line': well.cell_line,
        'compound': well.compound,
        'dose_uM': well.dose_uM,
        'timepoint_h': well.timepoint_h,
        'plate_id': well.plate_id,
        'is_sentinel': well.is_sentinel,
        'morphology': morphology,
        'atp_signal': float(atp_signal),
    }


def worker_execute_well(args):
    """Worker function for parallel execution"""
    well, design_id = args
    result = simulate_well(well)
    result['design_id'] = design_id
    return result


# ============================================================================
# Design Loader
# ============================================================================

def load_design_file(filename: str) -> Dict:
    """Load design JSON from file"""
    design_path = DESIGNS_DIR / filename

    if not design_path.exists():
        raise FileNotFoundError(f"Design file not found: {design_path}")

    with open(design_path, 'r') as f:
        return json.load(f)


# ============================================================================
# Comparison Runner
# ============================================================================

def run_design(design_data: Dict, db: ComparisonDB, n_workers: int) -> str:
    """Execute a design in parallel"""
    design_id = design_data['design_id']
    metadata = design_data.get('metadata', {})
    wells_data = design_data['wells']

    logger.info(f"\n{'='*80}")
    logger.info(f"RUNNING: {design_id}")
    logger.info(f"Description: {design_data['description']}")
    logger.info(f"Wells: {len(wells_data)}, Plates: {metadata.get('n_plates', 'N/A')}")
    logger.info(f"{'='*80}")

    # Save design metadata
    db.save_design(
        design_id=design_id,
        version=design_data.get('version', 'v1'),
        description=design_data['description'],
        n_plates=metadata.get('n_plates', 0),
        n_wells=len(wells_data)
    )

    # Convert to WellAssignment objects
    wells = []
    for w in wells_data:
        wells.append(WellAssignment(
            well_id=w['well_id'],
            cell_line=w['cell_line'],
            compound=w['compound'],
            dose_uM=w['dose_uM'],
            timepoint_h=w['timepoint_h'],
            plate_id=w['plate_id'],
            is_sentinel=w.get('is_sentinel', False)
        ))

    # Execute in parallel
    start_time = time.time()
    logger.info(f"Executing {len(wells)} wells with {n_workers} workers...")

    with Pool(processes=n_workers) as pool:
        work_items = [(well, design_id) for well in wells]

        results = list(tqdm(
            pool.imap(worker_execute_well, work_items, chunksize=50),
            total=len(wells),
            desc=f"{design_id[:20]}"
        ))

    # Save results in batches
    batch_size = 500
    for i in range(0, len(results), batch_size):
        db.insert_results_batch(results[i:i+batch_size])

    elapsed = time.time() - start_time
    logger.info(f"✓ Completed {len(results)} wells in {elapsed:.1f}s ({len(results)/elapsed:.1f} wells/s)")

    return design_id


def fit_dose_response_bootstrap(doses, responses, n_bootstrap=100):
    """
    Fit Hill equation with bootstrap confidence intervals

    Returns: (ec50_mean, ec50_ci_width, hill_mean, hill_ci_width, n_samples)
    """
    from scipy.optimize import curve_fit

    def hill_equation(dose, ec50, hill, top, bottom):
        return bottom + (top - bottom) / (1 + (dose / ec50) ** hill)

    # Filter out zero doses for fitting
    nonzero = [(d, r) for d, r in zip(doses, responses) if d > 0]
    if len(nonzero) < 3:
        return None, None, None, None, len(doses)

    doses_fit = np.array([d for d, r in nonzero])
    responses_fit = np.array([r for d, r in nonzero])

    # Initial parameter guess
    try:
        # Fit original data
        params, _ = curve_fit(
            hill_equation,
            doses_fit,
            responses_fit,
            p0=[np.median(doses_fit), 2.0, 1.0, 0.0],
            bounds=([doses_fit.min()*0.1, 0.5, 0.5, 0.0],
                    [doses_fit.max()*10, 5.0, 1.5, 0.5]),
            maxfev=5000
        )

        # Bootstrap resampling
        ec50_samples = []
        hill_samples = []

        for _ in range(n_bootstrap):
            # Resample with replacement
            indices = np.random.choice(len(doses_fit), len(doses_fit), replace=True)
            d_boot = doses_fit[indices]
            r_boot = responses_fit[indices]

            try:
                params_boot, _ = curve_fit(
                    hill_equation,
                    d_boot,
                    r_boot,
                    p0=params,
                    bounds=([doses_fit.min()*0.1, 0.5, 0.5, 0.0],
                            [doses_fit.max()*10, 5.0, 1.5, 0.5]),
                    maxfev=5000
                )
                ec50_samples.append(params_boot[0])
                hill_samples.append(params_boot[1])
            except:
                pass

        if len(ec50_samples) < 10:
            return None, None, None, None, len(doses)

        # Compute confidence intervals (95%)
        ec50_ci = np.percentile(ec50_samples, [2.5, 97.5])
        hill_ci = np.percentile(hill_samples, [2.5, 97.5])

        ec50_mean = np.mean(ec50_samples)
        hill_mean = np.mean(hill_samples)

        ec50_ci_width = ec50_ci[1] - ec50_ci[0]
        hill_ci_width = hill_ci[1] - hill_ci[0]

        return ec50_mean, ec50_ci_width, hill_mean, hill_ci_width, len(doses)

    except Exception as e:
        return None, None, None, None, len(doses)


def compute_statistical_power(design_id: str, db: ComparisonDB) -> Dict:
    """Compute statistical power metrics via dose-response fitting"""
    results = db.get_results(design_id)

    if not results:
        return {}

    # Group by compound, cell line, timepoint
    groups = {}
    for r in results:
        if r['is_sentinel']:
            continue

        key = (r['compound'], r['cell_line'], r['timepoint_h'])
        if key not in groups:
            groups[key] = []
        groups[key].append(r)

    # Fit dose-response curves
    power_metrics = {}
    successful_fits = 0
    total_conditions = len(groups)

    logger.info(f"  Fitting dose-response curves for {total_conditions} conditions...")

    for (compound, cell_line, tp), wells in groups.items():
        if compound == 'DMSO':
            continue

        doses = [w['dose_uM'] for w in wells]
        responses = [w['atp_signal'] for w in wells]  # atp_signal contains LDH values

        ec50_mean, ec50_ci_width, hill_mean, hill_ci_width, n_samples = fit_dose_response_bootstrap(
            doses, responses, n_bootstrap=50
        )

        if ec50_mean is not None:
            key_name = f"{compound}_{cell_line}_T{int(tp)}h"
            power_metrics[key_name] = {
                'ec50_mean': ec50_mean,
                'ec50_ci_width': ec50_ci_width,
                'hill_mean': hill_mean,
                'hill_ci_width': hill_ci_width,
                'n_samples': n_samples
            }
            successful_fits += 1

    logger.info(f"  Successfully fit {successful_fits}/{total_conditions} curves")

    return power_metrics


def compute_simple_metrics(design_id: str, db: ComparisonDB) -> Dict:
    """Compute simplified comparison metrics"""
    results = db.get_results(design_id)

    if not results:
        return {}

    # Basic counts
    metrics = {
        'design_id': design_id,
        'n_wells': len(results),
        'n_sentinels': sum(1 for r in results if r['is_sentinel']),
        'n_experimental': sum(1 for r in results if not r['is_sentinel']),
    }

    # Group by cell line to show per-cell-line replication
    cell_line_counts = {}
    for r in results:
        cl = r['cell_line']
        if cl not in cell_line_counts:
            cell_line_counts[cl] = 0
        cell_line_counts[cl] += 1

    metrics['cell_line_counts'] = cell_line_counts

    # Group by timepoint
    timepoint_groups = {}
    for r in results:
        tp = r['timepoint_h']
        if tp not in timepoint_groups:
            timepoint_groups[tp] = []
        timepoint_groups[tp].append(r)

    # Compute per-timepoint variance (simplified)
    for tp, tp_results in timepoint_groups.items():
        sentinels = [r for r in tp_results if r['is_sentinel']]

        if len(sentinels) > 1:
            # Sentinel stability (CV of LDH across sentinels)
            ldh_values = [r['atp_signal'] for r in sentinels]  # atp_signal contains LDH
            cv = np.std(ldh_values) / np.mean(ldh_values) if np.mean(ldh_values) > 0 else 999

            metrics[f'T{int(tp)}h_sentinel_cv'] = cv
            db.save_metric(design_id, 'sentinel_cv', cv, tp)

            # Morphology variance (trace of covariance)
            morph_matrix = np.array([[
                r['morph_er'], r['morph_mito'], r['morph_nucleus'], r['morph_actin'], r['morph_rna']
            ] for r in sentinels])

            if len(morph_matrix) > 1:
                cov = np.cov(morph_matrix.T)
                trace = np.trace(cov)

                metrics[f'T{int(tp)}h_morph_variance'] = trace
                db.save_metric(design_id, 'morph_variance', trace, tp)

    # Statistical power analysis
    logger.info(f"Computing statistical power for {design_id}...")
    power_metrics = compute_statistical_power(design_id, db)

    # Aggregate CI widths
    if power_metrics:
        ec50_widths = [pm['ec50_ci_width'] for pm in power_metrics.values() if pm['ec50_ci_width'] is not None]
        if ec50_widths:
            metrics['mean_ec50_ci_width'] = np.mean(ec50_widths)
            metrics['median_ec50_ci_width'] = np.median(ec50_widths)
            db.save_metric(design_id, 'mean_ec50_ci_width', np.mean(ec50_widths), None)

    return metrics


def generate_report(all_metrics: List[Dict]) -> str:
    """Generate comparison report"""
    report = []
    report.append("\n" + "="*80)
    report.append("DESIGN COMPARISON REPORT - WITH STATISTICAL POWER")
    report.append("="*80 + "\n")

    # Overview
    report.append("OVERVIEW")
    report.append("-" * 80)
    report.append(f"{'Design':<45} {'Wells':<10} {'Sentinels':<12} {'Experimental':<12}")
    report.append("-" * 80)

    for m in all_metrics:
        report.append(f"{m['design_id']:<45} {m['n_wells']:<10} {m['n_sentinels']:<12} {m['n_experimental']:<12}")

    report.append("")

    # Per-cell-line replication
    report.append("\nPER-CELL-LINE REPLICATION")
    report.append("-" * 80)
    report.append(f"{'Design':<45} {'A549 wells':<15} {'HepG2 wells':<15}")
    report.append("-" * 80)

    for m in all_metrics:
        cl_counts = m.get('cell_line_counts', {})
        a549 = cl_counts.get('A549', 0)
        hepg2 = cl_counts.get('HepG2', 0)

        report.append(f"{m['design_id']:<45} {a549:<15} {hepg2:<15}")

    report.append("")

    # Sentinel stability
    report.append("\nSENTINEL STABILITY (CV of LDH - lower is better)")
    report.append("-" * 80)
    report.append(f"{'Design':<45} {'T12h CV':<15} {'T48h CV':<15}")
    report.append("-" * 80)

    for m in all_metrics:
        cv_12h = m.get('T12h_sentinel_cv', 999)
        cv_48h = m.get('T48h_sentinel_cv', 999)

        cv_12h_str = f"{cv_12h:.3f}" if cv_12h < 999 else "N/A"
        cv_48h_str = f"{cv_48h:.3f}" if cv_48h < 999 else "N/A"

        report.append(f"{m['design_id']:<45} {cv_12h_str:<15} {cv_48h_str:<15}")

    report.append("")

    # Statistical power (EC50 confidence interval width)
    report.append("\nSTATISTICAL POWER (Mean EC50 CI Width - lower is better)")
    report.append("-" * 80)
    report.append(f"{'Design':<45} {'Mean CI Width (µM)':<20} {'Interpretation':<30}")
    report.append("-" * 80)

    for m in all_metrics:
        ci_width = m.get('mean_ec50_ci_width', None)

        if ci_width is not None:
            ci_str = f"{ci_width:.2f}"

            if ci_width < 5.0:
                interp = "HIGH POWER ✓"
            elif ci_width < 15.0:
                interp = "MODERATE POWER"
            else:
                interp = "LOW POWER ✗"

            report.append(f"{m['design_id']:<45} {ci_str:<20} {interp:<30}")
        else:
            report.append(f"{m['design_id']:<45} {'N/A':<20} {'Failed to fit':<30}")

    report.append("")

    # Morphology variance
    report.append("\nMORPHOLOGY VARIANCE (Trace of Cov)")
    report.append("-" * 80)
    report.append(f"{'Design':<45} {'T12h Var':<15} {'T48h Var':<15}")
    report.append("-" * 80)

    for m in all_metrics:
        var_12h = m.get('T12h_morph_variance', 999)
        var_48h = m.get('T48h_morph_variance', 999)

        var_12h_str = f"{var_12h:.3f}" if var_12h < 999 else "N/A"
        var_48h_str = f"{var_48h:.3f}" if var_48h < 999 else "N/A"

        report.append(f"{m['design_id']:<45} {var_12h_str:<15} {var_48h_str:<15}")

    report.append("")

    # Summary interpretation
    report.append("\nKEY TRADE-OFFS")
    report.append("-" * 80)

    # Find designs
    v2 = next((m for m in all_metrics if 'v2' in m['design_id']), None)
    v3 = next((m for m in all_metrics if 'v3' in m['design_id']), None)

    if v2 and v3:
        v2_a549 = v2.get('cell_line_counts', {}).get('A549', 0)
        v3_a549 = v3.get('cell_line_counts', {}).get('A549', 0)

        v2_ci = v2.get('mean_ec50_ci_width', 999)
        v3_ci = v3.get('mean_ec50_ci_width', 999)

        report.append(f"v2: {v2_a549} wells per cell line, CI width = {v2_ci:.2f} µM")
        report.append(f"v3: {v3_a549} wells per cell line, CI width = {v3_ci:.2f} µM")
        report.append("")

        replication_ratio = v2_a549 / v3_a549 if v3_a549 > 0 else 0
        ci_ratio = v3_ci / v2_ci if v2_ci > 0 else 0

        report.append(f"v3 has {replication_ratio:.1f}× FEWER replicates per cell line")
        report.append(f"v3 has {ci_ratio:.2f}× WIDER confidence intervals (less power)")
        report.append("")

        if ci_ratio < 1.3:
            report.append("✓ VERDICT: v3's power loss is ACCEPTABLE (< 30% wider CIs)")
            report.append("  Throughput gain (50% fewer plates) outweighs small power loss")
        elif ci_ratio < 1.5:
            report.append("~ VERDICT: v3's power loss is MODERATE (30-50% wider CIs)")
            report.append("  Trade-off depends on cost constraints and use case")
        else:
            report.append("✗ VERDICT: v3's power loss is SEVERE (> 50% wider CIs)")
            report.append("  Throughput gain may not be worth loss of statistical power")

    report.append("\n" + "="*80 + "\n")

    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Design Comparison Runner")
    parser.add_argument("--workers", type=int, default=cpu_count(), help="Number of parallel workers")
    parser.add_argument("--db", type=str, default="design_comparison_results.db", help="Output database path")
    args = parser.parse_args()

    logger.info(f"Starting design comparison with {args.workers} workers")
    logger.info(f"Output database: {args.db}\n")

    # Initialize database
    db = ComparisonDB(db_path=args.db)

    # Run all designs
    all_metrics = []

    for version in ['v1', 'v2', 'v3']:
        try:
            filename = DESIGN_FILES[version]
            design_data = load_design_file(filename)

            # Run design
            design_id = run_design(design_data, db, args.workers)

            # Compute metrics
            metrics = compute_simple_metrics(design_id, db)
            all_metrics.append(metrics)

        except Exception as e:
            logger.error(f"Failed to run {version}: {e}")
            import traceback
            traceback.print_exc()

    # Generate report
    report = generate_report(all_metrics)
    print(report)

    # Save report
    report_path = "design_comparison_report.txt"
    with open(report_path, 'w') as f:
        f.write(report)

    logger.info(f"\n✓ Comparison complete!")
    logger.info(f"  Database: {args.db}")
    logger.info(f"  Report: {report_path}")

    db.close()


if __name__ == "__main__":
    main()
