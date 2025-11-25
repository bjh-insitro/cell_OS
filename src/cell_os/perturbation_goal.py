# -*- coding: utf-8 -*-
"""Perturbation-level data structures for POSH screens.

Defines goals, plans, and posteriors for selecting which genes/guides to perturb
in a POSH screen. This layer sits above the imaging dose loop.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import pandas as pd
import numpy as np


@dataclass
class PerturbationGoal:
    """Goal for perturbation selection in a POSH screen.
    
    Defines what the perturbation acquisition loop should optimize for when
    selecting genes and guides for a POSH screen.
    
    Attributes
    ----------
    objective : str
        Primary objective: "maximize_diversity", "target_pathway", "explore_hits"
    target_genes : Optional[List[str]]
        Optional list of genes to prioritize (e.g., for pathway targeting)
    min_guides_per_gene : int
        Minimum number of guides per gene (for redundancy)
    max_guides_per_gene : int
        Maximum number of guides per gene (for cost control)
    min_replicates : int
        Minimum number of replicate wells per perturbation
    max_perturbations : int
        Maximum number of perturbations (plate capacity constraint)
    budget_usd : Optional[float]
        Optional budget constraint
    
    Examples
    --------
    >>> goal = PerturbationGoal(
    ...     objective="maximize_diversity",
    ...     min_guides_per_gene=3,
    ...     max_perturbations=200,
    ... )
    """
    
    objective: str = "maximize_diversity"
    target_genes: Optional[List[str]] = None
    min_guides_per_gene: int = 3
    max_guides_per_gene: int = 5
    min_replicates: int = 2
    max_perturbations: int = 200
    budget_usd: Optional[float] = None


@dataclass
class PerturbationPlan:
    """A single proposed perturbation for a POSH screen.
    
    Represents one gene with its selected guides, ready to be executed.
    
    Attributes
    ----------
    gene : str
        Gene symbol (e.g., "TP53")
    guides : List[str]
        List of guide sequences to use for this gene
    guide_ids : List[str]
        List of guide IDs (for tracking)
    replicates : int
        Number of replicate wells
    expected_phenotype_score : float
        Expected phenotypic diversity score (higher = more informative)
    notes : str
        Optional notes (e.g., "known stress pathway gene")
    
    Examples
    --------
    >>> plan = PerturbationPlan(
    ...     gene="TP53",
    ...     guides=["GACTCCAGTGGTAATCTAC", "CAGCACATGACGGAGGTTG"],
    ...     guide_ids=["TP53_g1", "TP53_g2"],
    ...     replicates=3,
    ...     expected_phenotype_score=0.85,
    ... )
    """
    
    gene: str
    guides: List[str]
    guide_ids: List[str]
    replicates: int = 2
    expected_phenotype_score: float = 0.0
    notes: str = ""


@dataclass
class PerturbationBatch:
    """A batch of perturbations proposed for a POSH screen.
    
    Attributes
    ----------
    plans : List[PerturbationPlan]
        List of perturbations to execute
    total_cost_usd : float
        Estimated total cost for this batch
    expected_diversity : float
        Expected phenotypic diversity across the batch
    """
    
    plans: List[PerturbationPlan] = field(default_factory=list)
    total_cost_usd: float = 0.0
    expected_diversity: float = 0.0


class PerturbationPosterior:
    """Posterior belief about gene -> phenotype relationships.
    
    This will eventually store:
    - Morphological embeddings per gene
    - Phenotypic similarity matrices
    - Hit probabilities
    - Pathway enrichment scores
    
    For now, this is a placeholder for future morphology integration.
    
    Future API
    ----------
    - `update_with_posh_results(df: pd.DataFrame)`: Update posterior with POSH data
    - `predict_phenotype(gene: str) -> np.ndarray`: Predict morphological embedding
    - `get_diversity_score(genes: List[str]) -> float`: Score phenotypic diversity
    - `rank_genes_by_informativeness() -> List[str]`: Rank genes by expected info gain
    
    Examples
    --------
    >>> posterior = PerturbationPosterior()
    >>> # Future: posterior.update_with_posh_results(posh_df)
    >>> # Future: diversity = posterior.get_diversity_score(["TP53", "MDM2"])
    """
    
    def __init__(self):
        """Initialize empty posterior."""
        self.history: List[Dict] = []  # Future: POSH results
        self.embeddings: Dict[str, any] = {}  # Future: morphological embeddings
        self.phenotype_scores: Dict[str, float] = {}  # Future: phenotype scores
    
    def update_with_results(self, results: pd.DataFrame) -> None:
        """Update posterior with perturbation screen results.
        
        Parameters
        ----------
        results : pd.DataFrame
            Results from executor with columns: gene, guide_id, replicate, viability, morphology_embedding
        
        Notes
        -----
        For now, just stores results in history and updates embeddings dict.
        Future: compute similarity matrices, refit models, etc.
        """
        self.history.append(results)
        
        # Extract embeddings per gene
        for gene in results['gene'].unique():
            gene_data = results[results['gene'] == gene]
            # Average embeddings across replicates
            embeddings = np.array([e for e in gene_data['morphology_embedding'].values])
            self.embeddings[gene] = embeddings.mean(axis=0)
            
            # Store average viability as phenotype score
            self.phenotype_scores[gene] = gene_data['viability'].mean()
    
    def get_diversity_score(self, genes: List[str]) -> float:
        """Compute expected phenotypic diversity for a gene set.
        
        Parameters
        ----------
        genes : List[str]
            List of genes to score
        
        Returns
        -------
        diversity : float
            Expected phenotypic diversity (0-1, higher = more diverse)
        
        Notes
        -----
        Simple heuristic: use gene name hash as diversity score.
        Future: use morphological embeddings to compute real diversity.
        """
        if len(genes) == 0:
            return 0.0
        
        # Simple heuristic: hash gene name to get stable score
        # This gives different genes different scores deterministically
        gene_hash = sum(ord(c) for c in genes[0])
        score = (gene_hash % 100) / 100.0  # 0-1 range
        
        return score
