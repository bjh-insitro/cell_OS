"""
guide_design_v2.py

Adapter for the existing constraint-based guide_design_v2 tool.
Integrates external solver-based gRNA library design into cell_OS workflow.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any
import tempfile
import yaml
import pandas as pd

from src.upstream import GuideRNA, GeneTarget


@dataclass
class GuideDesignConfig:
    """Configuration for guide_design_v2 solver."""
    
    posh_barcode_hamming_distance: int = 2
    posh_barcode_length: int = 13
    min_guides_per_gene: int = 1
    max_guides_per_gene: int = 4
    overlap_threshold: int = 6
    score_name: str = "rs3_sequence_score"
    solver_time_limit_seconds: int = 28800
    repositories: List[str] = field(default_factory=lambda: ["vbc", "crispick"])
    gene_list_path: Optional[str] = None


class GuideLibraryAdapter:
    """
    Adapter to integrate external guide_design_v2 tool with cell_OS.
    
    This class wraps the constraint-based solver and translates between
    cell_OS data structures and the external tool's interface.
    """
    
    def __init__(
        self,
        config: GuideDesignConfig,
        repositories_yaml: Optional[str] = None,
        verbose: bool = False
    ):
        """
        Initialize the adapter.
        
        Args:
            config: Guide design configuration
            repositories_yaml: Path to sgRNA repository config file
            verbose: Whether to print solver output
        """
        self.config = config
        self.repositories_yaml = repositories_yaml
        self.verbose = verbose
        
        # Check if external tool is available
        self._check_external_tool()
    
    def _check_external_tool(self) -> None:
        """Check if ml_projects.posh.guide_design_v2 is available."""
        try:
            from ml_projects.posh.guide_design_v2 import create_library
            self.create_library = create_library
            self._tool_available = True
        except ImportError:
            self._tool_available = False
            print(
                "[GuideLibraryAdapter] WARNING: ml_projects.posh.guide_design_v2 not found. "
                "Will fall back to mock implementation."
            )
    
    def design_library(
        self,
        genes: List[GeneTarget],
        output_path: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Design a gRNA library for the given gene list.
        
        Args:
            genes: List of gene targets
            output_path: Optional path to save output CSV
            
        Returns:
            DataFrame with designed library
        """
        if not self._tool_available:
            return self._mock_design(genes)
        
        # Create temporary gene list file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            gene_list_path = f.name
            f.write("gene_symbol\n")
            for gene in genes:
                f.write(f"{gene.symbol}\n")
        
        # Create temporary config file
        config_dict = {
            'posh_barcode_hamming_distance': self.config.posh_barcode_hamming_distance,
            'posh_barcode_length': self.config.posh_barcode_length,
            'min_guides_per_gene': self.config.min_guides_per_gene,
            'max_guides_per_gene': self.config.max_guides_per_gene,
            'overlap_threshold': self.config.overlap_threshold,
            'score_name': self.config.score_name,
            'solver_time_limit_seconds': self.config.solver_time_limit_seconds,
            'repositories': self.config.repositories,
            'gene_list': gene_list_path
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_yaml_path = f.name
            yaml.dump(config_dict, f)
        
        try:
            # Call external tool
            library_df = self.create_library.run(
                config_yaml_path,
                self.repositories_yaml,
                verbose=self.verbose
            )
            
            # Optionally save output
            if output_path is not None:
                library_df.to_csv(output_path, index=False)
            
            return library_df
            
        finally:
            # Cleanup temp files
            Path(gene_list_path).unlink(missing_ok=True)
            Path(config_yaml_path).unlink(missing_ok=True)
    
    def _mock_design(self, genes: List[GeneTarget]) -> pd.DataFrame:
        """
        Fallback mock implementation when external tool is unavailable.
        """
        rows = []
        for gene in genes:
            for i in range(self.config.max_guides_per_gene):
                rows.append({
                    'gene_symbol': gene.symbol,
                    'guide_sequence': f"G{gene.symbol}MOCK{i+1:02d}",
                    'pam_site': 'NGG',
                    'score': 95.0 - i * 2,  # Decreasing scores
                    'repository': 'mock'
                })
        return pd.DataFrame(rows)
    
    def to_guide_rnas(self, library_df: pd.DataFrame) -> List[GuideRNA]:
        """
        Convert library DataFrame to List[GuideRNA].
        
        Args:
            library_df: DataFrame from design_library()
            
        Returns:
            List of GuideRNA objects
        """
        guides = []
        
        for _, row in library_df.iterrows():
            # Map repository-specific score column to on_target_score
            score_col = self.config.score_name
            if score_col in row:
                on_target = float(row[score_col])
            elif 'score' in row:
                on_target = float(row['score'])
            else:
                on_target = 100.0
            
            guide = GuideRNA(
                sequence=row['guide_sequence'],
                target_gene=row['gene_symbol'],
                on_target_score=on_target,
                off_target_score=100.0,  # Not provided by solver output
                is_control=row.get('is_control', False)
            )
            guides.append(guide)
        
        return guides


def create_default_repositories_yaml(output_path: str) -> None:
    """
    Create a template sgRNA repositories config file.
    
    Args:
        output_path: Where to save the YAML file
    """
    template = {
        'vbc': 's3://insitro-posh-production/guide_repository/tech-dev/vbc_rs3_scored_w_location.csv',
        'crispick': 's3://insitro-posh-production/guide_repository/tech-dev/crispick_rs3_scored_w_location.csv',
    }
    
    with open(output_path, 'w') as f:
        yaml.dump(template, f, default_flow_style=False)
        f.write("\n# Add custom sgRNA repositories here\n")
        f.write("# my_repo: path/to/custom_library.csv\n")
