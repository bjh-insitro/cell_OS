"""
Demo script showing the power of the Cell Line Database.

This demonstrates queries that were difficult/impossible with YAML files.
"""

from cell_os.cell_line_db import CellLineDatabase

def main():
    print("="*60)
    print("🔬 CELL LINE DATABASE - DEMO")
    print("="*60)
    
    # Initialize database
    db = CellLineDatabase("data/cell_lines.db")
    
    # Query 1: Find all cell lines
    print("\n📋 Query 1: All cell lines")
    print("-" * 40)
    cell_lines = db.get_all_cell_lines()
    for cell_line_id in sorted(cell_lines):
        cell_line = db.get_cell_line(cell_line_id)
        print(f"  {cell_line_id:20s} | {cell_line.cell_type:15s} | {cell_line.cost_tier}")
    
    # Query 2: Find cell lines requiring coating
    print("\n🧫 Query 2: Cell lines requiring coating")
    print("-" * 40)
    coating_lines = db.find_cell_lines(coating_required=True)
    for cell_line in coating_lines:
        print(f"  {cell_line.cell_line_id:20s} | Coating: {cell_line.coating_reagent}")
    
    # Query 3: Find budget-friendly cell lines
    print("\n💰 Query 3: Budget-friendly cell lines")
    print("-" * 40)
    budget_lines = db.find_cell_lines(cost_tier="budget")
    for cell_line in budget_lines:
        print(f"  {cell_line.cell_line_id:20s} | Media: {cell_line.growth_media}")
    
    # Query 4: Find iPSC and stem cells
    print("\n🧬 Query 4: Stem cells (iPSC, hESC)")
    print("-" * 40)
    for cell_type in ["iPSC", "hESC"]:
        stem_cells = db.find_cell_lines(cell_type=cell_type)
        for cell_line in stem_cells:
            print(f"  {cell_line.cell_line_id:20s} | {cell_line.display_name}")
    
    # Query 5: Get protocol parameters
    print("\n⚗️  Query 5: Passage protocol for iPSC in T75 flask")
    print("-" * 40)
    passage_params = db.get_protocol("iPSC", "passage", "T75")
    if passage_params:
        print("  Volumes (reference):")
        for key, value in passage_params.get("volumes_mL_reference", {}).items():
            print(f"    {key:15s}: {value} mL")
        print("  Incubation:")
        detach = passage_params.get("incubation", {}).get("detach", {})
        print(f"    Temperature: {detach.get('temp_C')}°C")
        print(f"    Duration: {detach.get('minutes')} minutes")
    
    # Query 6: Get characteristics
    print("\n🔬 Query 6: Characteristics of HEK293T")
    print("-" * 40)
    chars = db.get_characteristics("HEK293T")
    for key, value in sorted(chars.items()):
        print(f"  {key:25s}: {value}")
    
    # Query 7: Find primary cells
    print("\n🧫 Query 7: Primary cell lines")
    print("-" * 40)
    primary_cells = db.find_cell_lines(cell_type="primary")
    for cell_line in primary_cells:
        print(f"  {cell_line.cell_line_id:20s} | {cell_line.display_name}")
    
    # Query 8: Find differentiated cells
    print("\n🧬 Query 8: Differentiated cell lines")
    print("-" * 40)
    diff_cells = db.find_cell_lines(cell_type="differentiated")
    for cell_line in diff_cells:
        chars = db.get_characteristics(cell_line.cell_line_id)
        media = chars.get("media", "unknown")
        print(f"  {cell_line.cell_line_id:20s} | Media: {media}")
    
    # Query 9: Compare feeding schedules
    print("\n📅 Query 9: Feeding schedules (T75 flasks)")
    print("-" * 40)
    for cell_line_id in ["iPSC", "HEK293", "Primary_Neurons"]:
        feed_params = db.get_protocol(cell_line_id, "feed", "T75")
        if feed_params:
            interval = feed_params.get("schedule", {}).get("interval_days", "N/A")
            volume = feed_params.get("volume_ml", "N/A")
            print(f"  {cell_line_id:20s} | Every {interval} days | {volume} mL")
    
    # Query 10: Summary statistics
    print("\n📊 Query 10: Summary statistics")
    print("-" * 40)
    all_lines = db.get_all_cell_lines()
    print(f"  Total cell lines: {len(all_lines)}")
    
    by_type = {}
    for cell_line_id in all_lines:
        cell_line = db.get_cell_line(cell_line_id)
        cell_type = cell_line.cell_type
        by_type[cell_type] = by_type.get(cell_type, 0) + 1
    
    print("  By type:")
    for cell_type, count in sorted(by_type.items()):
        print(f"    {cell_type:15s}: {count}")
    
    coating_count = len(db.find_cell_lines(coating_required=True))
    print(f"  Requiring coating: {coating_count}")
    
    print("\n" + "="*60)
    print("✅ Demo complete!")
    print("\n💡 These queries would require complex YAML parsing!")
    print("   Now they're simple database queries!")
    print("="*60)

if __name__ == "__main__":
    main()
