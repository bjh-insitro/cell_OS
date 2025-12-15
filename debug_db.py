
import sqlite3
import os

db_path = "data/cell_thalamus_results.db"

print(f"Checking database at: {os.path.abspath(db_path)}")

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Count total results
        cursor.execute("SELECT COUNT(*) FROM thalamus_results")
        count = cursor.fetchone()[0]
        print(f"Total rows in thalamus_results: {count}")
        
        # Grouped counts
        print("\n--- Top 20 Conditions (Compound x Cell Line x Timepoint) ---")
        query = """
        SELECT compound, cell_line, timepoint_h, count(*) as n_wells 
        FROM thalamus_results 
        GROUP BY compound, cell_line, timepoint_h
        ORDER BY n_wells DESC
        LIMIT 20
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        print(f"{'Compound':<20} {'Cell Line':<15} {'Time (h)':<10} {'Wells':<10}")
        print("-" * 60)
        for row in rows:
            print(f"{str(row[0]):<20} {str(row[1]):<15} {str(row[2]):<10} {str(row[3]):<10}")

        print("\n--- Recent Designs ---")
        cursor.execute("SELECT design_id, phase, created_at FROM thalamus_designs ORDER BY created_at DESC LIMIT 5")
        designs = cursor.fetchall()
        for d in designs:
            print(d)

        conn.close()
    except Exception as e:
        print(f"Error reading database: {e}")
