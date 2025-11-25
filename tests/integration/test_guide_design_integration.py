"""
Integration test for guide_design_v2 solver integration.

Tests the adapter layer that connects cell_OS LibraryDesign with the
external constraint-based solver.
"""

import os


from cell_os.upstream import LibraryDesign, GeneTarget


def test_mock_design():
    """Test mock design (fallback when solver unavailable)."""
    print("Testing mock design...")
    
    lib = LibraryDesign(
        design_id="test_mock",
        genes=[GeneTarget("BRCA1"), GeneTarget("TP53")],
        guides_per_gene=4,
        use_solver=False  # Explicitly use mock
    )
    
    guides = lib.generate_guides()
    
    # Should have 8 gene guides + 10 controls = 18
    assert len(guides) == 18, f"Expected 18 guides, got {len(guides)}"
    
    # Check gene-targeting guides
    gene_guides = [g for g in guides if not g.is_control]
    assert len(gene_guides) == 8
    assert all(g.target_gene in ["BRCA1", "TP53"] for g in gene_guides)
    
    # Check controls
    controls = [g for g in guides if g.is_control]
    assert len(controls) == 10
    assert all(g.target_gene == "NTC" for g in controls)
    
    print("✓ Mock design test passed")


def test_solver_design_fallback():
    """
    Test solver design with expected fallback to mock.
    
    This will likely fallback since ml_projects.posh.guide_design_v2
    is not installed in this environment.
    """
    print("\nTesting solver design (with expected fallback)...")
    
    lib = LibraryDesign(
        design_id="test_solver",
        genes=[GeneTarget("BRCA1"), GeneTarget("TP53"), GeneTarget("KRAS")],
        guides_per_gene=4,
        use_solver=True  # Try to use solver
    )
    
    guides = lib.generate_guides()
    
    # Should still return guides via fallback
    assert len(guides) >= 12, f"Expected at least 12 guides, got {len(guides)}"
    
    print(f"✓ Solver design test passed (returned {len(guides)} guides)")
    
    # Show what we got
    print("\nSample guides:")
    for i, guide in enumerate(guides[:5]):
        print(f"  {i+1}. {guide.target_gene}: {guide.sequence} (score: {guide.on_target_score:.1f})")


def test_adapter_import():
    """Test that guide_design_v2 module imports correctly."""
    print("\nTesting adapter module import...")
    
    try:
        from cell_os.guide_design_v2 import GuideLibraryAdapter, GuideDesignConfig
        print("✓ Adapter module imported successfully")
        
        # Test config creation
        config = GuideDesignConfig(
            min_guides_per_gene=1,
            max_guides_per_gene=4
        )
        assert config.min_guides_per_gene == 1
        assert config.max_guides_per_gene == 4
        print("✓ GuideDesignConfig created successfully")
        
    except Exception as e:
        print(f"✗ Adapter import failed: {e}")
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("Guide Design Integration Tests")
    print("=" * 60)
    
    test_adapter_import()
    test_mock_design()
    test_solver_design_fallback()
    
    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
