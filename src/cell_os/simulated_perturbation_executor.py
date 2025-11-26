# -*- coding: utf-8 -*-
"""Simulated executor for perturbation experiments.

Generates synthetic morphological phenotypes for testing the perturbation loop.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict

from cell_os.perturbation_goal import PerturbationBatch, PerturbationPlan


class SimulatedPerturbationExecutor:
    """Simulated executor for perturbation experiments.
    
    Generates deterministic synthetic phenotypes based on gene names.
    Each gene gets a stable 10-dimensional morphological embedding.
    
    Parameters
    ----------
    embedding_dim : int
        Dimensionality of morphological embeddings (default: 10)
    base_viability : float
        Base viability for all perturbations (default: 0.95)
    viability_noise : float
        Noise added to viability (default: 0.05)
    seed : int
        Random seed for reproducibility (default: 42)
    inventory : Inventory, optional
        Inventory to track reagent consumption (default: None)
    
    Examples
    --------
    >>> executor = SimulatedPerturbationExecutor()
    >>> batch = PerturbationBatch(plans=[...])
    >>> results = executor.run_batch(batch)
    >>> results.columns
    Index(['gene', 'guide_id', 'replicate', 'viability', 'morphology_embedding'])
    """
    
    def __init__(
        self,
        embedding_dim: int = 10,
        base_viability: float = 0.95,
        viability_noise: float = 0.05,
        seed: int = 42,
        inventory=None,  # Optional[Inventory]
    ):
        """Initialize simulated executor."""
        self.embedding_dim = embedding_dim
        self.base_viability = base_viability
        self.viability_noise = viability_noise
        self.seed = seed
        self.inventory = inventory
    
    def _generate_gene_embedding(self, gene: str) -> np.ndarray:
        """Generate deterministic embedding for a gene.
        
        Uses gene name as seed for reproducibility.
        
        Parameters
        ----------
        gene : str
            Gene symbol
        
        Returns
        -------
        embedding : np.ndarray
            Morphological embedding (shape: embedding_dim)
        """
        # Use gene name to seed RNG for stable behavior
        gene_seed = sum(ord(c) for c in gene)
        rng = np.random.RandomState(self.seed + gene_seed)
        
        # Generate random embedding
        embedding = rng.randn(self.embedding_dim)
        
        # Normalize to unit length
        embedding = embedding / (np.linalg.norm(embedding) + 1e-9)
        
        return embedding
    
    def run_batch(self, batch: PerturbationBatch) -> pd.DataFrame:
        """Execute a batch of perturbations and return synthetic results.
        
        Parameters
        ----------
        batch : PerturbationBatch
            Batch of perturbations to execute
        
        Returns
        -------
        results : pd.DataFrame
            Synthetic results with columns:
            - gene: Gene symbol
            - guide_id: Guide identifier
            - replicate: Replicate number (1-indexed)
            - viability: Cell viability (0-1)
            - morphology_embedding: Morphological features (list of floats)
        
        Raises
        ------
        OutOfStockError
            If inventory tracking is enabled and reagents are depleted
        """
        # Consume inventory if tracking is enabled
        if self.inventory is not None:
            self._consume_reagents(batch)
        
        rows = []
        
        for plan in batch.plans:
            # Generate stable embedding for this gene
            gene_embedding = self._generate_gene_embedding(plan.gene)
            
            # Generate results for each guide and replicate
            for guide_id in plan.guide_ids:
                for rep in range(1, plan.replicates + 1):
                    # Viability with small noise
                    rng = np.random.RandomState(
                        self.seed + sum(ord(c) for c in guide_id) + rep
                    )
                    viability = self.base_viability + rng.randn() * self.viability_noise
                    viability = np.clip(viability, 0.0, 1.0)
                    
                    # Morphology is gene-specific (same for all guides/replicates of that gene)
                    rows.append({
                        'gene': plan.gene,
                        'guide_id': guide_id,
                        'replicate': rep,
                        'viability': viability,
                        'morphology_embedding': gene_embedding.tolist(),
                    })
        
        return pd.DataFrame(rows)
    
    def _consume_reagents(self, batch: PerturbationBatch):
        """Consume reagents from inventory for a batch.
        
        Parameters
        ----------
        batch : PerturbationBatch
            Batch to consume reagents for
        
        Raises
        ------
        OutOfStockError
            If insufficient reagents available
        """
        # Calculate total wells needed
        total_wells = sum(
            len(plan.guide_ids) * plan.replicates 
            for plan in batch.plans
        )
        
        # Consume plates (assume 6-well plates, 1 plate per 6 wells)
        plates_needed = np.ceil(total_wells / 6.0)
        self.inventory.consume("PLATE_6WELL", plates_needed, "plate")
        
        # Consume media (assume 2 mL per well for 6-well plates)
        media_ml = total_wells * 2.0  # 2 mL per well
        self.inventory.consume("DMEM_MEDIA", media_ml, "mL")
        
        # Consume FBS (10% of media volume)
        fbs_ml = media_ml * 0.1
        self.inventory.consume("FBS", fbs_ml, "mL")
