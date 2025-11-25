"""
upstream.py

Models the "Genetic Supply Chain" - the upstream processes required to create
the physical biological materials for a screen.

Includes:
- Library Design (Gene selection, gRNA picking)
- Oligo Synthesis specifications
- Plasmid Construction
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import math

@dataclass
class GeneTarget:
    symbol: str
    entrez_id: Optional[str] = None
    tier: str = "primary" # primary, control, exploratory

@dataclass
class GuideRNA:
    sequence: str
    target_gene: str
    off_target_score: float = 100.0
    on_target_score: float = 100.0
    is_control: bool = False

@dataclass
class LibraryDesign:
    design_id: str
    genes: List[GeneTarget]
    guides_per_gene: int = 4
    controls_per_plate: int = 10
    use_solver: bool = False  # Enable constraint-based solver
    repositories_yaml: Optional[str] = None  # Path to sgRNA repo config
    
    def total_guides(self) -> int:
        return (len(self.genes) * self.guides_per_gene) + self.controls_per_plate

    def generate_guides(self) -> List[GuideRNA]:
        """
        Generate gRNA sequences.
        
        If use_solver=True, uses the constraint-based guide_design_v2 tool.
        Otherwise, uses mock implementation.
        """
        if self.use_solver:
            return self._generate_with_solver()
        else:
            return self._generate_mock()
    
    def _generate_with_solver(self) -> List[GuideRNA]:
        """
        Generate guides using constraint-based solver.
        """
        try:
            from cell_os.guide_design_v2 import GuideLibraryAdapter, GuideDesignConfig
            
            config = GuideDesignConfig(
                min_guides_per_gene=1,
                max_guides_per_gene=self.guides_per_gene,
                repositories=["vbc", "crispick"]
            )
            
            # Use default repositories_yaml if not provided
            repos_yaml = self.repositories_yaml
            if repos_yaml is None:
                repos_yaml = "data/configs/sgRNA_repositories.yaml"
            
            adapter = GuideLibraryAdapter(
                config=config,
                repositories_yaml=repos_yaml,
                verbose=True
            )
            
            # Design library
            library_df = adapter.design_library(self.genes)
            
            # Convert to GuideRNA objects
            guides = adapter.to_guide_rnas(library_df)
            
            # Add controls if needed
            n_controls_needed = self.controls_per_plate
            if n_controls_needed > 0:
                guides.extend(self._generate_mock_controls(n_controls_needed))
            
            return guides
            
        except Exception as e:
            print(f"[LibraryDesign] Solver failed: {e}")
            print("[LibraryDesign] Falling back to mock implementation")
            return self._generate_mock()
    
    def _generate_mock(self) -> List[GuideRNA]:
        """
        Mock function to generate gRNA sequences.
        In a real system, this would query a database (e.g., Brunello, Dolcetto).
        """
        guides = []
        for gene in self.genes:
            for i in range(self.guides_per_gene):
                guides.append(GuideRNA(
                    sequence=f"G{gene.symbol}SEQ{i+1}",
                    target_gene=gene.symbol,
                    on_target_score=95.0,
                    off_target_score=98.0
                ))
        
        # Add controls
        guides.extend(self._generate_mock_controls(self.controls_per_plate))
            
        return guides
    
    def _generate_mock_controls(self, n: int) -> List[GuideRNA]:
        """Generate mock non-targeting controls."""
        controls = []
        for i in range(n):
            controls.append(GuideRNA(
                sequence=f"NTC_SEQ{i+1}",
                target_gene="NTC",
                is_control=True
            ))
        return controls

@dataclass
class OligoPool:
    design: LibraryDesign
    vendor: str = "Twist Bioscience"
    synthesis_scale: str = "10ug"
    
    @property
    def cost_usd(self) -> float:
        """
        Calculate cost based on pool size and vendor.
        """
        n_guides = self.design.total_guides()
        
        if self.vendor == "Twist Bioscience":
            # Twist pricing model (Mock)
            # < 12k oligos: Flat rate ~$1500
            # > 12k: Custom
            if n_guides <= 12000:
                return 1500.0
            else:
                return 1500.0 + (n_guides - 12000) * 0.10
        elif self.vendor == "GenScript":
            if n_guides <= 12000:
                return 1800.0
            else:
                return 1800.0 + (n_guides - 12000) * 0.12
        else:
            return 2000.0 # Generic fallback

@dataclass
class PlasmidLibrary:
    oligo_pool: OligoPool
    backbone: str = "pLenti-Guide-Puro"
    cloning_method: str = "Golden Gate"
    
    def complexity_check(self) -> bool:
        """
        Check if library complexity is sufficient.
        """
        # Mock check
        return True
