import yaml
import os
import sys

def load_yaml(path):
    if not os.path.exists(path):
        print(f"⚠️  Warning: {path} not found.")
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}

def scan_required_items():
    print("🔍 SCANNING PLATFORM PROTOCOLS...")
    
    # 1. Load the Recipes (Unit Ops)
    ops_data = load_yaml("data/raw/unitops.yaml")
    unit_ops = ops_data.get('unit_ops', {})
    
    if not unit_ops:
        print("❌ No Unit Ops found in data/raw/unitops.yaml")
        return set()

    print(f"   Found {len(unit_ops)} Unit Operations defined.")
    
    # 2. Scrape every required item
    required_items = set()
    
    for op_name, details in unit_ops.items():
        # Handle Structure A: "consumables" list (Titration logic)
        if 'consumables' in details:
            for c in details['consumables']:
                if 'item' in c: required_items.add(c['item'])
        
        # Handle Structure B: "items" dictionary (Your older complex logic)
        if 'items' in details:
            for item_key in details['items']:
                required_items.add(item_key)

    print(f"    identified {len(required_items)} unique materials required across all protocols.")
    return required_items

def check_inventory(required_items):
    print("\n💰 CHECKING PRICING DATABASE...")
    
    pricing_data = load_yaml("data/raw/pricing.yaml")
    
    missing = []
    found_count = 0
    
    print("-" * 60)
    print(f"{'MATERIAL':<35} | {'STATUS':<10} | {'PRICE':<10}")
    print("-" * 60)
    
    for item in sorted(required_items):
        if item in pricing_data:
            price = pricing_data[item].get('unit_price_usd', 0.0)
            unit = pricing_data[item].get('logical_unit', 'unit')
            print(f"{item:<35} | ✅ FOUND   | ${price:.2f}/{unit}")
            found_count += 1
        else:
            print(f"{item:<35} | ❌ MISSING | ???")
            missing.append(item)
            
    print("-" * 60)
    
    # Final Verdict
    if missing:
        print(f"\n🛑 AUDIT FAILED.")
        print(f"   You have {len(missing)} items defined in your protocols (unitops.yaml)")
        print(f"   that are missing from your price list (pricing.yaml).")
        print("\n   Run 'python fix_inventory.py' and add these keys:")
        print(f"   {missing}")
        sys.exit(1)
    else:
        print("\n✅ AUDIT PASSED. All protocols are fully priced.")
        sys.exit(0)

if __name__ == "__main__":
    reqs = scan_required_items()
    check_inventory(reqs)