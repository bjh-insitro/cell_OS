#!/usr/bin/env python3
"""
Hardware Inventory Manager

Interactive CLI tool to manage lab hardware inventory.

Usage:
    python scripts/inventory_manager.py summary
    python scripts/inventory_manager.py list liquid_handlers
    python scripts/inventory_manager.py capabilities
    python scripts/inventory_manager.py check-feasibility phase0
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cell_os.lab_world_model import load_hardware_registry


def cmd_summary(args):
    """Print inventory summary"""
    registry = load_hardware_registry()
    registry.print_summary()


def cmd_list(args):
    """List hardware by category"""
    registry = load_hardware_registry()

    if args.category:
        items = registry.get_by_category(args.category)
        print(f"\n{args.category.upper().replace('_', ' ')}:")
        print("-" * 80)

        if not items:
            print("  (none)")
        else:
            for hw in items:
                status_symbol = "✓" if hw.status == "operational" else "✗"
                print(f"  {status_symbol} {hw.id}")
                print(f"     {hw.manufacturer} {hw.model}")
                print(f"     Status: {hw.status}")
                if hw.location:
                    print(f"     Location: {hw.location}")
                print()
    else:
        # List all categories
        all_hw = registry.get_all_hardware()
        categories = sorted(set(hw.category for hw in all_hw))

        for cat in categories:
            items = registry.get_by_category(cat)
            print(f"\n{cat.upper().replace('_', ' ')} ({len(items)}):")
            for hw in items:
                status_symbol = "✓" if hw.status == "operational" else "✗"
                print(f"  {status_symbol} {hw.id} - {hw.manufacturer} {hw.model}")


def cmd_capabilities(args):
    """Check lab capabilities"""
    registry = load_hardware_registry()

    print("\n" + "="*80)
    print("LAB CAPABILITIES CHECK")
    print("="*80 + "\n")

    checks = [
        ("Liquid Handling", registry.can_perform_liquid_handling()),
        ("High-Content Imaging (5+ channels)", registry.can_perform_imaging(5)),
        ("Cell Painting (5-channel)", registry.can_perform_cell_painting()),
        ("ATP Assay (Luminescence)", registry.can_perform_atp_assay()),
    ]

    for name, available in checks:
        status = "✓ AVAILABLE" if available else "✗ NOT AVAILABLE"
        print(f"{name:<40} {status}")

    print()


def cmd_cell_lines(args):
    """List available cell lines"""
    registry = load_hardware_registry()
    cell_lines = registry.get_cell_lines()

    print("\n" + "="*80)
    print("AVAILABLE CELL LINES")
    print("="*80 + "\n")

    if not cell_lines:
        print("  (none)")
    else:
        for cl in cell_lines:
            print(f"  • {cl['name']} ({cl['tissue']})")
            print(f"    Passage: {cl.get('passage_number', 'N/A')}")
            print(f"    Vials: {cl.get('vials_available', 0)}")
            print(f"    Location: {cl.get('location', 'N/A')}")
            if cl.get('notes'):
                print(f"    Notes: {cl['notes']}")
            print()


def cmd_compounds(args):
    """List available compounds"""
    registry = load_hardware_registry()
    libraries = registry.get_compound_libraries()

    print("\n" + "="*80)
    print("COMPOUND LIBRARIES")
    print("="*80 + "\n")

    if not libraries:
        print("  (none)")
    else:
        for lib in libraries:
            print(f"  Library: {lib['library_id']}")
            print(f"  Description: {lib.get('description', 'N/A')}")
            print(f"  Location: {lib.get('storage_location', 'N/A')}")
            print(f"  Format: {lib.get('format', 'N/A')}")
            print(f"  Compounds ({len(lib.get('compounds', []))}):")

            for comp in lib.get('compounds', []):
                print(f"    • {comp['name']} - {comp.get('target_pathway', 'N/A')}")

            print()


def cmd_feasibility(args):
    """Check experimental feasibility"""
    registry = load_hardware_registry()

    print("\n" + "="*80)
    print("EXPERIMENTAL FEASIBILITY CHECK")
    print("="*80 + "\n")

    if args.design_type:
        print(f"Design Type: {args.design_type}\n")

    throughput = registry.estimate_throughput(args.design_type or "phase0")

    print("Estimated Throughput:")
    print(f"  Automation Level: {throughput['automation_level']}")
    print(f"  Plates/Day: {throughput['plates_per_day']}")
    print(f"  Operator Hours/Day: {throughput['operator_hours_per_day']}")
    print()

    if throughput['bottlenecks']:
        print("⚠ Bottlenecks:")
        for bottleneck in throughput['bottlenecks']:
            print(f"  • {bottleneck}")
        print()

    # Additional checks
    print("Required Capabilities:")
    capabilities = [
        ("Liquid handling", registry.can_perform_liquid_handling()),
        ("5-channel imaging", registry.can_perform_imaging(5)),
        ("ATP assay", registry.can_perform_atp_assay()),
    ]

    all_met = True
    for name, available in capabilities:
        status = "✓" if available else "✗"
        print(f"  {status} {name}")
        if not available:
            all_met = False

    print()

    if all_met:
        print("✓ All required capabilities are available!")
    else:
        print("✗ Some required capabilities are missing.")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Hardware Inventory Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/inventory_manager.py summary
  python scripts/inventory_manager.py list liquid_handlers
  python scripts/inventory_manager.py capabilities
  python scripts/inventory_manager.py cell-lines
  python scripts/inventory_manager.py compounds
  python scripts/inventory_manager.py feasibility phase0
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Summary command
    subparsers.add_parser('summary', help='Print inventory summary')

    # List command
    list_parser = subparsers.add_parser('list', help='List hardware by category')
    list_parser.add_argument('category', nargs='?', help='Hardware category to list')

    # Capabilities command
    subparsers.add_parser('capabilities', help='Check lab capabilities')

    # Cell lines command
    subparsers.add_parser('cell-lines', help='List available cell lines')

    # Compounds command
    subparsers.add_parser('compounds', help='List compound libraries')

    # Feasibility command
    feasibility_parser = subparsers.add_parser('feasibility', help='Check experimental feasibility')
    feasibility_parser.add_argument('design_type', nargs='?', default='phase0',
                                   help='Design type (phase0, phase1, etc.)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to appropriate command
    commands = {
        'summary': cmd_summary,
        'list': cmd_list,
        'capabilities': cmd_capabilities,
        'cell-lines': cmd_cell_lines,
        'compounds': cmd_compounds,
        'feasibility': cmd_feasibility,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


if __name__ == '__main__':
    main()
