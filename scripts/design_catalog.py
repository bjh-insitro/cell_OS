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


if __name__ == '__main__':
    main()
