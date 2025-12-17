"""
Hardware Registry module.

Loads and manages the lab's physical hardware inventory.
Provides queries for experiment planning and feasibility checks.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import yaml


@dataclass
class HardwareItem:
    """Single piece of hardware equipment"""
    id: str
    category: str  # liquid_handler, imager, incubator, etc.
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    status: str = "operational"  # operational | maintenance | offline
    location: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HardwareRegistry:
    """
    Registry for physical lab equipment and resources.

    Mirrors the structure in hardware_inventory.yaml
    """
    inventory_path: Path
    _raw_data: Dict[str, Any] = field(default_factory=dict)
    _indexed_hardware: Dict[str, HardwareItem] = field(default_factory=dict)

    def __post_init__(self):
        """Load inventory on initialization"""
        self.reload()

    def reload(self):
        """Reload inventory from YAML file"""
        if not self.inventory_path.exists():
            raise FileNotFoundError(f"Hardware inventory not found: {self.inventory_path}")

        with open(self.inventory_path, 'r') as f:
            self._raw_data = yaml.safe_load(f)

        # Index all hardware items by ID
        self._indexed_hardware = {}
        self._index_category('liquid_handlers')
        self._index_category('imaging_systems')
        self._index_category('plate_readers')
        self._index_category('incubators')
        self._index_category('plate_hotels')
        self._index_category('plate_washers')
        self._index_category('compound_dispensers')
        self._index_category('centrifuges')
        self._index_category('cell_counters')
        self._index_category('microscopes')
        self._index_category('shakers')

    def _index_category(self, category: str):
        """Index hardware items from a category"""
        items = self._raw_data.get(category, [])
        if not items:
            return

        for item in items:
            if not isinstance(item, dict) or 'id' not in item:
                continue

            hw_item = HardwareItem(
                id=item['id'],
                category=category,
                manufacturer=item.get('manufacturer'),
                model=item.get('model'),
                status=item.get('status', 'operational'),
                location=item.get('location'),
                capabilities=item.get('capabilities', []),
                metadata=item
            )
            self._indexed_hardware[item['id']] = hw_item

    # ========================================================================
    # Query Methods
    # ========================================================================

    def get_hardware(self, hardware_id: str) -> Optional[HardwareItem]:
        """Get hardware by ID"""
        return self._indexed_hardware.get(hardware_id)

    def get_all_hardware(self) -> List[HardwareItem]:
        """Get all hardware items"""
        return list(self._indexed_hardware.values())

    def get_by_category(self, category: str) -> List[HardwareItem]:
        """Get all hardware in a category"""
        return [hw for hw in self._indexed_hardware.values() if hw.category == category]

    def get_operational(self, category: Optional[str] = None) -> List[HardwareItem]:
        """Get all operational hardware, optionally filtered by category"""
        hw_list = self.get_all_hardware() if category is None else self.get_by_category(category)
        return [hw for hw in hw_list if hw.status == 'operational']

    def get_by_capability(self, capability: str) -> List[HardwareItem]:
        """Find all hardware with a specific capability"""
        return [
            hw for hw in self._indexed_hardware.values()
            if capability in hw.capabilities
        ]

    def has_capability(self, capability: str) -> bool:
        """Check if lab has any operational hardware with this capability"""
        hw_list = self.get_by_capability(capability)
        return any(hw.status == 'operational' for hw in hw_list)

    # ========================================================================
    # Cell Lines & Compounds
    # ========================================================================

    def get_cell_lines(self) -> List[Dict[str, Any]]:
        """Get all available cell lines"""
        return self._raw_data.get('cell_lines', [])

    def get_cell_line(self, name: str) -> Optional[Dict[str, Any]]:
        """Get specific cell line by name"""
        for cl in self.get_cell_lines():
            if cl.get('name') == name:
                return cl
        return None

    def get_compound_libraries(self) -> List[Dict[str, Any]]:
        """Get all compound libraries"""
        return self._raw_data.get('compound_libraries', [])

    def get_compound_library(self, library_id: str) -> Optional[Dict[str, Any]]:
        """Get specific compound library"""
        for lib in self.get_compound_libraries():
            if lib.get('library_id') == library_id:
                return lib
        return None

    def get_available_compounds(self) -> List[str]:
        """Get list of all available compound names"""
        compounds = []
        for lib in self.get_compound_libraries():
            for comp in lib.get('compounds', []):
                compounds.append(comp.get('name'))
        return compounds

    # ========================================================================
    # Feasibility Checks
    # ========================================================================

    def can_perform_liquid_handling(self) -> bool:
        """Check if lab can perform liquid handling operations"""
        return len(self.get_operational('liquid_handlers')) > 0

    def can_perform_imaging(self, channels_required: int = 1) -> bool:
        """Check if lab can perform imaging with required channels"""
        for hw in self.get_operational('imaging_systems'):
            channels = hw.metadata.get('channels', 0)

            # Handle both old format (int) and new format (dict)
            if isinstance(channels, dict):
                # Extract fluorescence channel count
                fluor_channels = channels.get('fluorescence', 0)
                # Handle string values like "5+" or "4-6"
                if isinstance(fluor_channels, str):
                    # Extract first number from strings like "5+" or "4-6"
                    import re
                    match = re.search(r'\d+', fluor_channels)
                    if match:
                        fluor_channels = int(match.group())
                    else:
                        fluor_channels = 0
                channels = fluor_channels

            if channels >= channels_required:
                return True
        return False

    def can_perform_cell_painting(self) -> bool:
        """Check if lab can perform 5-channel Cell Painting"""
        return self.can_perform_imaging(channels_required=5)

    def can_perform_atp_assay(self) -> bool:
        """Check if lab has luminescence plate reader"""
        for hw in self.get_operational('plate_readers'):
            modes = hw.metadata.get('detection_modes', [])
            if 'luminescence' in modes:
                return True
        return False

    def estimate_throughput(self, design_type: str = "phase0") -> Dict[str, Any]:
        """
        Estimate throughput based on available hardware.

        Returns dict with:
            - plates_per_day: int
            - operator_hours_per_day: float
            - automation_level: str (manual | semi-automated | fully-automated)
            - bottlenecks: List[str]
        """
        bottlenecks = []

        # Check liquid handling
        liquid_handlers = self.get_operational('liquid_handlers')
        if not liquid_handlers:
            return {
                "plates_per_day": 0,
                "operator_hours_per_day": 0,
                "automation_level": "none",
                "bottlenecks": ["No liquid handling equipment available"]
            }

        # Check imaging
        imagers = self.get_operational('imaging_systems')
        if not imagers:
            bottlenecks.append("No imaging system available")

        # Check incubation capacity
        incubators = self.get_operational('incubators')
        plate_hotels = self.get_operational('plate_hotels')

        total_incubation_capacity = 0
        for hw in incubators + plate_hotels:
            # Handle both old format (capacity_plates) and new format (capacity.max_plates)
            capacity = hw.metadata.get('capacity_plates', 0)
            if capacity == 0:
                # Try nested format
                capacity_dict = hw.metadata.get('capacity', {})
                if isinstance(capacity_dict, dict):
                    capacity = capacity_dict.get('max_plates', 0)
            total_incubation_capacity += capacity

        if total_incubation_capacity < 20:
            bottlenecks.append(f"Limited incubation capacity ({total_incubation_capacity} plates)")

        # Estimate automation level
        has_automated_hotel = False
        for hw in plate_hotels:
            # Handle both old format (automated) and new format (automation.robotic_access)
            if hw.metadata.get('automated', False):
                has_automated_hotel = True
                break
            automation_dict = hw.metadata.get('automation', {})
            if isinstance(automation_dict, dict) and automation_dict.get('robotic_access', False):
                has_automated_hotel = True
                break

        # Determine automation level based on capabilities
        has_robotic_integration = has_automated_hotel

        # Check for compound dispensing automation (Echo or Certus)
        has_automated_compound_dosing = False
        for lh in liquid_handlers:
            if 'echo' in lh.id.lower() or 'certus' in lh.id.lower():
                has_automated_compound_dosing = True
                break

        # Estimate automation level and throughput
        if has_automated_hotel and len(imagers) > 0 and len(liquid_handlers) >= 3:
            # Fully automated: robotic hotel, multiple liquid handlers, imaging
            automation_level = "fully-automated"
            plates_per_day = 24  # Can run Phase 0 screen (24 plates) in 1-2 days
            operator_hours = 2
        elif has_automated_hotel and len(imagers) > 0:
            automation_level = "semi-automated"
            plates_per_day = 20
            operator_hours = 2
        elif len(liquid_handlers) > 0:
            automation_level = "manual"
            plates_per_day = 5
            operator_hours = 4
        else:
            automation_level = "manual"
            plates_per_day = 2
            operator_hours = 6

        return {
            "plates_per_day": plates_per_day,
            "operator_hours_per_day": operator_hours,
            "automation_level": automation_level,
            "bottlenecks": bottlenecks
        }

    # ========================================================================
    # Summary & Reporting
    # ========================================================================

    def get_summary(self) -> Dict[str, Any]:
        """Get high-level summary of lab capabilities"""
        all_hw = self.get_all_hardware()
        operational = [hw for hw in all_hw if hw.status == 'operational']

        return {
            "metadata": self._raw_data.get('metadata', {}),
            "total_hardware_items": len(all_hw),
            "operational_items": len(operational),
            "cell_lines_available": len(self.get_cell_lines()),
            "compound_libraries": len(self.get_compound_libraries()),
            "total_compounds": len(self.get_available_compounds()),
            "capabilities": {
                "liquid_handling": self.can_perform_liquid_handling(),
                "high_content_imaging": self.can_perform_imaging(channels_required=5),
                "cell_painting": self.can_perform_cell_painting(),
                "atp_assay": self.can_perform_atp_assay(),
            },
            "estimated_throughput": self.estimate_throughput()
        }

    def print_summary(self):
        """Print human-readable summary"""
        summary = self.get_summary()

        print("\n" + "="*80)
        print("HARDWARE INVENTORY SUMMARY")
        print("="*80)

        meta = summary['metadata']
        print(f"\nLab: {meta.get('lab_name', 'N/A')}")
        print(f"Location: {meta.get('location', 'N/A')}")
        print(f"Last Updated: {meta.get('last_updated', 'N/A')}")

        print(f"\nHardware Items: {summary['operational_items']}/{summary['total_hardware_items']} operational")
        print(f"Cell Lines: {summary['cell_lines_available']}")
        print(f"Compound Libraries: {summary['compound_libraries']} ({summary['total_compounds']} compounds)")

        print("\nCapabilities:")
        for cap, available in summary['capabilities'].items():
            status = "✓" if available else "✗"
            print(f"  {status} {cap.replace('_', ' ').title()}")

        print("\nEstimated Throughput:")
        throughput = summary['estimated_throughput']
        print(f"  Automation Level: {throughput['automation_level']}")
        print(f"  Plates/Day: {throughput['plates_per_day']}")
        print(f"  Operator Hours/Day: {throughput['operator_hours_per_day']}")

        if throughput['bottlenecks']:
            print("\nBottlenecks:")
            for bottleneck in throughput['bottlenecks']:
                print(f"  ⚠ {bottleneck}")

        print("\n" + "="*80 + "\n")


def load_hardware_registry(inventory_path: Optional[Path] = None) -> HardwareRegistry:
    """
    Load hardware registry from default or specified path.

    Args:
        inventory_path: Path to hardware_inventory.yaml (default: data/hardware_inventory.yaml)

    Returns:
        HardwareRegistry instance
    """
    if inventory_path is None:
        # Default to data/hardware_inventory.yaml relative to project root
        project_root = Path(__file__).parent.parent.parent.parent
        inventory_path = project_root / "data" / "hardware_inventory.yaml"

    return HardwareRegistry(inventory_path=inventory_path)
