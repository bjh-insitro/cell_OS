# -*- coding: utf-8 -*-
"""Perturbation acquisition loop for POSH screens.

This loop operates at the gene/guide level, selecting which perturbations
to include in a POSH screen. It sits above the imaging dose loop.

Architecture:
- ImagingDoseLoop chooses the optimal stressor dose (Phase -1)
- PerturbationAcquisitionLoop chooses which genes/guides to screen (Phase 0)
- Together they define a complete POSH campaign
"""

from __future__ import annotations
from typing import Protocol, Optional, List
import pandas as pd
import numpy as np

from cell_os.perturbation_goal import (
    PerturbationGoal,
    PerturbationPlan,
    PerturbationBatch,
    PerturbationPosterior,
)
from cell_os.plate_constraints import PlateConstraints


class PerturbationExecutorLike(Protocol):
    """Protocol for perturbation executors.
    
    An executor takes a batch of perturbation plans and returns results
    (morphological features, viability, etc.).
    
    Future implementations:
    - SimulatedPerturbationExecutor: For testing
    - RealPerturbationExecutor: Integrates with lab automation
    """
    
    def run_batch(self, batch: PerturbationBatch) -> pd.DataFrame:
        """Execute a batch of perturbations and return results.
        
        Parameters
        ----------
        batch : PerturbationBatch
            Batch of perturbations to execute
        
        Returns
        -------
        results : pd.DataFrame
            Results with columns: gene, guide_id, replicate, morphology_features, viability
        """
        ...


class PerturbationAcquisitionLoop:
    """Autonomous loop for selecting perturbations in POSH screens.
    
    This loop proposes which genes and guides to include in a POSH screen,
    based on a goal (e.g., maximize phenotypic diversity) and constraints
    (e.g., plate capacity, budget).
    
    Workflow:
    1. propose() -> PerturbationBatch (which genes/guides to screen)
    2. executor.run_batch() -> results (morphological features)
    3. posterior.update_with_results() -> updated beliefs
    4. Repeat
    
    Parameters
    ----------
    posterior : PerturbationPosterior
        Belief about gene -> phenotype relationships
    executor : PerturbationExecutorLike
        Executor for running perturbation experiments
    goal : PerturbationGoal
        Goal defining what to optimize for
    
    Examples
    --------
    >>> posterior = PerturbationPosterior()
    >>> executor = SimulatedPerturbationExecutor()  # Future
    >>> goal = PerturbationGoal(objective="maximize_diversity", max_perturbations=200)
    >>> loop = PerturbationAcquisitionLoop(posterior, executor, goal)
    >>> batch = loop.propose(candidate_genes=["TP53", "MDM2", "ATM"])
    >>> results = loop.run_one_cycle(candidate_genes=["TP53", "MDM2", "ATM"])
    
    Notes
    -----
    This is a skeleton. Future implementation will:
    - Use morphological embeddings to predict phenotypic diversity
    - Integrate with guide design solver (existing gRNA code)
    - Optimize for information gain per dollar
    - Handle plate layout constraints (384-well)
    """
    
    def __init__(
        self,
        posterior: PerturbationPosterior,
        executor: PerturbationExecutorLike,
        goal: PerturbationGoal,
        plate_constraints: Optional[PlateConstraints] = None,
    ):
        """Initialize the perturbation acquisition loop.
        
        Parameters
        ----------
        plate_constraints : Optional[PlateConstraints]
            Physical plate constraints (default: 384-well with 16 controls)
        """
        self.posterior = posterior
        self.executor = executor
        self.goal = goal
        self.plate_constraints = plate_constraints or PlateConstraints()
    
    def propose(
        self,
        candidate_genes: List[str],
        candidate_guides: Optional[pd.DataFrame] = None,
    ) -> PerturbationBatch:
        """Propose a batch of perturbations to execute.
        
        Parameters
        ----------
        candidate_genes : List[str]
            List of candidate genes to consider
        candidate_guides : Optional[pd.DataFrame]
            Optional pre-designed guides (columns: gene, guide_seq, guide_id, score)
            If None, guides will be designed on-the-fly (future integration with gRNA solver)
        
        Returns
        -------
        batch : PerturbationBatch
            Proposed perturbations to execute
        
        Notes
        -----
        Phase 0.3+: Uses POSH pooled capacity for gene-level constraints.
        1. Score each gene by diversity
        2. Select top N genes (respecting POSH pooled capacity)
        3. For each gene, create placeholder guides
        4. Compute cost
        5. Return batch
        """
        # Compute max genes given POSH pooled capacity or goal limit
        goal_max = self.goal.effective_max_genes()
        
        # Also respect physical plate constraints
        plate_max = self.plate_constraints.max_perturbations(self.goal)
        
        max_genes = min(goal_max, plate_max)
        
        # Score each gene using diversity and phenotype scores
        # Use profile to weight diversity vs exploitation
        diversity_weight = self.goal.profile.diversity_weight
        
        scores = {}
        for gene in candidate_genes:
            # Diversity score (0-1, higher = more diverse from existing)
            diversity = self.posterior.diversity_score([gene])
            
            # Phenotype score (0-1, higher = more phenotypically interesting)
            # Use viability as proxy for phenotype (lower viability = more interesting)
            phenotype_score = self.posterior.phenotype_scores.get(gene, 0.5)
            # Invert so lower viability = higher score
            phenotype_score = 1.0 - phenotype_score
            
            # Weighted combination
            combined_score = (
                diversity_weight * diversity +
                (1.0 - diversity_weight) * phenotype_score
            )
            scores[gene] = combined_score
        
        # Select top N genes
        selected_genes = sorted(scores.keys(), key=lambda g: scores[g], reverse=True)[:max_genes]
        
        # Create plans
        plans = []
        total_cost = 0.0
        
        for gene in selected_genes:
            # Create placeholder guides
            n_guides = self.goal.min_guides_per_gene
            guides = [f"{gene}_guide_{i+1}" for i in range(n_guides)]
            guide_ids = [f"{gene}_g{i+1}" for i in range(n_guides)]
            
            # Simple cost model: $5 per guide per replicate
            cost_per_gene = n_guides * self.goal.min_replicates * 5.0
            total_cost += cost_per_gene
            
            plan = PerturbationPlan(
                gene=gene,
                guides=guides,
                guide_ids=guide_ids,
                replicates=self.goal.min_replicates,
            )
            plans.append(plan)
        
        # Compute expected diversity for the selected set
        if selected_genes:
            expected_diversity = self.posterior.diversity_score(list(selected_genes))
        else:
            expected_diversity = 0.0
        
        return PerturbationBatch(
            plans=plans,
            total_cost_usd=total_cost,
            expected_diversity=expected_diversity,
        )
    
    def run_one_cycle(
        self,
        candidate_genes: List[str],
        candidate_guides: Optional[pd.DataFrame] = None,
    ) -> PerturbationBatch:
        """Run one cycle: propose -> execute -> update.
        
        Parameters
        ----------
        candidate_genes : List[str]
            List of candidate genes to consider
        candidate_guides : Optional[pd.DataFrame]
            Optional pre-designed guides
        
        Returns
        -------
        batch : PerturbationBatch
            The batch that was executed
        
        Notes
        -----
        Phase 0.1: Full closed loop implementation.
        1. Call propose() to get batch
        2. Call executor.run_batch() to execute
        3. Call posterior.update_with_results() to learn
        4. Return the executed batch
        """
        # Propose
        batch = self.propose(candidate_genes, candidate_guides)
        
        # Execute
        results = self.executor.run_batch(batch)
        
        # Update posterior
        self.posterior.update_with_results(results)
        
        return batch
