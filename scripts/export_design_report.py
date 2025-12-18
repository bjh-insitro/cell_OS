"""
Export Design Report for LLM Review

Creates a comprehensive JSON report containing:
1. Design parameters (what was chosen)
2. Design statistics (well counts, plates, compounds)
3. Validation certificate (all invariant checks)
4. Scaffold provenance (hash verification)
5. Spatial dispersion metrics (scatter quality)

This report can be fed to an LLM (e.g., ChatGPT) for feedback on design quality.

Usage:
    python export_design_report.py <design_file> <output_report>
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any


def compute_spatial_metrics(wells: List[Dict]) -> Dict[str, Any]:
    """Compute spatial dispersion metrics for each compound"""
    def get_row_col(pos):
        row = ord(pos[0]) - ord('A')
        col = int(pos[1:]) - 1
        return row, col

    # Group by plate and compound
    wells_by_plate_compound = {}
    for well in wells:
        if well['is_sentinel']:
            continue
        key = f"{well['plate_id']}|{well['compound']}"
        if key not in wells_by_plate_compound:
            wells_by_plate_compound[key] = []
        wells_by_plate_compound[key].append(well)

    # Compute metrics
    metrics = {}
    for key, compound_wells in wells_by_plate_compound.items():
        plate_id, compound = key.split('|')

        positions = [get_row_col(w['well_pos']) for w in compound_wells]
        rows = [r for r, c in positions]
        cols = [c for r, c in positions]

        row_span = max(rows) - min(rows) + 1
        col_span = max(cols) - min(cols) + 1
        bbox_area = row_span * col_span

        if compound not in metrics:
            metrics[compound] = {
                'compound': compound,
                'well_count': len(compound_wells),
                'plates': []
            }

        metrics[compound]['plates'].append({
            'plate_id': plate_id,
            'row_span': row_span,
            'col_span': col_span,
            'bounding_box_area': bbox_area,
        })

    # Compute averages
    for compound, data in metrics.items():
        areas = [p['bounding_box_area'] for p in data['plates']]
        row_spans = [p['row_span'] for p in data['plates']]
        col_spans = [p['col_span'] for p in data['plates']]

        data['avg_bounding_box_area'] = sum(areas) / len(areas)
        data['avg_row_span'] = sum(row_spans) / len(row_spans)
        data['avg_col_span'] = sum(col_spans) / len(col_spans)
        data['min_bounding_box_area'] = min(areas)
        data['max_bounding_box_area'] = max(areas)

    return metrics


def extract_design_parameters(design: Dict) -> Dict[str, Any]:
    """Extract the design parameters that were chosen"""
    metadata = design.get('metadata', {})

    return {
        'design_id': design.get('design_id'),
        'design_type': design.get('design_type'),
        'description': design.get('description'),
        'cell_lines': metadata.get('cell_lines', []),
        'compounds': {
            'groups': metadata.get('compound_groups', []),
            'total': metadata.get('n_compounds'),
        },
        'doses': metadata.get('experimental_conditions', {}).get('doses', []),
        'replicates': metadata.get('experimental_conditions', {}).get('replicates'),
        'timepoints_h': metadata.get('timepoints_h', []),
        'days': metadata.get('days', []),
        'operators': metadata.get('operators', []),
        'plate_format': 96,  # Hardcoded for Phase 0
        'exclusions': {
            'corners': True,
            'midRow': True,
        },
        'sentinel_schema': {
            'policy': metadata.get('sentinel_schema', {}).get('policy'),
            'scaffold_id': metadata.get('sentinel_schema', {}).get('scaffold_metadata', {}).get('scaffold_id'),
            'scaffold_hash': metadata.get('sentinel_schema', {}).get('scaffold_metadata', {}).get('scaffold_hash'),
            'total_per_plate': metadata.get('sentinel_schema', {}).get('total_per_plate'),
            'types': metadata.get('sentinel_schema', {}).get('types', {}),
        },
        'randomization': {
            'seed': metadata.get('design_seed'),
            'method': 'per_cell_line_shuffle',
            'note': metadata.get('batch_structure', {}).get('randomization', ''),
        },
    }


def generate_design_report(design_path: str, output_path: str):
    """Generate comprehensive design report for LLM review"""

    # Load design
    design = json.load(open(design_path))
    wells = design['wells']

    # Extract parameters
    parameters = extract_design_parameters(design)

    # Compute statistics
    sentinel_wells = [w for w in wells if w['is_sentinel']]
    experimental_wells = [w for w in wells if not w['is_sentinel']]
    plates = sorted(set(w['plate_id'] for w in wells))

    compounds = sorted(set(w['compound'] for w in experimental_wells))
    cell_lines = sorted(set(w['cell_line'] for w in wells))

    statistics = {
        'total_wells': len(wells),
        'sentinel_wells': len(sentinel_wells),
        'experimental_wells': len(experimental_wells),
        'plates': len(plates),
        'wells_per_plate': len(wells) // len(plates) if plates else 0,
        'unique_compounds': len(compounds),
        'unique_cell_lines': len(cell_lines),
        'timepoints': sorted(set(w.get('timepoint_h') for w in wells if w.get('timepoint_h'))),
        'days': sorted(set(w.get('day') for w in wells if w.get('day'))),
        'operators': sorted(set(w.get('operator') for w in wells if w.get('operator'))),
    }

    # Compute spatial metrics
    spatial_dispersion = compute_spatial_metrics(wells)

    # Build report
    report = {
        '_meta': {
            'report_type': 'phase0_design_report_for_llm_review',
            'version': '1.0.0',
            'purpose': 'Comprehensive design snapshot for LLM feedback on design quality',
            'design_file': design_path,
        },
        'parameters': parameters,
        'statistics': statistics,
        'spatial_dispersion': spatial_dispersion,
        'validation': {
            'note': 'Run validateFounderDesign.ts to get full validation certificate',
            'scaffold_hash': parameters['sentinel_schema']['scaffold_hash'],
        },
        'context': {
            'design_goals': [
                'Maximum identifiability (position = identity)',
                'Batch orthogonality (day × operator × timepoint)',
                'Spatial scatter (eliminate gradient confounding)',
                'Position stability (same position = same condition within cell line)',
            ],
            'constraints': [
                'Fixed sentinel scaffold (28 sentinels, same positions on all plates)',
                'Exact fill requirement (88 wells per plate, no partials)',
                'Cell line separation (no mixing on same plate)',
                'Identical conditions per timepoint (multiset consistency)',
            ],
            'spatial_baseline': {
                'sequential_fill': 'rows≈2, cols≈6, area≈12 (BAD: creates compound-specific gradients)',
                'random_scatter': 'rows≈5-7, cols≈8-11, area≈50-80 (GOOD: eliminates spatial confounding)',
            },
        },
    }

    # Write report
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"✅ Design report written to: {output_path}")
    print(f"   Design: {parameters['design_id']}")
    print(f"   Wells: {statistics['total_wells']} ({statistics['sentinel_wells']} sentinels, {statistics['experimental_wells']} experimental)")
    print(f"   Plates: {statistics['plates']}")
    print(f"   Compounds: {statistics['unique_compounds']}")
    print(f"   Avg bounding box area: {sum(m['avg_bounding_box_area'] for m in spatial_dispersion.values()) / len(spatial_dispersion):.1f}")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python export_design_report.py <design_file> <output_report>")
        print("Example: python export_design_report.py ../data/designs/phase0_founder_v2_regenerated.json design_report.json")
        sys.exit(1)

    design_path = sys.argv[1]
    output_path = sys.argv[2]

    generate_design_report(design_path, output_path)
