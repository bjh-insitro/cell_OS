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


class POSHPooledCapacity:
    """Capacity model for pooled POSH screens.
    
    Parameters
    ----------
    cells_per_well : int
        Total cells in a single POSH imaging well at analysis time.
    iss_efficiency : float
        Fraction of cells with a successfully decoded barcode
        (e.g. 0.6 for A549 in our current model).
    min_cells_per_gene : int
        Minimum number of barcoded cells required per gene KO
        (across all guides for that gene), e.g. 1000.
    guides_per_gene : int
        Number of guides per gene in the library, e.g. 4.
    
    Examples
    --------
    >>> # A549 defaults
    >>> cap = POSHPooledCapacity(
    ...     cells_per_well=500_000,
    ...     iss_efficiency=0.60,
    ...     min_cells_per_gene=1000,
    ...     guides_per_gene=4,
    ... )
    >>> cap.effective_barcoded_cells
    300000
    >>> cap.max_genes
    300
    >>> cap.max_guides
    1200
    """
    
    def __init__(
        self,
        cells_per_well: int = 500_000,
        iss_efficiency: float = 0.60,
        min_cells_per_gene: int = 1000,
        guides_per_gene: int = 4,
    ):
        self.cells_per_well = cells_per_well
        self.iss_efficiency = iss_efficiency
        self.min_cells_per_gene = min_cells_per_gene
        self.guides_per_gene = guides_per_gene
    
    @property
    def effective_barcoded_cells(self) -> int:
        """Number of cells with a usable barcode."""
        return int(self.cells_per_well * self.iss_efficiency)
    
    @property
    def max_genes(self) -> int:
        """Maximum number of genes that can be robustly profiled in one POSH pool.
        
        Given the min_cells_per_gene requirement.
        """
        if self.min_cells_per_gene <= 0:
            return 0
        return self.effective_barcoded_cells // self.min_cells_per_gene
    
    @property
    def max_guides(self) -> int:
        """Maximum number of guide perturbations in the pool."""
        return self.max_genes * self.guides_per_gene


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
    posh_capacity: Optional[POSHPooledCapacity] = None
    
    def effective_max_genes(self) -> int:
        """Return the effective gene-level capacity for this goal.
        
        For POSH pooled screens, if posh_capacity is set, we use
        posh_capacity.max_genes. Otherwise fall back to max_perturbations
        as a simple gene-count limit.
        
        Returns
        -------
        max_genes : int
            Maximum number of genes to include
        
        Examples
        --------
        >>> # Without POSH capacity
        >>> goal = PerturbationGoal(max_perturbations=50)
        >>> goal.effective_max_genes()
        50
        
        >>> # With POSH capacity (A549 defaults)
        >>> cap = POSHPooledCapacity()
        >>> goal = PerturbationGoal(max_perturbations=50, posh_capacity=cap)
        >>> goal.effective_max_genes()
        300
        """
        if self.posh_capacity is not None:
            return self.posh_capacity.max_genes
        return self.max_perturbations


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
    
    def compute_pairwise_distance_matrix(self, embeddings: Dict[str, np.ndarray]) -> np.ndarray:
        """Compute pairwise cosine distance matrix for gene embeddings.
        
        Parameters
        ----------
        embeddings : Dict[str, np.ndarray]
            Dictionary mapping gene names to embedding vectors
        
        Returns
        -------
        distance_matrix : np.ndarray
            Pairwise cosine distance matrix (shape: n_genes × n_genes)
        
        Notes
        -----
        Cosine distance = 1 - cosine similarity
        Distance is 0 for identical vectors, 2 for opposite vectors.
        """
        if len(embeddings) == 0:
            return np.array([[]])
        
        genes = list(embeddings.keys())
        n_genes = len(genes)
        
        # Stack embeddings into matrix
        emb_matrix = np.array([embeddings[g] for g in genes])
        
        # Normalize to unit length
        norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
        emb_matrix = emb_matrix / (norms + 1e-9)
        
        # Compute cosine similarity matrix
        similarity = emb_matrix @ emb_matrix.T
        
        # Convert to distance
        distance = 1.0 - similarity
        
        return distance
    
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
        Phase 0.2: Uses cosine distance between morphological embeddings.
        - For genes with embeddings: compute pairwise cosine distance, average across pairs
        - For genes without embeddings: use placeholder vector (hash-based)
        - Normalize to [0, 1] range
        """
        if len(genes) == 0:
            return 0.0
        
        # Collect embeddings for genes that have them
        gene_embeddings = {}
        for gene in genes:
            if gene in self.embeddings:
                gene_embeddings[gene] = self.embeddings[gene]
            else:
                # Placeholder: hash-based vector for genes without embeddings
                gene_hash = sum(ord(c) for c in gene)
                rng = np.random.RandomState(gene_hash)
                placeholder = rng.randn(10)  # Assume 10-dim embeddings
                placeholder = placeholder / (np.linalg.norm(placeholder) + 1e-9)
                gene_embeddings[gene] = placeholder
        
        # Compute pairwise distances
        if len(gene_embeddings) == 1:
            # Single gene: no diversity
            return 0.0
        
        distance_matrix = self.compute_pairwise_distance_matrix(gene_embeddings)
        
        # Average pairwise distance (excluding diagonal)
        n = distance_matrix.shape[0]
        if n <= 1:
            return 0.0
        
        # Sum off-diagonal elements and divide by number of pairs
        total_distance = (distance_matrix.sum() - np.trace(distance_matrix)) / 2.0
        n_pairs = n * (n - 1) / 2.0
        avg_distance = total_distance / n_pairs if n_pairs > 0 else 0.0
        
        # Normalize to [0, 1] (max cosine distance is 2.0)
        score = avg_distance / 2.0
        
        return float(np.clip(score, 0.0, 1.0))
