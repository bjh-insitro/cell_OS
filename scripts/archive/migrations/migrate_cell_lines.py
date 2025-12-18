"""
Migrate cell lines from YAML to SQLite database.

This script:
1. Loads data from data/cell_lines.yaml (614 lines!)
2. Creates cell_lines.db
3. Migrates all cell line metadata
4. Migrates all protocol parameters
5. Migrates all characteristics
6. Validates the migration
"""

import yaml
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.cell_line_db import (
    CellLineDatabase,
    CellLine,
    CellLineCharacteristic,
    ProtocolParameters
)


def load_yaml_data(yaml_path: str = "data/cell_lines.yaml"):
    """Load cell lines from YAML file."""
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def migrate_cell_line_metadata(db: CellLineDatabase, yaml_data: dict):
    """Migrate core cell line metadata."""
    print("\n📊 Migrating cell line metadata...")
    
    cell_lines = yaml_data.get("cell_lines", {})
    count = 0
    
    for cell_line_id, config in cell_lines.items():
        profile = config.get("profile", {})
        
        # Create cell line object
        cell_line = CellLine(
            cell_line_id=cell_line_id,
            display_name=config.get("display_name", cell_line_id),
            cell_type=profile.get("cell_type", "unknown"),
            growth_media=config.get("growth_media", "dmem_high_glucose"),
            wash_buffer=config.get("wash_buffer"),
            detach_reagent=config.get("detach_reagent"),
            coating_required=profile.get("coating_required", False),
            coating_reagent=profile.get("coating_reagent"),
            cost_tier=profile.get("cost_tier", "standard")
        )
        
        # Add to database
        db.add_cell_line(cell_line)
        count += 1
        print(f"  ✅ {cell_line_id}: {cell_line.display_name}")
    
    print(f"\n✅ Migrated {count} cell lines")
    return count


def migrate_characteristics(db: CellLineDatabase, yaml_data: dict):
    """Migrate cell line characteristics (profile data)."""
    print("\n🔬 Migrating cell line characteristics...")
    
    cell_lines = yaml_data.get("cell_lines", {})
    count = 0
    
    for cell_line_id, config in cell_lines.items():
        profile = config.get("profile", {})
        
        # Skip fields already in main table
        skip_fields = {"cell_type", "coating_required", "coating_reagent", "cost_tier"}
        
        for key, value in profile.items():
            if key not in skip_fields:
                char = CellLineCharacteristic(
                    cell_line_id=cell_line_id,
                    characteristic=key,
                    value=str(value),
                    notes=None
                )
                db.add_characteristic(char)
                count += 1
    
    print(f"\n✅ Migrated {count} characteristics")
    return count


def migrate_protocols(db: CellLineDatabase, yaml_data: dict):
    """Migrate protocol parameters (passage, thaw, feed)."""
    print("\n⚗️  Migrating protocol parameters...")
    
    cell_lines = yaml_data.get("cell_lines", {})
    count = 0
    
    for cell_line_id, config in cell_lines.items():
        # Migrate each protocol type
        for protocol_type in ["passage", "thaw", "feed"]:
            if protocol_type not in config:
                continue
            
            protocol_config = config[protocol_type]
            
            # Skip reference_vessel field
            for vessel_type, params in protocol_config.items():
                if vessel_type == "reference_vessel":
                    continue
                
                protocol = ProtocolParameters(
                    cell_line_id=cell_line_id,
                    protocol_type=protocol_type,
                    vessel_type=vessel_type,
                    parameters=params
                )
                
                db.add_protocol(protocol)
                count += 1
                print(f"  ✅ {cell_line_id} / {protocol_type} / {vessel_type}")
    
    print(f"\n✅ Migrated {count} protocol parameter sets")
    return count


def validate_migration(db: CellLineDatabase, yaml_data: dict):
    """Validate that migration was successful."""
    print("\n🔍 Validating migration...")
    
    errors = []
    
    # Validate cell line count
    yaml_cell_lines = set(yaml_data.get("cell_lines", {}).keys())
    db_cell_lines = set(db.get_all_cell_lines())
    
    if yaml_cell_lines != db_cell_lines:
        errors.append(f"Cell line mismatch: YAML has {len(yaml_cell_lines)}, DB has {len(db_cell_lines)}")
        missing = yaml_cell_lines - db_cell_lines
        if missing:
            errors.append(f"  Missing in DB: {missing}")
    else:
        print(f"  ✅ Cell lines: {len(db_cell_lines)} matched")
    
    # Validate specific cell lines
    for cell_line_id in yaml_cell_lines:
        yaml_config = yaml_data["cell_lines"][cell_line_id]
        db_cell_line = db.get_cell_line(cell_line_id)
        
        if db_cell_line is None:
            errors.append(f"Missing cell line: {cell_line_id}")
            continue
        
        # Check display name
        yaml_display = yaml_config.get("display_name", cell_line_id)
        if db_cell_line.display_name != yaml_display:
            errors.append(
                f"{cell_line_id}: display_name mismatch "
                f"(YAML: {yaml_display}, DB: {db_cell_line.display_name})"
            )
        
        # Check growth media
        yaml_media = yaml_config.get("growth_media")
        if db_cell_line.growth_media != yaml_media:
            errors.append(
                f"{cell_line_id}: growth_media mismatch "
                f"(YAML: {yaml_media}, DB: {db_cell_line.growth_media})"
            )
        
        # Validate protocols
        for protocol_type in ["passage", "thaw", "feed"]:
            if protocol_type not in yaml_config:
                continue
            
            for vessel_type in yaml_config[protocol_type].keys():
                if vessel_type == "reference_vessel":
                    continue
                
                db_params = db.get_protocol(cell_line_id, protocol_type, vessel_type)
                if db_params is None:
                    errors.append(f"Missing protocol: {cell_line_id} / {protocol_type} / {vessel_type}")
    
    if errors:
        print("\n❌ Validation FAILED:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n✅ Validation PASSED - All data migrated correctly!")
        return True


def print_summary(db: CellLineDatabase):
    """Print summary of migrated data."""
    print("\n" + "="*60)
    print("📊 MIGRATION SUMMARY")
    print("="*60)
    
    cell_lines = db.get_all_cell_lines()
    
    print(f"\n📋 Total Cell Lines: {len(cell_lines)}")
    
    # Group by cell type
    by_type = {}
    for cell_line_id in cell_lines:
        cell_line = db.get_cell_line(cell_line_id)
        cell_type = cell_line.cell_type
        if cell_type not in by_type:
            by_type[cell_type] = []
        by_type[cell_type].append(cell_line_id)
    
    print("\n📊 By Cell Type:")
    for cell_type, lines in sorted(by_type.items()):
        print(f"  {cell_type:15s}: {len(lines)} cell lines")
        for line in sorted(lines):
            print(f"    - {line}")
    
    # Coating requirements
    coating_required = db.find_cell_lines(coating_required=True)
    print(f"\n🧫 Coating Required: {len(coating_required)} cell lines")
    for cell_line in coating_required:
        print(f"  - {cell_line.cell_line_id}: {cell_line.coating_reagent}")
    
    # Cost tiers
    print("\n💰 By Cost Tier:")
    for tier in ["budget", "standard", "premium"]:
        lines = db.find_cell_lines(cost_tier=tier)
        print(f"  {tier:10s}: {len(lines)} cell lines")
    
    print("\n" + "="*60)


def main():
    """Main migration function."""
    print("="*60)
    print("🚀 CELL LINES MIGRATION")
    print("="*60)
    print("\nMigrating from 614-line YAML to SQLite database...")
    
    # Load YAML data
    print("\n📂 Loading YAML data...")
    yaml_path = "data/cell_lines.yaml"
    
    if not Path(yaml_path).exists():
        print(f"❌ Error: {yaml_path} not found!")
        return 1
    
    yaml_data = load_yaml_data(yaml_path)
    print(f"✅ Loaded {yaml_path}")
    print(f"   Found {len(yaml_data.get('cell_lines', {}))} cell lines")
    
    # Create database
    print("\n💾 Creating database...")
    db_path = "data/cell_lines.db"
    
    # Backup existing database if it exists
    if Path(db_path).exists():
        backup_path = f"{db_path}.backup"
        Path(db_path).rename(backup_path)
        print(f"⚠️  Backed up existing database to {backup_path}")
    
    db = CellLineDatabase(db_path)
    print(f"✅ Created {db_path}")
    
    # Migrate data
    metadata_count = migrate_cell_line_metadata(db, yaml_data)
    char_count = migrate_characteristics(db, yaml_data)
    protocol_count = migrate_protocols(db, yaml_data)
    
    # Validate migration
    if not validate_migration(db, yaml_data):
        print("\n❌ Migration failed validation!")
        return 1
    
    # Print summary
    print_summary(db)
    
    print("\n✅ Migration completed successfully!")
    print(f"\n📊 Total records migrated:")
    print(f"  - Cell lines: {metadata_count}")
    print(f"  - Characteristics: {char_count}")
    print(f"  - Protocol parameters: {protocol_count}")
    print(f"\n💾 Database created at: {db_path}")
    print("\n" + "="*60)
    
    return 0


if __name__ == "__main__":
    exit(main())
