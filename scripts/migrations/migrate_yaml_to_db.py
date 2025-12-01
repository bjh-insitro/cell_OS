#!/usr/bin/env python3
"""
Migrate cell_lines.yaml to SQLite database.

This script reads the YAML file and populates the SQLite database with all cell line data.
"""

import yaml
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.cell_line_db import CellLineDatabase, CellLine, CellLineCharacteristic


def migrate():
    """Migrate YAML data to SQLite database."""
    
    # Load YAML
    yaml_path = Path("data/cell_lines.yaml")
    if not yaml_path.exists():
        print(f"❌ YAML file not found: {yaml_path}")
        return
    
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    
    cell_lines_data = data.get('cell_lines', {})
    
    # Initialize database
    db = CellLineDatabase("data/cell_lines.db")
    
    print(f"📦 Migrating {len(cell_lines_data)} cell lines...")
    
    for cell_line_id, config in cell_lines_data.items():
        print(f"\n  → {cell_line_id}")
        
        # Create CellLine object
        cell_line = CellLine(
            cell_line_id=cell_line_id,
            display_name=config.get('display_name', cell_line_id),
            cell_type=config.get('profile', {}).get('cell_type', 'unknown'),
            growth_media=config.get('growth_media', 'dmem_10fbs'),
            wash_buffer=config.get('wash_buffer'),
            detach_reagent=config.get('detach_reagent'),
            coating_required=config.get('profile', {}).get('coating_required', False),
            coating_reagent=config.get('profile', {}).get('coating_reagent'),
            cost_tier=config.get('profile', {}).get('cost_tier', 'standard')
        )
        
        # Add to database
        db.add_cell_line(cell_line)
        print(f"    ✓ Added cell line")
        
        # Add characteristics from profile
        profile = config.get('profile', {})
        characteristics = {
            'dissociation_method': profile.get('dissociation_method'),
            'dissociation_notes': profile.get('dissociation_notes'),
            'transfection_method': profile.get('transfection_method'),
            'transfection_efficiency': profile.get('transfection_efficiency'),
            'transfection_notes': profile.get('transfection_notes'),
            'transduction_method': profile.get('transduction_method'),
            'transduction_notes': profile.get('transduction_notes'),
            'freezing_media': profile.get('freezing_media'),
            'freezing_notes': profile.get('freezing_notes'),
            'vial_type': profile.get('vial_type'),
            'freezing_volume_ml': profile.get('freezing_volume_ml'),
            'cells_per_vial': profile.get('cells_per_vial'),
            'media': profile.get('media'),
        }
        
        for char_name, char_value in characteristics.items():
            if char_value is not None:
                char = CellLineCharacteristic(
                    cell_line_id=cell_line_id,
                    characteristic=char_name,
                    value=str(char_value),
                    notes=None
                )
                db.add_characteristic(char)
        
        print(f"    ✓ Added {len([v for v in characteristics.values() if v is not None])} characteristics")
    
    print(f"\n✅ Migration complete!")
    print(f"   Database: data/cell_lines.db")
    print(f"   Cell lines: {len(cell_lines_data)}")
    
    # Verify
    all_lines = db.get_all_cell_lines()
    print(f"\n📊 Verification:")
    print(f"   Cell lines in DB: {len(all_lines)}")
    for line_id in all_lines:
        line = db.get_cell_line(line_id)
        chars = db.get_characteristics(line_id)
        print(f"   - {line_id}: {line.display_name} ({len(chars)} characteristics)")


if __name__ == "__main__":
    migrate()
