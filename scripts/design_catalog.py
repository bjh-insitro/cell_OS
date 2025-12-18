#!/usr/bin/env python3
"""
Design Catalog Manager for Cell Thalamus

Manages experimental design versions, tracks evolution, and validates designs.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class DesignCatalog:
    """Manager for experimental design catalog."""

    def __init__(self, catalog_path: str = None):
        if catalog_path is None:
            # Default to project data/designs directory
            self.catalog_path = Path(__file__).parent.parent / "data" / "designs" / "catalog.json"
        else:
            self.catalog_path = Path(catalog_path)

        self.designs_dir = self.catalog_path.parent
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> Dict:
        """Load catalog from JSON file."""
        with open(self.catalog_path, 'r') as f:
            return json.load(f)

    def _save_catalog(self):
        """Save catalog to JSON file."""
        with open(self.catalog_path, 'w') as f:
            json.dump(self.catalog, f, indent=2)

    def list_designs(self, status: Optional[str] = None) -> List[Dict]:
        """List all designs, optionally filtered by status."""
        designs = self.catalog['designs']

        if status:
            designs = [d for d in designs if d['status'] == status]

        return designs

    def get_design(self, design_id: str) -> Optional[Dict]:
        """Get design metadata by ID."""
        for design in self.catalog['designs']:
            if design['design_id'] == design_id:
                return design
        return None

    def get_current_design(self) -> Optional[Dict]:
        """Get the current active design."""
        current = [d for d in self.catalog['designs'] if d['status'] == 'current']
        return current[0] if current else None

    def load_design_file(self, design_id: str) -> Optional[Dict]:
        """Load full design JSON file."""
        design = self.get_design(design_id)
        if not design:
            return None

        design_file = self.designs_dir / design['filename']
        with open(design_file, 'r') as f:
            return json.load(f)

    def add_design(
        self,
        design_id: str,
        filename: str,
        version: str,
        description: str,
        design_type: str = "phase0_founder_screen",
        status: str = "draft",
        metadata: Dict = None,
        features: List[str] = None,
        improvements: List[str] = None,
        supersedes: str = None
    ):
        """Add a new design to the catalog."""

        # Check if design already exists
        if self.get_design(design_id):
            print(f"Warning: Design {design_id} already exists in catalog")
            return False

        # If this supersedes another design, update that design's status
        if supersedes:
            old_design = self.get_design(supersedes)
            if old_design:
                old_design['superseded_by'] = design_id
                if old_design['status'] == 'current':
                    old_design['status'] = 'archived'

        # If this is marked as current, archive any other current designs
        if status == 'current':
            for design in self.catalog['designs']:
                if design['status'] == 'current':
                    design['status'] = 'archived'

        # Create new design entry
        new_design = {
            'design_id': design_id,
            'version': version,
            'filename': filename,
            'created_at': datetime.now().strftime('%Y-%m-%d'),
            'status': status,
            'design_type': design_type,
            'description': description,
            'metadata': metadata or {},
            'features': features or [],
        }

        if improvements:
            new_design['improvements_over_previous'] = improvements

        if supersedes:
            new_design['supersedes'] = supersedes

        self.catalog['designs'].append(new_design)
        self._save_catalog()

        print(f"✓ Added design {design_id} to catalog")
        return True

    def compare_designs(self, design_id_1: str, design_id_2: str):
        """Compare two designs."""
        d1 = self.get_design(design_id_1)
        d2 = self.get_design(design_id_2)

        if not d1 or not d2:
            print(f"Error: Could not find one or both designs")
            return

        print(f"\nCOMPARISON: {design_id_1} vs {design_id_2}")
        print("=" * 80)

        # Compare key metrics
        metrics = ['n_plates', 'n_wells', 'wells_per_plate', 'n_timepoints', 'n_compounds']

        print("\nMetadata Comparison:")
        for metric in metrics:
            v1 = d1['metadata'].get(metric, 'N/A')
            v2 = d2['metadata'].get(metric, 'N/A')

            if v1 != v2:
                change_icon = "→"
            else:
                change_icon = "="

            print(f"  {metric:20s}: {v1:10} {change_icon} {v2}")

        print("\nFeatures:")
        print(f"\n  {design_id_1}:")
        for f in d1.get('features', []):
            print(f"    • {f}")

        print(f"\n  {design_id_2}:")
        for f in d2.get('features', []):
            print(f"    • {f}")

        if d2.get('improvements_over_previous'):
            print(f"\n  Improvements in {design_id_2}:")
            for imp in d2['improvements_over_previous']:
                print(f"    ✓ {imp}")

    def validate_design_file(self, design_id: str) -> bool:
        """Validate that design file exists and has required structure."""
        design = self.get_design(design_id)
        if not design:
            print(f"Error: Design {design_id} not found in catalog")
            return False

        design_data = self.load_design_file(design_id)
        if not design_data:
            print(f"Error: Could not load design file for {design_id}")
            return False

        print(f"\nValidating {design_id}...")
        print("=" * 80)

        # Check required fields exist
        errors = []
        warnings = []

        # Check design_id matches
        if design_data.get('design_id') != design_id:
            errors.append(f"Design ID mismatch: catalog={design_id}, file={design_data.get('design_id')}")

        # Check required top-level fields
        required_fields = ['design_id', 'metadata', 'wells']
        for field in required_fields:
            if field not in design_data:
                errors.append(f"Missing required field: {field}")

        # Validate catalog metadata is consistent with file (if comparable)
        catalog_meta = design['metadata']
        file_meta = design_data.get('metadata', {})

        # Only check fields that exist in both
        if 'n_plates' in catalog_meta and 'n_plates' in file_meta:
            if catalog_meta['n_plates'] != file_meta['n_plates']:
                warnings.append(f"n_plates mismatch: catalog={catalog_meta['n_plates']}, file={file_meta['n_plates']}")

        # Check timepoints are consistent
        if 'timepoints_h' in catalog_meta and 'timepoints_h' in file_meta:
            if set(catalog_meta['timepoints_h']) != set(file_meta['timepoints_h']):
                warnings.append(f"Timepoints mismatch: catalog={catalog_meta['timepoints_h']}, file={file_meta['timepoints_h']}")

        if errors:
            print("✗ Validation FAILED:")
            for err in errors:
                print(f"  • {err}")
            return False
        else:
            print("✓ Validation PASSED")
            if warnings:
                print("\nWarnings:")
                for warn in warnings:
                    print(f"  ⚠ {warn}")
            return True


def main():
    """CLI interface for design catalog."""
    if len(sys.argv) < 2:
        print("Usage: design_catalog.py <command> [args]")
        print("\nCommands:")
        print("  list [status]         - List all designs (optionally filter by status)")
        print("  show <design_id>      - Show design details")
        print("  current               - Show current active design")
        print("  compare <id1> <id2>   - Compare two designs")
        print("  validate <design_id>  - Validate design file against catalog")
        print("  evolution             - Show design evolution history")
        return

    catalog = DesignCatalog()
    command = sys.argv[1]

    if command == 'list':
        status = sys.argv[2] if len(sys.argv) > 2 else None
        designs = catalog.list_designs(status)

        print(f"\nDesigns{f' (status={status})' if status else ''}:")
        print("-" * 80)
        for d in designs:
            status_icon = '✓' if d['status'] == 'current' else '○'
            print(f"{status_icon} {d['design_id']:40s} v{d['version']:3s} [{d['status']}]")
            print(f"  {d['description']}")
            print()

    elif command == 'show':
        if len(sys.argv) < 3:
            print("Error: design_id required")
            return

        design_id = sys.argv[2]
        design = catalog.get_design(design_id)

        if not design:
            print(f"Error: Design {design_id} not found")
            return

        print(f"\nDesign: {design['design_id']}")
        print("=" * 80)
        print(f"Version: {design['version']}")
        print(f"Status: {design['status']}")
        print(f"File: {design['filename']}")
        print(f"Created: {design['created_at']}")
        print(f"\nDescription: {design['description']}")
        print(f"\nMetadata:")
        for key, value in design['metadata'].items():
            print(f"  {key}: {value}")
        print(f"\nFeatures:")
        for feature in design['features']:
            print(f"  • {feature}")

    elif command == 'current':
        design = catalog.get_current_design()

        if not design:
            print("No current design set")
            return

        print(f"\nCurrent Design: {design['design_id']}")
        print(f"Version: {design['version']}")
        print(f"Description: {design['description']}")

    elif command == 'compare':
        if len(sys.argv) < 4:
            print("Error: two design_ids required")
            return

        catalog.compare_designs(sys.argv[2], sys.argv[3])

    elif command == 'validate':
        if len(sys.argv) < 3:
            print("Error: design_id required")
            return

        catalog.validate_design_file(sys.argv[2])

    elif command == 'evolution':
        print("\nDesign Evolution:")
        print("=" * 80)
        for i, evolution in enumerate(catalog.catalog['design_evolution_log'], 1):
            from_v = evolution['from_version'] or 'initial'
            to_v = evolution['to_version']
            print(f"\n{i}. {from_v} → {to_v} ({evolution['date']})")
            print(f"   Reason: {evolution['reason']}")

            if evolution.get('evidence'):
                print(f"\n   Evidence:")
                for key, value in evolution['evidence'].items():
                    print(f"     • {key}: {value}")

            print(f"\n   Changes:")
            for change in evolution.get('key_changes', []):
                print(f"     - {change}")

    else:
        print(f"Unknown command: {command}")


class DesignGenerator:
    """
    Interactive design generator for Cell Thalamus experiments.

    Creates experimental designs with full control over:
    - Cell lines and compounds
    - Dose levels and IC50 positioning
    - Replicates and batch structure
    - Sentinel wells and QC controls
    - Plate layout (checkerboard, corner exclusion)
    - Plate format (96-well, 384-well)
    """

    def __init__(self):
        # Compound parameters (IC50 values for dose calculation)
        self.compound_ic50 = {
            'tBHQ': 30.0, 'H2O2': 100.0, 'tbhp': 80.0,
            'tunicamycin': 1.0, 'thapsigargin': 0.5,
            'CCCP': 5.0, 'oligomycin': 1.0, 'two_deoxy_d_glucose': 1000.0,
            'etoposide': 10.0, 'cisplatin': 5.0, 'doxorubicin': 0.5, 'staurosporine': 0.1,
            'MG132': 1.0,
            'nocodazole': 0.5, 'paclitaxel': 0.01,
        }

    def create_design(
        self,
        design_id: str,
        description: str,
        # Cell lines and compounds
        cell_lines: List[str] = None,
        compounds: List[str] = None,
        # Dose configuration
        n_doses: int = 4,
        dose_multipliers: List[float] = None,  # Relative to IC50 (e.g., [0, 0.1, 1, 10])
        # Replicates and batch structure
        replicates_per_dose: int = 3,
        days: List[int] = None,
        operators: List[str] = None,
        timepoints_h: List[float] = None,
        # Sentinels
        sentinel_config: Dict = None,
        # Plate layout
        plate_format: int = 96,
        checkerboard: bool = False,
        exclude_corners: bool = False,
        exclude_edges: bool = False,
        # Output
        output_path: str = None
    ) -> Dict:
        """
        Generate a custom experimental design.

        Args:
            design_id: Unique design identifier
            description: Human-readable description
            cell_lines: List of cell lines (default: ['A549', 'HepG2'])
            compounds: List of compounds to test (default: all 10 from Phase 0)
            n_doses: Number of dose levels per compound (default: 4)
            dose_multipliers: Dose positions relative to IC50 (default: [0, 0.1, 1, 10])
            replicates_per_dose: Technical replicates per dose (default: 3)
            days: Experimental days (default: [1, 2])
            operators: Operators (default: ['Operator_A', 'Operator_B'])
            timepoints_h: Timepoints in hours (default: [12.0, 48.0])
            sentinel_config: Custom sentinel configuration (default: standard QC sentinels)
            plate_format: 96 or 384 wells (default: 96)
            checkerboard: Interleave cell lines in checkerboard pattern (default: False)
            exclude_corners: Exclude corner wells (A1, A12, H1, H12) (default: False)
            exclude_edges: Exclude all edge wells (default: False)
            output_path: Where to save design JSON (default: data/designs/<design_id>.json)

        Returns:
            Design dictionary ready for standalone_cell_thalamus.py
        """

        # Defaults
        if cell_lines is None:
            cell_lines = ['A549', 'HepG2']
        if compounds is None:
            compounds = ['tBHQ', 'H2O2', 'tunicamycin', 'thapsigargin', 'CCCP',
                        'oligomycin', 'etoposide', 'MG132', 'nocodazole', 'paclitaxel']
        if dose_multipliers is None:
            dose_multipliers = [0, 0.1, 1.0, 10.0]  # Vehicle, low, mid, high
        if days is None:
            days = [1, 2]
        if operators is None:
            operators = ['Operator_A', 'Operator_B']
        if timepoints_h is None:
            timepoints_h = [12.0, 48.0]
        if sentinel_config is None:
            # Standard QC sentinels (per cell line)
            sentinel_config = {
                'DMSO': {'dose_uM': 0.0, 'n_per_cell': 4},
                'tBHQ': {'dose_uM': 10.0, 'n_per_cell': 2},
                'tunicamycin': {'dose_uM': 2.0, 'n_per_cell': 2},
            }
        if output_path is None:
            output_path = f"data/designs/{design_id}.json"

        # Validate plate format
        if plate_format not in [96, 384]:
            raise ValueError(f"plate_format must be 96 or 384, got {plate_format}")

        # Calculate plate geometry
        if plate_format == 96:
            n_rows, n_cols = 8, 12
            row_labels = [chr(65 + i) for i in range(n_rows)]  # A-H
        else:  # 384
            n_rows, n_cols = 16, 24
            row_labels = [chr(65 + i) for i in range(n_rows)]  # A-P

        # Generate excluded wells
        excluded_wells = set()
        if exclude_corners:
            excluded_wells.update([
                f"{row_labels[0]}{1:02d}",  # Top-left
                f"{row_labels[0]}{n_cols:02d}",  # Top-right
                f"{row_labels[-1]}{1:02d}",  # Bottom-left
                f"{row_labels[-1]}{n_cols:02d}",  # Bottom-right
            ])
        if exclude_edges:
            # All wells in first/last row or first/last column
            for row in [row_labels[0], row_labels[-1]]:
                for col in range(1, n_cols + 1):
                    excluded_wells.add(f"{row}{col:02d}")
            for col in [1, n_cols]:
                for row in row_labels:
                    excluded_wells.add(f"{row}{col:02d}")

        # Generate all well positions
        all_wells = [f"{row}{col:02d}" for row in row_labels for col in range(1, n_cols + 1)]
        available_wells = [w for w in all_wells if w not in excluded_wells]

        print(f"\nDesign Configuration:")
        print(f"  Plate format: {plate_format}-well")
        print(f"  Available wells: {len(available_wells)}/{len(all_wells)}")
        print(f"  Cell lines: {len(cell_lines)}")
        print(f"  Compounds: {len(compounds)}")
        print(f"  Doses per compound: {len(dose_multipliers)}")
        print(f"  Replicates per dose: {replicates_per_dose}")
        print(f"  Sentinels per cell line: {sum(s['n_per_cell'] for s in sentinel_config.values())}")
        print(f"  Timepoints: {timepoints_h}")
        print(f"  Days × Operators: {len(days)} × {len(operators)}")

        # Calculate wells needed per plate
        experimental_wells_per_cell = len(compounds) * len(dose_multipliers) * replicates_per_dose
        sentinel_wells_per_cell = sum(s['n_per_cell'] for s in sentinel_config.values())
        wells_per_cell_line = experimental_wells_per_cell + sentinel_wells_per_cell

        if checkerboard:
            # Checkerboard: both cell lines on same plate
            total_wells_needed = wells_per_cell_line * len(cell_lines)
            print(f"\nCheckerboard layout: {total_wells_needed} wells needed per plate")
            if total_wells_needed > len(available_wells):
                raise ValueError(
                    f"Not enough wells! Need {total_wells_needed}, have {len(available_wells)}. "
                    f"Try reducing compounds/doses/replicates or using 384-well format."
                )
        else:
            # Separate plates per cell line
            print(f"\nSeparate plates: {wells_per_cell_line} wells per cell line")
            if wells_per_cell_line > len(available_wells):
                raise ValueError(
                    f"Not enough wells! Need {wells_per_cell_line}, have {len(available_wells)}. "
                    f"Try reducing compounds/doses/replicates or using 384-well format."
                )

        # Generate wells
        wells = []
        well_counter = 0

        for day in days:
            for operator in operators:
                for timepoint in timepoints_h:
                    if checkerboard:
                        # Single plate with interleaved cell lines
                        plate_id = f"Plate_Day{day}_{operator}_T{timepoint}h"
                        well_iter = iter(available_wells)

                        # Experimental wells - interleave by cell line
                        for compound in compounds:
                            ic50 = self.compound_ic50.get(compound, 1.0)
                            for dose_mult in dose_multipliers:
                                dose_uM = dose_mult * ic50
                                for rep in range(replicates_per_dose):
                                    for cell_line in cell_lines:
                                        well_pos = next(well_iter)
                                        wells.append({
                                            'plate_id': plate_id,
                                            'cell_line': cell_line,
                                            'compound': compound,
                                            'dose_uM': dose_uM,
                                            'timepoint_h': timepoint,
                                            'operator': operator,
                                            'day': day,
                                            'is_sentinel': False,
                                            'sentinel_type': None,
                                            'well_pos': well_pos,
                                            'row': well_pos[0],
                                            'col': int(well_pos[1:]),
                                            'well_id': f"{plate_id}_W{well_counter:03d}"
                                        })
                                        well_counter += 1

                        # Sentinel wells - interleave by cell line
                        for sentinel_compound, config in sentinel_config.items():
                            for _ in range(config['n_per_cell']):
                                for cell_line in cell_lines:
                                    well_pos = next(well_iter)
                                    wells.append({
                                        'plate_id': plate_id,
                                        'cell_line': cell_line,
                                        'compound': sentinel_compound,
                                        'dose_uM': config['dose_uM'],
                                        'timepoint_h': timepoint,
                                        'operator': operator,
                                        'day': day,
                                        'is_sentinel': True,
                                        'sentinel_type': sentinel_compound.lower(),
                                        'well_pos': well_pos,
                                        'row': well_pos[0],
                                        'col': int(well_pos[1:]),
                                        'well_id': f"{plate_id}_W{well_counter:03d}"
                                    })
                                    well_counter += 1
                    else:
                        # Separate plate per cell line
                        for cell_line in cell_lines:
                            plate_id = f"Plate_{cell_line}_Day{day}_{operator}_T{timepoint}h"
                            well_iter = iter(available_wells)

                            # Experimental wells
                            for compound in compounds:
                                ic50 = self.compound_ic50.get(compound, 1.0)
                                for dose_mult in dose_multipliers:
                                    dose_uM = dose_mult * ic50
                                    for rep in range(replicates_per_dose):
                                        well_pos = next(well_iter)
                                        wells.append({
                                            'plate_id': plate_id,
                                            'cell_line': cell_line,
                                            'compound': compound,
                                            'dose_uM': dose_uM,
                                            'timepoint_h': timepoint,
                                            'operator': operator,
                                            'day': day,
                                            'is_sentinel': False,
                                            'sentinel_type': None,
                                            'well_pos': well_pos,
                                            'row': well_pos[0],
                                            'col': int(well_pos[1:]),
                                            'well_id': f"{plate_id}_W{well_counter:03d}"
                                        })
                                        well_counter += 1

                            # Sentinel wells
                            for sentinel_compound, config in sentinel_config.items():
                                for _ in range(config['n_per_cell']):
                                    well_pos = next(well_iter)
                                    wells.append({
                                        'plate_id': plate_id,
                                        'cell_line': cell_line,
                                        'compound': sentinel_compound,
                                        'dose_uM': config['dose_uM'],
                                        'timepoint_h': timepoint,
                                        'operator': operator,
                                        'day': day,
                                        'is_sentinel': True,
                                        'sentinel_type': sentinel_compound.lower(),
                                        'well_pos': well_pos,
                                        'row': well_pos[0],
                                        'col': int(well_pos[1:]),
                                        'well_id': f"{plate_id}_W{well_counter:03d}"
                                    })
                                    well_counter += 1

        # Create design object
        design = {
            'design_id': design_id,
            'design_type': 'custom_generated',
            'description': description,
            'metadata': {
                'generated_at_utc': datetime.utcnow().isoformat() + 'Z',
                'generator': 'DesignGenerator',
                'cell_lines': cell_lines,
                'compounds': compounds,
                'n_doses': len(dose_multipliers),
                'dose_multipliers': dose_multipliers,
                'replicates_per_dose': replicates_per_dose,
                'days': days,
                'operators': operators,
                'timepoints_h': timepoints_h,
                'plate_format': plate_format,
                'checkerboard': checkerboard,
                'exclude_corners': exclude_corners,
                'exclude_edges': exclude_edges,
                'n_plates': len(wells) // len(available_wells) if checkerboard else len(cell_lines) * len(days) * len(operators) * len(timepoints_h),
                'wells_per_plate': len(available_wells),
                'total_wells': len(wells),
            },
            'wells': wells
        }

        # Save to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(design, f, indent=2)

        print(f"\n✓ Design saved to: {output_file}")
        print(f"  Total wells: {len(wells)}")
        print(f"  Unique plates: {len(set(w['plate_id'] for w in wells))}")

        return design


if __name__ == '__main__':
    main()
