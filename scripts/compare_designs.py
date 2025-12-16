#!/usr/bin/env python3
"""
Design Comparison Script - Run v1, v2, v3 head-to-head

Executes all three Phase 0 designs and compares:
- Geometry preservation
- Sentinel drift
- Technical vs biological variance
- Throughput efficiency
- Chart health metrics
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.cell_thalamus.thalamus_agent import CellThalamusAgent
from cell_os.hardware.biological_virtual import BiologicalVirtualMachine
from cell_os.database.cell_thalamus_db import CellThalamusDB
from cell_os.cell_thalamus.design_generator import WellAssignment
from cell_os.cell_thalamus.variance_analysis import VarianceAnalyzer
from cell_os.cell_thalamus.boundary_detection import analyze_boundaries, SentinelSpec
from cell_os.cell_thalamus.manifold_charts import create_chart_from_integration_test

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


class DesignComparator:
    """Compare multiple design versions head-to-head"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(Path(__file__).parent.parent / "data" / "cell_thalamus_comparison.db")
        self.designs_dir = Path(__file__).parent.parent / "data" / "designs"
        self.results = {}

    def load_design_file(self, filename: str) -> Dict[str, Any]:
        """Load design JSON file"""
        design_path = self.designs_dir / filename
        logger.info(f"Loading design from {design_path}")

        with open(design_path, 'r') as f:
            return json.load(f)

    def run_design_from_file(self, design_data: Dict[str, Any]) -> str:
        """Execute a design from loaded JSON data"""
        design_id = design_data['design_id']
        logger.info(f"\n{'='*80}")
        logger.info(f"RUNNING DESIGN: {design_id}")
        logger.info(f"Description: {design_data['description']}")
        logger.info(f"{'='*80}\n")

        # Create fresh hardware and DB for this design
        hardware = BiologicalVirtualMachine()
        db = CellThalamusDB(db_path=self.db_path)
        agent = CellThalamusAgent(phase=0, hardware=hardware, db=db)
        agent.design_id = design_id

        # Extract metadata
        metadata = design_data.get('metadata', {})
        wells_data = design_data['wells']

        logger.info(f"Design metadata:")
        logger.info(f"  Plates: {metadata.get('n_plates', 'N/A')}")
        logger.info(f"  Wells: {len(wells_data)}")
        logger.info(f"  Cell lines: {metadata.get('cell_lines', 'N/A')}")
        logger.info(f"  Timepoints: {metadata.get('timepoints_h', 'N/A')}")

        # Save design to database
        db.save_design(
            design_id=design_id,
            phase=0,
            cell_lines=metadata.get('cell_lines', []),
            compounds=list(set(w['compound'] for w in wells_data)),
            metadata={
                'design_type': design_data.get('design_type'),
                'description': design_data.get('description'),
                'original_metadata': metadata
            }
        )

        # Convert wells to WellAssignment objects
        wells = []
        for well_data in wells_data:
            wells.append(WellAssignment(
                well_id=well_data['well_id'],
                cell_line=well_data['cell_line'],
                compound=well_data['compound'],
                dose_uM=well_data['dose_uM'],
                timepoint_h=well_data['timepoint_h'],
                plate_id=well_data['plate_id'],
                day=well_data.get('day', 1),
                operator=well_data.get('operator', 'Operator_A'),
                is_sentinel=well_data.get('is_sentinel', False)
            ))

        # Execute wells with progress
        logger.info(f"\nExecuting {len(wells)} wells...")
        results = []

        for idx, well in enumerate(wells, 1):
            if idx % 100 == 0:
                logger.info(f"  Progress: {idx}/{len(wells)} wells ({100*idx//len(wells)}%)")

            result = agent._execute_well(well)
            if result:
                results.append(result)
                db.insert_results_batch([result])

        logger.info(f"✓ Completed {len(results)} wells")

        return design_id

    def compute_metrics(self, design_id: str) -> Dict[str, Any]:
        """Compute comparison metrics for a design"""
        logger.info(f"\nComputing metrics for {design_id}...")

        db = CellThalamusDB(db_path=self.db_path)
        results = db.get_results(design_id)

        if not results:
            logger.warning(f"No results found for {design_id}")
            return {}

        metrics = {
            'design_id': design_id,
            'n_wells': len(results),
            'n_sentinels': sum(1 for r in results if r['is_sentinel']),
            'n_experimental': sum(1 for r in results if not r['is_sentinel']),
        }

        # Variance analysis
        try:
            analyzer = VarianceAnalyzer(db)
            variance_results = analyzer.analyze_design(design_id)

            if 'summary' in variance_results:
                metrics['biological_fraction'] = variance_results['summary']['biological_fraction_mean']
                metrics['technical_fraction'] = variance_results['summary']['technical_fraction_mean']
                metrics['criteria_pass'] = all(
                    c['pass'] for c in variance_results['summary']['criteria'].values()
                )
        except Exception as e:
            logger.warning(f"Variance analysis failed: {e}")
            metrics['variance_error'] = str(e)

        # Group by timepoint for chart analysis
        timepoint_results = {}
        for r in results:
            tp = r.get('timepoint_h', 0.0)
            if tp not in timepoint_results:
                timepoint_results[tp] = []
            timepoint_results[tp].append(r)

        # Sentinel specs for integration test
        sentinel_specs = [
            SentinelSpec(name="vehicle", cell_line="A549", compound="DMSO", dose_uM=0.0),
            SentinelSpec(name="ER", cell_line="A549", compound="thapsigargin", dose_uM=0.5),
            SentinelSpec(name="mito", cell_line="A549", compound="oligomycin", dose_uM=1.0),
            SentinelSpec(name="proteostasis", cell_line="A549", compound="MG132", dose_uM=1.0),
            SentinelSpec(name="oxidative", cell_line="A549", compound="tBHQ", dose_uM=30.0),
        ]

        # Analyze each timepoint separately
        chart_metrics = {}
        for tp, tp_results in sorted(timepoint_results.items()):
            try:
                analysis = analyze_boundaries(
                    results=tp_results,
                    design_id=f"{design_id}_T{int(tp):02d}h",
                    phase1_metrics={"trajectory_snr": {}, "global_nuisance_fraction": 0.5},
                    sentinel_specs=sentinel_specs,
                    boundary_type="death"
                )

                # Extract key metrics
                integration_test = analysis['integration_test']
                chart_metrics[f'T{int(tp)}h'] = {
                    'geometry_preservation_median': integration_test['geometry_preservation_median'],
                    'geometry_preservation_min': integration_test['geometry_preservation_min'],
                    'vehicle_drift_median': integration_test['vehicle_drift_median_normalized'],
                    'sentinel_max_drift': integration_test['sentinel_max_drift_normalized'],
                    'n_batches': len(analysis['batch_diagnostics'])
                }
            except Exception as e:
                logger.warning(f"Chart analysis failed for T{int(tp)}h: {e}")
                chart_metrics[f'T{int(tp)}h'] = {'error': str(e)}

        metrics['chart_metrics'] = chart_metrics

        db.close()
        return metrics

    def generate_comparison_report(self, all_metrics: List[Dict[str, Any]]) -> str:
        """Generate human-readable comparison report"""
        report = []
        report.append("\n" + "="*80)
        report.append("DESIGN COMPARISON REPORT")
        report.append("="*80 + "\n")

        # Overview table
        report.append("OVERVIEW")
        report.append("-" * 80)
        report.append(f"{'Design':<40} {'Wells':<10} {'Sentinels':<12} {'Experimental':<12}")
        report.append("-" * 80)

        for metrics in all_metrics:
            design = metrics['design_id']
            n_wells = metrics.get('n_wells', 0)
            n_sentinels = metrics.get('n_sentinels', 0)
            n_exp = metrics.get('n_experimental', 0)
            report.append(f"{design:<40} {n_wells:<10} {n_sentinels:<12} {n_exp:<12}")

        report.append("")

        # Variance metrics
        report.append("\nVARIANCE DECOMPOSITION")
        report.append("-" * 80)
        report.append(f"{'Design':<40} {'Biological %':<15} {'Technical %':<15} {'Pass':<10}")
        report.append("-" * 80)

        for metrics in all_metrics:
            design = metrics['design_id']
            bio_frac = metrics.get('biological_fraction', None)
            tech_frac = metrics.get('technical_fraction', None)
            criteria_pass = metrics.get('criteria_pass', False)

            bio_str = f"{bio_frac*100:.1f}%" if bio_frac is not None else "N/A"
            tech_str = f"{tech_frac*100:.1f}%" if tech_frac is not None else "N/A"
            pass_str = "✓" if criteria_pass else "✗"

            report.append(f"{design:<40} {bio_str:<15} {tech_str:<15} {pass_str:<10}")

        report.append("")

        # Chart health metrics
        report.append("\nCHART HEALTH METRICS")
        report.append("-" * 80)

        for metrics in all_metrics:
            design = metrics['design_id']
            report.append(f"\n{design}:")

            chart_metrics = metrics.get('chart_metrics', {})
            if not chart_metrics:
                report.append("  No chart metrics available")
                continue

            for timepoint, tm in sorted(chart_metrics.items()):
                if 'error' in tm:
                    report.append(f"  {timepoint}: Error - {tm['error']}")
                    continue

                geom = tm.get('geometry_preservation_median', 0)
                geom_min = tm.get('geometry_preservation_min', 0)
                vehicle_drift = tm.get('vehicle_drift_median', 0)
                sent_drift = tm.get('sentinel_max_drift', 0)

                status = "PASS" if geom >= 0.9 and sent_drift <= 0.8 else "FAIL"

                report.append(f"  {timepoint}: Geometry={geom:.3f} (min={geom_min:.3f}), "
                            f"Vehicle drift={vehicle_drift:.3f}, Sentinel max={sent_drift:.3f} [{status}]")

        report.append("\n" + "="*80)

        # Winner determination
        report.append("\nRECOMMENDATION")
        report.append("-" * 80)

        # Score each design
        scores = []
        for metrics in all_metrics:
            score = 0
            design = metrics['design_id']

            # Variance criteria
            if metrics.get('criteria_pass'):
                score += 3

            # Chart health
            chart_metrics = metrics.get('chart_metrics', {})
            for tp, tm in chart_metrics.items():
                if 'error' not in tm:
                    geom = tm.get('geometry_preservation_median', 0)
                    drift = tm.get('sentinel_max_drift', 1.0)
                    if geom >= 0.9 and drift <= 0.8:
                        score += 1

            # Throughput efficiency (wells per plate)
            n_wells = metrics.get('n_wells', 0)
            if n_wells > 0:
                # Estimate plates (rough)
                n_plates = n_wells / 88  # Approximate
                efficiency = n_wells / max(n_plates, 1)
                if efficiency > 90:
                    score += 2
                elif efficiency > 85:
                    score += 1

            scores.append((design, score, metrics))

        scores.sort(key=lambda x: x[1], reverse=True)

        report.append(f"\nRanking by overall score:")
        for rank, (design, score, metrics) in enumerate(scores, 1):
            report.append(f"  {rank}. {design} (score: {score})")

        winner = scores[0]
        report.append(f"\n✓ Winner: {winner[0]} with score {winner[1]}")

        report.append("="*80 + "\n")

        return "\n".join(report)

    def run_comparison(self):
        """Run full design comparison"""
        designs_to_compare = [
            ('phase0_design_v1_basic.json', 'full_phase0_screen_v1'),
            ('phase0_design_v2_controls_stratified.json', 'phase0_founder_v2_controls_stratified'),
            ('phase0_design_v3_mixed_celllines_checkerboard.json', 'phase0_founder_v3_mixed_celllines_checkerboard'),
        ]

        all_metrics = []

        for filename, expected_id in designs_to_compare:
            try:
                # Load design
                design_data = self.load_design_file(filename)

                # Run simulation
                design_id = self.run_design_from_file(design_data)

                # Compute metrics
                metrics = self.compute_metrics(design_id)
                all_metrics.append(metrics)

            except Exception as e:
                logger.error(f"Failed to run design {filename}: {e}")
                import traceback
                traceback.print_exc()
                all_metrics.append({
                    'design_id': expected_id,
                    'error': str(e)
                })

        # Generate report
        report = self.generate_comparison_report(all_metrics)
        print(report)

        # Save report to file
        report_path = Path(__file__).parent.parent / "data" / f"design_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_path, 'w') as f:
            f.write(report)

        logger.info(f"\n✓ Comparison complete! Report saved to: {report_path}")
        logger.info(f"✓ Results database: {self.db_path}")


if __name__ == "__main__":
    comparator = DesignComparator()
    comparator.run_comparison()
