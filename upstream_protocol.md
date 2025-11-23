# Upstream Protocol: Genetic Supply Chain

This document details the "Path A" workflow for creating the biological materials required for a POSH screen.

## Phase 1: Library Design & Synthesis

### 1.1 Gene Selection
*   **Input**: List of target genes (e.g., "Druggable Genome", "Kinome").
*   **Tool**: `src.upstream.LibraryDesign`.
*   **Parameters**:
    *   Guides per gene: 4 (Standard for CRISPRko/CRISPRi).
    *   Controls: 10-50 Non-Targeting Controls (NTCs).

### 1.2 Oligo Synthesis
*   **Vendor**: Twist Bioscience or GenScript.
*   **Format**: Pooled Oligos (Single-stranded DNA).
*   **Scale**: 10-100 ng (sufficient for cloning).
*   **Sequence Structure**:
    `[Adapter_Fwd] - [gRNA_Seq] - [Adapter_Rev]`

## Phase 2: Cloning (Golden Gate Assembly)

We use a one-step Golden Gate assembly to insert the gRNA pool into the CROP-seq vector.

### 2.1 Reagents
*   **Vector**: `pLenti-Guide-Puro` (or similar CROP-seq backbone).
*   **Enzyme**: BsmBI-v2 (NEB R0739).
*   **Ligase**: T4 DNA Ligase (NEB M0202).
*   **Cells**: Stbl3 Competent E. coli (to minimize recombination).

### 2.2 Reaction Mix (20 µL)
| Component | Volume |
| :--- | :--- |
| Plasmid Backbone (100 ng) | X µL |
| Oligo Pool (diluted) | Y µL |
| T4 DNA Ligase Buffer (10x) | 2 µL |
| BsmBI-v2 | 1 µL |
| T4 DNA Ligase | 1 µL |
| Nuclease-free Water | to 20 µL |

### 2.3 Cycling Protocol
1.  37°C for 5 min (Digest)
2.  16°C for 5 min (Ligate)
3.  Repeat steps 1-2 for 30 cycles.
4.  55°C for 15 min (Final Digest).
5.  80°C for 20 min (Heat Inactivation).

### 2.4 Transformation & Expansion
*   Transform 2 µL into Stbl3 cells.
*   Plate on large bioassay dishes (Ampicillin) to ensure >500x coverage of library complexity.
*   Scrape colonies and perform **Endotoxin-free Plasmid Maxiprep** (Qiagen).

## Phase 3: Virus Production

### 3.1 Transfection (HEK293T)
*   **Vessel**: T-175 Flasks (1-2 per library).
*   **Reagents**:
    *   Packaging Plasmids: psPAX2 (Gag/Pol), pMD2.G (VSV-G).
    *   Transfection Agent: Lipofectamine 3000 or PEI MAX.
*   **Protocol**:
    1.  Seed HEK293T cells to 70-80% confluency.
    2.  Mix Plasmids + Transfection Reagent in Opti-MEM.
    3.  Add to cells. Incubate 6 hours, then change media.

### 3.2 Harvest & Concentration
1.  Harvest supernatant at 48h and 72h.
2.  Filter through 0.45 µm PVDF filter (low protein binding).
3.  Concentrate using **Amicon Ultra-15 (100kDa cutoff)** if high titer is needed (e.g., 50x concentration).
4.  Aliquot and store at -80°C.

## Phase 4: QC (NGS Verification)

*   **Method**: PCR amplify the gRNA region from the plasmid pool.
*   **Sequencing**: Illumina MiSeq (Nano or Micro flow cell).
*   **Analysis**: Check for skew (uniformity) and dropout (missing guides).
    *   *Pass Criteria*: < 1% dropout, < 10-fold skew (90/10 ratio).
