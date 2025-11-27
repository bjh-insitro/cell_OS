import yaml
import os

def sync_inventory():
    unitops_path = "data/raw/unitops.yaml"
    pricing_path = "data/raw/pricing.yaml"
    
    # 1. Load Protocols (The Demand)
    if not os.path.exists(unitops_path):
        print(f"❌ Error: {unitops_path} not found.")
        return

    with open(unitops_path, 'r') as f:
        ops_data = yaml.safe_load(f) or {}
        
    # Handle structure (root key vs flat)
    unit_ops = ops_data.get('unit_ops', ops_data)
    
    # 2. Scrape Required Items
    required_items = set()
    print(f"🔍 Scanning {len(unit_ops)} Unit Operations...")
    
    for op_name, details in unit_ops.items():
        # Pattern A: 'consumables' list
        if 'consumables' in details:
            for c in details['consumables']:
                if 'item' in c: required_items.add(c['item'])
        
        # Pattern B: 'items' dict
        if 'items' in details:
            for item_key in details['items']:
                required_items.add(item_key)

    print(f"   Found {len(required_items)} total unique items required.")

    # 3. Load Inventory (The Supply)
    with open(pricing_path, 'r') as f:
        pricing_data = yaml.safe_load(f) or {}

    # 4. Find Gaps
    missing_keys = [item for item in required_items if item not in pricing_data]
    
    if not missing_keys:
        print("\n✅ Inventory is in sync! No missing items.")
        return

    # 5. Auto-Fill Gaps
    print(f"\n⚠️  Found {len(missing_keys)} missing items. Adding placeholders to {pricing_path}...")
    
    with open(pricing_path, 'a') as f:
        f.write("\n# --- AUTO-GENERATED MISSING ITEMS ---\n")
        for key in missing_keys:
            # Guess category based on name
            cat = "consumable"
            if "media" in key or "dmem" in key or "pbs" in key: cat = "reagent"
            if "kit" in key: cat = "kit"
            
            # Template entry
            entry = f"""
{key}:
  name: "{key.replace('_', ' ').title()} (TODO: Price Me)"
  category: {cat}
  unit_price_usd: 0.00
  logical_unit: unit
"""
            f.write(entry)
            print(f"   + Added placeholder for: {key}")

    print("\n✅ Done. Please open 'data/raw/pricing.yaml' and update the prices for the new items.")

if __name__ == "__main__":
    sync_inventory()