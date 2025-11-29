"""
Migrate simulation parameters from YAML to SQLite database.

This script:
1. Loads data from data/simulation_parameters.yaml
2. Creates simulation_params.db
3. Migrates all cell line parameters
4. Migrates all compound sensitivity data
5. Migrates default parameters
6. Validates the migration
"""

import yaml
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.simulation_params_db import (
    SimulationParamsDatabase,
    CellLineSimParams,
    CompoundSensitivity
)


def load_yaml_data(yaml_path: str = "data/simulation_parameters.yaml"):
    """Load simulation parameters from YAML file."""
    with open(yaml_path) as f:
        return yaml.safe_load(f)


def migrate_cell_line_params(db: SimulationParamsDatabase, yaml_data: dict):
    """Migrate cell line parameters to database."""
    print("\n📊 Migrating cell line parameters...")
    
    cell_lines = yaml_data.get("cell_lines", {})
    count = 0
    
    for cell_line_id, params in cell_lines.items():
        # Create params object
        cell_params = CellLineSimParams(
            cell_line_id=cell_line_id,
            doubling_time_h=params.get("doubling_time_h", 24.0),
            max_confluence=params.get("max_confluence", 0.9),
            max_passage=params.get("max_passage", 30),
            senescence_rate=params.get("senescence_rate", 0.01),
            seeding_efficiency=params.get("seeding_efficiency", 0.85),
            passage_stress=params.get("passage_stress", 0.02),
            cell_count_cv=params.get("cell_count_cv", 0.10),
            viability_cv=params.get("viability_cv", 0.02),
            biological_cv=params.get("biological_cv", 0.05),
            coating_required=params.get("coating_required", False),
            version=1,
            notes="Migrated from YAML"
        )
        
        # Add to database
        param_id = db.add_cell_line_params(cell_params)
        count += 1
        print(f"  ✅ {cell_line_id}: param_id={param_id}")
    
    print(f"\n✅ Migrated {count} cell line parameter sets")
    return count


def migrate_compound_sensitivity(db: SimulationParamsDatabase, yaml_data: dict):
    """Migrate compound sensitivity data to database."""
    print("\n🧪 Migrating compound sensitivity data...")
    
    compounds = yaml_data.get("compound_sensitivity", {})
    count = 0
    
    for compound_name, data in compounds.items():
        # Extract hill_slope (same for all cell lines)
        hill_slope = data.get("hill_slope", 1.0)
        
        # Add sensitivity for each cell line
        for key, value in data.items():
            if key != "hill_slope":  # Skip hill_slope, it's not a cell line
                cell_line_id = key
                ic50_um = value
                
                sensitivity = CompoundSensitivity(
                    compound_name=compound_name,
                    cell_line_id=cell_line_id,
                    ic50_um=ic50_um,
                    hill_slope=hill_slope,
                    source="literature",
                    version=1,
                    notes="Migrated from YAML"
                )
                
                sensitivity_id = db.add_compound_sensitivity(sensitivity)
                count += 1
                print(f"  ✅ {compound_name} + {cell_line_id}: IC50={ic50_um} µM")
    
    print(f"\n✅ Migrated {count} compound sensitivity records")
    return count


def migrate_defaults(db: SimulationParamsDatabase, yaml_data: dict):
    """Migrate default parameters to database."""
    print("\n⚙️  Migrating default parameters...")
    
    defaults = yaml_data.get("defaults", {})
    count = 0
    
    for param_name, param_value in defaults.items():
        db.set_default_param(param_name, param_value, f"Default {param_name}")
        count += 1
        print(f"  ✅ {param_name} = {param_value}")
    
    print(f"\n✅ Migrated {count} default parameters")
    return count


def validate_migration(db: SimulationParamsDatabase, yaml_data: dict):
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
    
    # Validate compound count
    yaml_compounds = set(yaml_data.get("compound_sensitivity", {}).keys())
    db_compounds = set(db.get_all_compounds())
    
    if yaml_compounds != db_compounds:
        errors.append(f"Compound mismatch: YAML has {len(yaml_compounds)}, DB has {len(db_compounds)}")
    else:
        print(f"  ✅ Compounds: {len(db_compounds)} matched")
    
    # Validate specific parameters
    for cell_line_id in yaml_cell_lines:
        yaml_params = yaml_data["cell_lines"][cell_line_id]
        db_params = db.get_cell_line_params(cell_line_id)
        
        if db_params is None:
            errors.append(f"Missing params for {cell_line_id}")
            continue
        
        # Check doubling time
        if abs(db_params.doubling_time_h - yaml_params["doubling_time_h"]) > 0.01:
            errors.append(
                f"{cell_line_id}: doubling_time mismatch "
                f"(YAML: {yaml_params['doubling_time_h']}, DB: {db_params.doubling_time_h})"
            )
    
    # Validate compound sensitivities
    for compound_name, data in yaml_data.get("compound_sensitivity", {}).items():
        for cell_line_id, ic50 in data.items():
            if cell_line_id == "hill_slope":
                continue
            
            db_sensitivity = db.get_compound_sensitivity(compound_name, cell_line_id)
            if db_sensitivity is None:
                errors.append(f"Missing sensitivity: {compound_name} + {cell_line_id}")
            elif abs(db_sensitivity.ic50_um - ic50) > 0.01:
                errors.append(
                    f"{compound_name} + {cell_line_id}: IC50 mismatch "
                    f"(YAML: {ic50}, DB: {db_sensitivity.ic50_um})"
                )
    
    if errors:
        print("\n❌ Validation FAILED:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n✅ Validation PASSED - All data migrated correctly!")
        return True


def print_summary(db: SimulationParamsDatabase):
    """Print summary of migrated data."""
    print("\n" + "="*60)
    print("📊 MIGRATION SUMMARY")
    print("="*60)
    
    cell_lines = db.get_all_cell_lines()
    compounds = db.get_all_compounds()
    
    print(f"\n📋 Cell Lines: {len(cell_lines)}")
    for cell_line in sorted(cell_lines):
        params = db.get_cell_line_params(cell_line)
        print(f"  - {cell_line}: {params.doubling_time_h}h doubling time")
    
    print(f"\n🧪 Compounds: {len(compounds)}")
    for compound in sorted(compounds):
        print(f"  - {compound}")
    
    print("\n" + "="*60)


def main():
    """Main migration function."""
    print("="*60)
    print("🚀 SIMULATION PARAMETERS MIGRATION")
    print("="*60)
    print("\nMigrating from YAML to SQLite database...")
    
    # Load YAML data
    print("\n📂 Loading YAML data...")
    yaml_path = "data/simulation_parameters.yaml"
    
    if not Path(yaml_path).exists():
        print(f"❌ Error: {yaml_path} not found!")
        return 1
    
    yaml_data = load_yaml_data(yaml_path)
    print(f"✅ Loaded {yaml_path}")
    
    # Create database
    print("\n💾 Creating database...")
    db_path = "data/simulation_params.db"
    
    # Backup existing database if it exists
    if Path(db_path).exists():
        backup_path = f"{db_path}.backup"
        Path(db_path).rename(backup_path)
        print(f"⚠️  Backed up existing database to {backup_path}")
    
    db = SimulationParamsDatabase(db_path)
    print(f"✅ Created {db_path}")
    
    # Migrate data
    cell_line_count = migrate_cell_line_params(db, yaml_data)
    compound_count = migrate_compound_sensitivity(db, yaml_data)
    default_count = migrate_defaults(db, yaml_data)
    
    # Validate migration
    if not validate_migration(db, yaml_data):
        print("\n❌ Migration failed validation!")
        return 1
    
    # Print summary
    print_summary(db)
    
    print("\n✅ Migration completed successfully!")
    print(f"\n📊 Total records migrated:")
    print(f"  - Cell line parameters: {cell_line_count}")
    print(f"  - Compound sensitivities: {compound_count}")
    print(f"  - Default parameters: {default_count}")
    print(f"\n💾 Database created at: {db_path}")
    print("\n" + "="*60)
    
    return 0


if __name__ == "__main__":
    exit(main())
