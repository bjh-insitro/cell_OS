
import sqlite3
import os

db_path = "data/cell_thalamus_results.db"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("\n--- Designs ---")
        cursor.execute("SELECT design_id, phase, created_at FROM thalamus_designs")
        designs = cursor.fetchall()
        design_ids = set()
        for d in designs:
            print(d)
            design_ids.add(d[0])
            
        print("\n--- Results by Design ID ---")
        cursor.execute("SELECT design_id, count(*) FROM thalamus_results GROUP BY design_id")
        result_groups = cursor.fetchall()
        
        for r in result_groups:
            did = r[0]
            count = r[1]
            status = "MATCH" if did in design_ids else "ORPHAN"
            print(f"Design: {did} | Count: {count} | Status: {status}")

        conn.close()
    except Exception as e:
        print(f"Error reading database: {e}")
