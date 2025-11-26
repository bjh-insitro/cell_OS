"""
POSH Library Design Agent.

This module implements the logic for designing a CRISPR guide library for a POSH pooled imaging screen.
"""

from dataclasses import dataclass
import pandas as pd
from typing import Optional, List, Dict, Any
import hashlib

from cell_os.lab_world_model import LabWorldModel
from cell_os.posh_scenario import POSHScenario
from cell_os.guide_design_v2 import GuideLibraryAdapter, GuideDesignConfig
from cell_os.upstream import GeneTarget

class LibraryDesignError(Exception):
    """Raised when the library design fails."""
    pass

@dataclass
class POSHLibrary:
    """
    Represents a designed CRISPR guide library.
    """
    df: pd.DataFrame
    num_genes: int
    guides_per_gene_actual: int
    vendor_payload: str

def design_posh_library(world: LabWorldModel, scenario: POSHScenario) -> POSHLibrary:
    """
    Design a CRISPR guide library suitable for a POSH pooled imaging screen.

    Args:
        world: The LabWorldModel containing resources. Currently unused, but reserved 
               for future integration with reference genomes and design defaults.
        scenario: The POSHScenario defining the requirements.

    Returns:
        A validated POSHLibrary object.

    Raises:
        LibraryDesignError: If the design cannot be satisfied.
    """
    
    # 1. Setup Guide Design Engine
    config = GuideDesignConfig(
        min_guides_per_gene=scenario.guides_per_gene,
        max_guides_per_gene=scenario.guides_per_gene + 2, # Allow some flexibility
        gene_list_path=None # We will pass genes directly
    )
    adapter = GuideLibraryAdapter(config=config)

    # 2. Prepare Targets
    # Validate genes_list length if present
    if scenario.genes_list is not None and len(scenario.genes_list) != scenario.genes:
        # We could warn, but mismatch is risky. Let's fail fast or at least warn heavily.
        # Given "Terse. Productive. Deterministic", failing on explicit mismatch is safer.
        raise LibraryDesignError(
            f"genes_list length {len(scenario.genes_list)} != genes {scenario.genes}"
        )

    gene_targets = []
    if scenario.genes_list:
        gene_targets = [GeneTarget(symbol=g) for g in scenario.genes_list]
    else:
        # Generate dummy genes based on count
        # Note: Dummy names are temporary behavior for synthetic tests or when no list is provided.
        for i in range(scenario.genes):
            gene_targets.append(GeneTarget(symbol=f"Gene_{i+1:04d}"))

    # 3. Generate Guides
    try:
        library_df = adapter.design_library(genes=gene_targets)
    except Exception as e:
        raise LibraryDesignError(f"Guide design failed: {e}")

    if library_df.empty:
        raise LibraryDesignError("No guides generated.")

    # 4. Process and Validate Guides
    processed_rows = []
    
    # Deterministic sorting
    library_df = library_df.sort_values(by=['gene_symbol', 'guide_sequence'])
    
    OFF_TARGET_THRESHOLD = 50.0 # anything below this is rejected

    for _, row in library_df.iterrows():
        gene = row['gene_symbol']
        seq = row['guide_sequence']
        pam = row.get('pam_site', 'NGG') # Default to NGG
        
        # Calculate GC content
        gc_content = _calculate_gc_content(seq)
        
        # Simple off-target score
        ot_score = _simple_off_target_score(seq)
        
        # Check constraints
        if ot_score < OFF_TARGET_THRESHOLD:
            # Skip this guide entirely
            continue
        
        # Validate PAM
        if pam != 'NGG':
             raise LibraryDesignError(f"Unsupported PAM {pam} for guide {seq}")

        processed_rows.append({
            'gene': gene,
            'sequence': seq,
            'pam': pam,
            'ot_score': ot_score,
            'gc_content': gc_content,
            'vendor_index': 0 # To be filled
        })

    df = pd.DataFrame(processed_rows)
    
    if df.empty:
        raise LibraryDesignError("No guides remained after validation.")
    
    # Ensure minimum guides per gene
    genes_passed = df['gene'].unique()
    if len(genes_passed) < len(gene_targets):
        # Some genes lost all guides
        missing = set(g.symbol for g in gene_targets) - set(genes_passed)
        # We could raise here too, but let's see if we can satisfy the rest.
        # Actually, if a gene is missing completely, we definitely failed "For each gene...".
        raise LibraryDesignError(f"Genes lost due to filtering: {missing}")
    
    # Select top N guides per gene
    final_rows = []
    for gene in genes_passed:
        gene_df = df[df['gene'] == gene].sort_values('ot_score', ascending=False)
        
        if len(gene_df) < scenario.guides_per_gene:
            raise LibraryDesignError(
                f"Gene {gene} only has {len(gene_df)} valid guides; "
                f"requires {scenario.guides_per_gene}."
            )
        
        selected = gene_df.head(scenario.guides_per_gene).copy()
        
        # Assign guide_id
        selected['guide_id'] = selected.apply(lambda r: f"{r['gene']}|{_hash_seq(r['sequence'])}", axis=1)
        final_rows.append(selected)
        
    final_df = pd.concat(final_rows)
    
    # 5. Vendor Formatting
    vendor_format = scenario.vendor_format or 'generic'
    
    final_df['vendor_index'] = range(1, len(final_df) + 1)
    
    vendor_payload = _generate_vendor_payload(final_df, vendor_format)
    
    return POSHLibrary(
        df=final_df,
        num_genes=final_df['gene'].nunique(),
        guides_per_gene_actual=final_df.groupby('gene').size().min(),
        vendor_payload=vendor_payload
    )

def _calculate_gc_content(seq: str) -> float:
    if not seq: return 0.0
    g = seq.count('G')
    c = seq.count('C')
    return (g + c) / len(seq) * 100.0

def _simple_off_target_score(seq: str) -> float:
    # Simple mock scoring:
    # Penalize poly-T, poly-G
    if 'TTTT' in seq: return 10.0
    if 'GGGG' in seq: return 20.0
    # Otherwise return high score (good)
    return 95.0

def _hash_seq(seq: str) -> str:
    return hashlib.md5(seq.encode()).hexdigest()[:8]

def _generate_vendor_payload(df: pd.DataFrame, fmt: str) -> str:
    if fmt == 'twist':
        # Twist format: name,sequence
        out = "name,sequence\n"
        for _, row in df.iterrows():
            out += f"{row['guide_id']},{row['sequence']}\n"
        return out
    elif fmt == 'genscript':
        # Genscript format
        out = "ID,Sequence\n"
        for _, row in df.iterrows():
            out += f"{row['guide_id']},{row['sequence']}\n"
        return out
    else:
        # Generic CSV
        return df.to_csv(index=False)
