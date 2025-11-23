"""
Zombie POSH Shopping List Generator

Generates a complete shopping list for Zombie POSH experiments based on:
- Number of plates
- Plate format (6-well, 12-well, 96-well)
- Whether doing multimodal imaging
- Current inventory levels (optional)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import json

@dataclass
class ReagentItem:
    """Single reagent item for shopping list."""
    name: str
    vendor: str
    catalog_number: str
    quantity_needed: float
    unit: str
    pack_size: float
    pack_unit: str
    pack_price_usd: float
    packs_to_order: int
    total_cost_usd: float
    category: str
    notes: str = ""

class ZombiePOSHShoppingList:
    """Generate shopping lists for Zombie POSH experiments."""
    
    # Reagent consumption per well (in specified units)
    REAGENT_USAGE = {
        # Zombie-specific reagents
        "hiscribe_t7_kit": {"per_well": 1, "unit": "reaction", "category": "Zombie Core"},
        "sodium_bicarbonate": {"per_well": 0.084, "unit": "g", "category": "Zombie Core"},  # 0.1M in ~100mL
        "nacl_5m": {"per_well": 0.6, "unit": "mL", "category": "Zombie Core"},  # 0.3M final
        "tris_1m": {"per_well": 0.1, "unit": "mL", "category": "Zombie Core"},
        "ribolock": {"per_well": 40, "unit": "U", "category": "Zombie Core"},  # 0.4 U/µL × 100µL
        
        # Oligos (Zombie-specific)
        "zombie_pd_padlock": {"per_well": 0.01, "unit": "nmol", "category": "Zombie Oligos"},
        "zombie_sbs2_primer": {"per_well": 0.01, "unit": "nmol", "category": "Zombie Oligos"},
        "rt_primer_odf136": {"per_well": 0.01, "unit": "nmol", "category": "Shared Oligos"},
        
        # Multimodal imaging (optional)
        "hcr_probe_set": {"per_well": 0.5, "unit": "set", "category": "Multimodal"},  # 3 genes, reusable
        "hcr_amplifier_set": {"per_well": 0.3, "unit": "set", "category": "Multimodal"},
        "lithium_borohydride": {"per_well": 0.0001, "unit": "g", "category": "Multimodal"},  # 1mg/mL × 100µL
        
        # Cell Painting dyes
        "phalloidin_568": {"per_well": 0.33, "unit": "unit", "category": "Cell Painting"},
        "cona_488": {"per_well": 1.25, "unit": "µg", "category": "Cell Painting"},
        "wga_555": {"per_well": 0.15, "unit": "µg", "category": "Cell Painting"},
        "hoechst": {"per_well": 0.02, "unit": "µg", "category": "Cell Painting"},
        "mitoprobe_12s_cy5": {"per_well": 0.025, "unit": "nmol", "category": "Cell Painting"},
        "mitoprobe_16s_cy5": {"per_well": 0.025, "unit": "nmol", "category": "Cell Painting"},
        
        # SBS reagents
        "miseq_reagent_v2_cycle": {"per_well": 13, "unit": "cycle", "category": "SBS"},  # 13 cycles
        
        # Consumables
        "cellvis_plate": {"per_well": 1, "unit": "plate", "category": "Consumables"},
        "plate_seals": {"per_well": 3, "unit": "seal", "category": "Consumables"},  # Multiple sealing steps
        
        # Buffers (shared)
        "pbs_rnase_free": {"per_well": 5, "unit": "mL", "category": "Buffers"},
        "ssc_20x": {"per_well": 2, "unit": "mL", "category": "Buffers"},
        "pfa_16pct": {"per_well": 0.5, "unit": "mL", "category": "Buffers"},
        "triton_x100": {"per_well": 0.1, "unit": "mL", "category": "Buffers"},
        "ethanol_molbio": {"per_well": 2, "unit": "mL", "category": "Buffers"},
    }
    
    # Catalog information
    CATALOG_INFO = {
        "hiscribe_t7_kit": {
            "name": "HiScribe T7 Quick High Yield RNA Synthesis Kit",
            "vendor": "New England Biolabs",
            "catalog": "E2050S",
            "pack_size": 50,
            "pack_unit": "reaction",
            "pack_price": 450.0,
        },
        "sodium_bicarbonate": {
            "name": "Sodium Bicarbonate (Fine White Powder)",
            "vendor": "FisherScientific",
            "catalog": "BP328-500",
            "pack_size": 500,
            "pack_unit": "g",
            "pack_price": 50.0,
        },
        "nacl_5m": {
            "name": "NaCl (5 M) RNase-free",
            "vendor": "FisherScientific",
            "catalog": "AM9760G",
            "pack_size": 100,
            "pack_unit": "mL",
            "pack_price": 80.0,
        },
        "tris_1m": {
            "name": "Tris (1 M) pH 8.0 RNase-free",
            "vendor": "FisherScientific",
            "catalog": "AM9855G",
            "pack_size": 100,
            "pack_unit": "mL",
            "pack_price": 60.0,
        },
        "ribolock": {
            "name": "RiboLock RNase Inhibitor",
            "vendor": "Thermo",
            "catalog": "EO0381",
            "pack_size": 2500,
            "pack_unit": "U",
            "pack_price": 120.0,
        },
        "zombie_pd_padlock": {
            "name": "Zombie_PD Padlock Probe (custom)",
            "vendor": "IDT",
            "catalog": "custom",
            "pack_size": 100,
            "pack_unit": "nmol",
            "pack_price": 30.0,
            "notes": "Sequence: /5Phos/gtttaagagctaagctggCTCCTGTTCGACAGTCAGCGCCATCTCCGACTTATTgctttatatatcttgtggaaaggac"
        },
        "zombie_sbs2_primer": {
            "name": "Zombie_SBS_2 Sequencing Primer (custom)",
            "vendor": "IDT",
            "catalog": "custom",
            "pack_size": 100,
            "pack_unit": "nmol",
            "pack_price": 25.0,
            "notes": "Sequence: CTCCTGTTCGACAGTCAGCGCCATCTCCGACTTATTgctttatatatcttgtggaaaggacgaaacaccg"
        },
        "rt_primer_odf136": {
            "name": "RT Primer oDF-136 (custom)",
            "vendor": "IDT",
            "catalog": "custom (Primer 135)",
            "pack_size": 100,
            "pack_unit": "nmol",
            "pack_price": 25.0,
            "notes": "Sequence: /5AmMC12/G+AC+TA+GC+CT+TA+TT+TaAACTTGCTAT"
        },
        "cellvis_plate": {
            "name": "Cellvis 6-well Glass Bottom Plate (high heat)",
            "vendor": "Cellvis",
            "catalog": "P06-1.5H-N",
            "pack_size": 10,
            "pack_unit": "plate",
            "pack_price": 250.0,
        },
        "plate_seals": {
            "name": "MicroAmp Clear Adhesive Film",
            "vendor": "Applied Biosystems",
            "catalog": "4306311",
            "pack_size": 100,
            "pack_unit": "seal",
            "pack_price": 150.0,
        },
        # Add more as needed...
    }
    
    def __init__(self, num_plates: int, wells_per_plate: int = 6, multimodal: bool = False, 
                 safety_factor: float = 1.2):
        """
        Initialize shopping list generator.
        
        Args:
            num_plates: Number of plates to run
            wells_per_plate: Wells per plate (6, 12, or 96)
            multimodal: Whether doing multimodal imaging (HCR FISH + IBEX)
            safety_factor: Overage factor (default 1.2 = 20% extra)
        """
        self.num_plates = num_plates
        self.wells_per_plate = wells_per_plate
        self.total_wells = num_plates * wells_per_plate
        self.multimodal = multimodal
        self.safety_factor = safety_factor
        
    def generate_shopping_list(self, current_inventory: Optional[Dict[str, float]] = None) -> List[ReagentItem]:
        """
        Generate complete shopping list.
        
        Args:
            current_inventory: Dict of reagent_id -> quantity on hand (optional)
            
        Returns:
            List of ReagentItem objects to order
        """
        shopping_list = []
        current_inventory = current_inventory or {}
        
        for reagent_id, usage_info in self.REAGENT_USAGE.items():
            # Skip multimodal reagents if not needed
            if usage_info["category"] == "Multimodal" and not self.multimodal:
                continue
            
            # Calculate total needed
            per_well = usage_info["per_well"]
            total_needed = per_well * self.total_wells * self.safety_factor
            
            # Subtract current inventory
            on_hand = current_inventory.get(reagent_id, 0)
            to_order = max(0, total_needed - on_hand)
            
            if to_order == 0:
                continue  # Skip if we have enough
            
            # Get catalog info
            if reagent_id not in self.CATALOG_INFO:
                continue  # Skip if no catalog info
            
            catalog = self.CATALOG_INFO[reagent_id]
            
            # Calculate packs to order
            pack_size = catalog["pack_size"]
            packs_needed = int(to_order / pack_size) + (1 if to_order % pack_size > 0 else 0)
            
            # Create reagent item
            item = ReagentItem(
                name=catalog["name"],
                vendor=catalog["vendor"],
                catalog_number=catalog["catalog"],
                quantity_needed=to_order,
                unit=usage_info["unit"],
                pack_size=pack_size,
                pack_unit=catalog["pack_unit"],
                pack_price_usd=catalog["pack_price"],
                packs_to_order=packs_needed,
                total_cost_usd=packs_needed * catalog["pack_price"],
                category=usage_info["category"],
                notes=catalog.get("notes", "")
            )
            
            shopping_list.append(item)
        
        return shopping_list
    
    def print_shopping_list(self, shopping_list: List[ReagentItem]):
        """Print formatted shopping list."""
        print("=" * 100)
        print(f"ZOMBIE POSH SHOPPING LIST")
        print(f"Experiment: {self.num_plates} plates × {self.wells_per_plate} wells = {self.total_wells} wells")
        print(f"Multimodal: {'Yes' if self.multimodal else 'No'}")
        print(f"Safety factor: {self.safety_factor:.0%}")
        print("=" * 100)
        
        # Group by category
        categories = {}
        for item in shopping_list:
            if item.category not in categories:
                categories[item.category] = []
            categories[item.category].append(item)
        
        total_cost = 0
        
        for category, items in sorted(categories.items()):
            print(f"\n** {category} **")
            print(f"{'Item':<50} {'Vendor':<20} {'Catalog #':<15} {'Qty':<15} {'Packs':<8} {'Cost':<10}")
            print("-" * 100)
            
            category_cost = 0
            for item in items:
                qty_str = f"{item.quantity_needed:.1f} {item.unit}"
                packs_str = f"{item.packs_to_order}×{item.pack_size}"
                cost_str = f"${item.total_cost_usd:.2f}"
                
                print(f"{item.name:<50} {item.vendor:<20} {item.catalog_number:<15} {qty_str:<15} {packs_str:<8} {cost_str:<10}")
                
                if item.notes:
                    print(f"  → {item.notes}")
                
                category_cost += item.total_cost_usd
            
            print(f"{'':>90} Subtotal: ${category_cost:.2f}")
            total_cost += category_cost
        
        print("\n" + "=" * 100)
        print(f"{'':>85} TOTAL: ${total_cost:.2f}")
        print("=" * 100)
        
        return total_cost


if __name__ == "__main__":
    # Example usage
    print("\n[Example 1] Small experiment: 2 plates, 6-well, simple")
    generator = ZombiePOSHShoppingList(num_plates=2, wells_per_plate=6, multimodal=False)
    shopping_list = generator.generate_shopping_list()
    generator.print_shopping_list(shopping_list)
    
    print("\n\n[Example 2] Large experiment: 10 plates, 6-well, multimodal")
    generator = ZombiePOSHShoppingList(num_plates=10, wells_per_plate=6, multimodal=True)
    shopping_list = generator.generate_shopping_list()
    generator.print_shopping_list(shopping_list)
    
    print("\n\n[Example 3] With existing inventory")
    current_inventory = {
        "hiscribe_t7_kit": 25,  # 25 reactions on hand
        "sodium_bicarbonate": 200,  # 200g on hand
        "ribolock": 1000,  # 1000 U on hand
    }
    generator = ZombiePOSHShoppingList(num_plates=5, wells_per_plate=6, multimodal=False)
    shopping_list = generator.generate_shopping_list(current_inventory=current_inventory)
    print(f"\nWith inventory: {current_inventory}")
    generator.print_shopping_list(shopping_list)
