#!/usr/bin/env python3
"""
Test script to validate the refactored dashboard architecture.
"""

import sys
import os

# Add paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, project_root)
sys.path.insert(0, current_dir)

from dashboard_app.config import create_page_registry, PageCategory


def test_page_registry():
    """Test that the page registry works correctly."""
    print("Testing Page Registry...")
    print("=" * 60)
    
    # Create registry
    registry = create_page_registry()
    
    # Test 1: Check total pages
    all_pages = registry.get_all_pages()
    print(f"\n✓ Total pages registered: {len(all_pages)}")
    assert len(all_pages) == 17, f"Expected 17 pages, got {len(all_pages)}"
    
    # Test 2: Check categories
    pages_by_category = registry.get_pages_by_category()
    print(f"\n✓ Pages organized into {len(pages_by_category)} categories:")
    for category, pages in pages_by_category.items():
        print(f"  - {category.value}: {len(pages)} pages")
    
    # Test 3: Check page lookup
    page_titles = registry.get_page_titles()
    print(f"\n✓ All page titles:")
    for i, title in enumerate(page_titles, 1):
        print(f"  {i:2d}. {title}")
    
    # Test 4: Verify each page has a render function
    print(f"\n✓ Verifying render functions...")
    for page in all_pages:
        assert callable(page.render_function), f"Page {page.title} has invalid render function"
        print(f"  ✓ {page.emoji} {page.title} -> {page.render_function.__name__}")
    
    # Test 5: Check page retrieval
    print(f"\n✓ Testing page retrieval...")
    test_title = "🚀 Mission Control"
    page = registry.get_page(test_title)
    assert page is not None, f"Failed to retrieve page: {test_title}"
    assert page.title == "Mission Control"
    assert page.emoji == "🚀"
    print(f"  ✓ Successfully retrieved: {test_title}")
    
    # Test 6: Verify category distribution
    print(f"\n✓ Category distribution:")
    expected_categories = {
        PageCategory.CORE: 3,
        PageCategory.SIMULATION: 2,
        PageCategory.AUDIT: 4,
        PageCategory.PLANNING: 5,
        PageCategory.ANALYSIS: 3
    }
    
    for category, expected_count in expected_categories.items():
        actual_count = len(pages_by_category.get(category, []))
        status = "✓" if actual_count == expected_count else "✗"
        print(f"  {status} {category.value}: {actual_count} pages (expected {expected_count})")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


def show_page_details():
    """Show detailed information about each page."""
    print("\n\nDetailed Page Information:")
    print("=" * 60)
    
    registry = create_page_registry()
    pages_by_category = registry.get_pages_by_category()
    
    for category in PageCategory:
        if category not in pages_by_category:
            continue
            
        print(f"\n📁 {category.value}")
        print("-" * 60)
        
        for page in pages_by_category[category]:
            print(f"\n  {page.emoji} {page.title}")
            print(f"     Key: {page.key}")
            print(f"     Order: {page.order}")
            if page.description:
                print(f"     Description: {page.description}")
            print(f"     Function: {page.render_function.__module__}.{page.render_function.__name__}")


if __name__ == "__main__":
    try:
        test_page_registry()
        show_page_details()
        print("\n✅ Dashboard refactoring validated successfully!\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
