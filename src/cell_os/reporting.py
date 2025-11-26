# -*- coding: utf-8 -*-
"""Campaign reporting and summary generation.

Provides human-readable summaries of campaign execution including budget,
inventory usage, experimental coverage, and morphology metrics.
"""

from __future__ import annotations
from typing import Dict, List, Optional
import numpy as np
import pandas as pd


def summarize_campaign(
    campaign,
    inventory,
    results: Optional[pd.DataFrame] = None,
    initial_inventory: Optional[Dict[str, float]] = None,
    termination_reason: str = "completed",
) -> str:
    """Generate a human-readable campaign summary.
    
    Parameters
    ----------
    campaign : Campaign
        Campaign object
    inventory : Inventory
        Inventory object
    results : pd.DataFrame, optional
        Experimental results DataFrame
    initial_inventory : Dict[str, float], optional
        Initial stock levels (resource_id -> quantity)
    termination_reason : str
        Reason for campaign termination
    
    Returns
    -------
    summary : str
        Formatted summary report
    
    Examples
    --------
    >>> summary = summarize_campaign(campaign, inventory, results)
    >>> print(summary)
    """
    lines = []
    lines.append("=" * 70)
    lines.append("CAMPAIGN SUMMARY REPORT")
    lines.append("=" * 70)
    lines.append("")
    
    # Budget section
    lines.append("BUDGET")
    lines.append("-" * 70)
    if campaign.budget_total_usd == float('inf'):
        lines.append(f"  Total Budget:      Unlimited")
        lines.append(f"  Spent:             ${campaign.budget_spent_usd:,.2f}")
    else:
        pct_used = 100 * campaign.budget_spent_usd / campaign.budget_total_usd
        lines.append(f"  Total Budget:      ${campaign.budget_total_usd:,.2f}")
        lines.append(f"  Spent:             ${campaign.budget_spent_usd:,.2f} ({pct_used:.1f}%)")
        lines.append(f"  Remaining:         ${campaign.budget_remaining_usd:,.2f}")
    lines.append("")
    
    # Inventory section
    lines.append("INVENTORY USAGE")
    lines.append("-" * 70)
    
    tracked_resources = ["PLATE_6WELL", "DMEM_MEDIA", "FBS"]
    for resource_id in tracked_resources:
        try:
            current = inventory.check_stock(resource_id)
            resource = inventory.get_resource(resource_id)
            
            if initial_inventory and resource_id in initial_inventory:
                initial = initial_inventory[resource_id]
                consumed = initial - current
                pct_consumed = 100 * consumed / initial if initial > 0 else 0
                
                lines.append(f"  {resource.name}:")
                lines.append(f"    Starting:  {initial:,.1f} {resource.logical_unit}")
                lines.append(f"    Consumed:  {consumed:,.1f} {resource.logical_unit} ({pct_consumed:.1f}%)")
                lines.append(f"    Remaining: {current:,.1f} {resource.logical_unit}")
            else:
                lines.append(f"  {resource.name}:")
                lines.append(f"    Current:   {current:,.1f} {resource.logical_unit}")
        except KeyError:
            pass
    lines.append("")
    
    # Experimental coverage section
    lines.append("EXPERIMENTAL COVERAGE")
    lines.append("-" * 70)
    
    if results is not None and len(results) > 0:
        n_perturbations = results['gene'].nunique() if 'gene' in results.columns else 0
        n_total_wells = len(results)
        
        lines.append(f"  Perturbations:     {n_perturbations}")
        lines.append(f"  Total Wells:       {n_total_wells}")
        
        # Unique conditions
        if all(col in results.columns for col in ['gene', 'guide_id']):
            n_unique = results[['gene', 'guide_id']].drop_duplicates().shape[0]
            lines.append(f"  Unique Conditions: {n_unique}")
    else:
        lines.append(f"  No experimental results available")
    lines.append("")
    
    # Morphology section
    lines.append("MORPHOLOGY")
    lines.append("-" * 70)
    
    if results is not None and 'morphology_embedding' in results.columns:
        n_embeddings = len(results)
        lines.append(f"  Embeddings:        {n_embeddings}")
        
        # Calculate diversity metric (mean pairwise distance)
        try:
            embeddings = np.vstack(results['morphology_embedding'].values)
            if len(embeddings) > 1:
                # Sample for efficiency if too many
                if len(embeddings) > 100:
                    idx = np.random.choice(len(embeddings), 100, replace=False)
                    embeddings = embeddings[idx]
                
                # Compute pairwise distances
                from scipy.spatial.distance import pdist
                distances = pdist(embeddings, metric='euclidean')
                mean_dist = np.mean(distances)
                std_dist = np.std(distances)
                
                lines.append(f"  Mean Pairwise Dist: {mean_dist:.3f} ± {std_dist:.3f}")
            else:
                lines.append(f"  Mean Pairwise Dist: N/A (single embedding)")
        except Exception as e:
            lines.append(f"  Diversity:         Error computing ({str(e)})")
    else:
        lines.append(f"  No morphology data available")
    lines.append("")
    
    # Termination section
    lines.append("TERMINATION")
    lines.append("-" * 70)
    lines.append(f"  Status:            {termination_reason}")
    lines.append(f"  Cycles Completed:  {campaign.current_cycle} / {campaign.max_cycles}")
    if campaign.success:
        lines.append(f"  Goal Met:          Yes")
    else:
        lines.append(f"  Goal Met:          No")
    lines.append("")
    
    lines.append("=" * 70)
    
    return "\n".join(lines)


def compute_morphology_diversity(embeddings: np.ndarray, sample_size: int = 100) -> Dict[str, float]:
    """Compute diversity metrics for morphology embeddings.
    
    Parameters
    ----------
    embeddings : np.ndarray
        Embedding matrix (n_samples × n_features)
    sample_size : int
        Maximum samples for pairwise distance computation
    
    Returns
    -------
    metrics : Dict[str, float]
        Diversity metrics (mean_distance, std_distance, etc.)
    """
    from scipy.spatial.distance import pdist
    
    if len(embeddings) == 0:
        return {"mean_distance": 0.0, "std_distance": 0.0, "n_samples": 0}
    
    if len(embeddings) == 1:
        return {"mean_distance": 0.0, "std_distance": 0.0, "n_samples": 1}
    
    # Sample if too large
    if len(embeddings) > sample_size:
        idx = np.random.choice(len(embeddings), sample_size, replace=False)
        embeddings = embeddings[idx]
    
    # Compute pairwise distances
    distances = pdist(embeddings, metric='euclidean')
    
    return {
        "mean_distance": float(np.mean(distances)),
        "std_distance": float(np.std(distances)),
        "n_samples": len(embeddings),
    }
