"""
Migrate experimental results from CSV to SQLite.
"""

import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from cell_os.experimental_db import ExperimentalDatabase

def migrate():
    csv_path = "data/raw/phase0_all_plates.csv"
    db_path = "data/experimental_results.db"
    
    print(f"Reading {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: {csv_path} not found.")
        return
    
    print(f"Found {len(df)} records.")
    
    print(f"Initializing database at {db_path}...")
    db = ExperimentalDatabase(db_path)
    
    print("Migrating data...")
    db.add_measurements(df)
    
    print("Migration complete.")
    
    # Verify
    stats = db.get_summary_stats()
    print("\nDatabase Summary:")
    print(f"Total Measurements: {stats['total_measurements']}")
    print(f"Unique Cell Lines: {len(stats['cell_lines'])} ({', '.join(stats['cell_lines'][:5])}...)")
    print(f"Unique Compounds: {len(stats['compounds'])} ({', '.join(stats['compounds'][:5])}...)")
    print(f"Total Plates: {stats['plates']}")

if __name__ == "__main__":
    migrate()
