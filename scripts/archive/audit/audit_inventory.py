import yaml
import os
import sys

def audit_pricing_file():
    yaml_path = "data/raw/pricing.yaml"
    
    # 1. Check if file exists
    if not os.path.exists(yaml_path):
        print(f"❌ CRITICAL: File not found at {yaml_path}")
        return

    # 2. Load the file
    with open(yaml_path, 'r') as f:
        inventory = yaml.safe_load(f) or {}

    print(f"🔍 Auditing {yaml_path}...")
    print(f"   Found {len(inventory)} total items defined.")

    # 3. Define the "Must Have" list (Based on budget_manager.py logic)
    required_keys = [
        # Plastics
        "plate_6well",
        "flow_tubes_5ml",
        "tips_1000ul",
        
        # Biologicals
        "media_dmem_complete",
        "trypsin_edta", 
        "pbs_1x",
        
        # Flow Reagents
        "flow_buffer",
        "viability_dye_zombie",
        
        # Critical
        "lentivirus_stock",
        "polybrene"
    ]

    # 4. Run the Check
    missing = []
    print("\n📋 Requirement Check:")
    print("-" * 40)
    
    for key in required_keys:
        if key in inventory:
            item = inventory[key]
            price = item.get('unit_price_usd', 0.0)
            unit = item.get('logical_unit', '???')
            print(f"   ✅ {key:<25} ${price:.2f} / {unit}")
        else:
            print(f"   ❌ {key:<25} MISSING!")
            missing.append(key)

    print("-" * 40)

    # 5. Verdict
    if missing:
        print(f"\n🛑 AUDIT FAILED. You are missing {len(missing)} items.")
        print("   The budget calculator will return $0.00 or crash for these items.")
        print(f"   Missing keys: {missing}")
        sys.exit(1)
    else:
        print("\n✅ AUDIT PASSED. Your inventory is ready for the campaign.")
        sys.exit(0)

if __name__ == "__main__":
    audit_pricing_file()