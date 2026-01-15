# Phase 1 Thalamus Analysis Plan

## First Print Pilot (n=1)

### A549 CRISPR-KO at Menadione Operating Point

**Endpoints:** POSH + Perturb-seq

---

## Summary

Run a single genome-wide CRISPR-KO experiment in A549 under vehicle and the Phase 0 menadione operating point, and evaluate whether pooled optical and transcriptomic readouts produce a coherent, printable perturbation landscape.

This is the first experiment in the Printing Data Squad program. The bar is not completeness. **The bar is whether the rails survive first contact with reality.**

---

## Objective

Nominate whether the dataset is "printable" under the Printing Data definition: a run that is technically stable enough and biologically structured enough to become part of the shared tensor coordinate system.

Operationally, Phase 1 aims to show that:

- POSH produces perturbation-associated morphology signatures that are not dominated by batch artifacts
- Perturb-seq produces perturbation-associated transcriptional signatures with acceptable guide assignment and QC
- Stress gating exists: perturbations look meaningfully different under stress vs vehicle for a non-trivial subset
- Controls behave in a way that makes the entire run interpretable

**No discovery claims. No pathway stories required.**

---

## Scope

### In scope

- **Cell line:** A549
- **Stressor:** menadione at the Phase 0 operating point
- **Perturbations:** genome-wide CRISPR knockout library
- **Conditions:** vehicle and menadione (paired rails)
- **Endpoints:**
  - POSH imaging features
  - Perturb-seq expression signatures

### Out of scope

- hit calling and prioritization
- directionality relative to known biology as a pass/fail gate
- cross-line generalization
- tensor-level claims of conserved structure (that comes later)

### What n=1 means here

This is explicitly a pilot print. We will not claim variance components or infer robustness from replicate concordance.

Instead, we will rely on:

- internal controls
- internal consistency (within-run stability checks)
- sanity distributions (do effects look real and non-pathological)
- cross-modality coarse coherence

If these fail, the run is not printable.

---

## Experimental Design

### Conditions (paired rails)

- Vehicle + KO library
- Menadione (operating point) + KO library

### Required controls

Include in both modalities:

- non-targeting guides
- essential gene controls
- guide multiplicity controls if available
- guide representation metrics (coverage, dropout)

### Sentinels

Fixed reference guide sets (non-targeting + essentials) used as stability anchors.

---

## Data Products

### POSH

- images + metadata
- barcode / guide assignment
- morphology features (single-cell and/or per-guide aggregate)
- QC flags (focus, saturation, segmentation coverage where applicable)

### Perturb-seq

- guide assignment per cell
- QC-filtered expression matrix
- per-guide perturbation signatures in:
  - vehicle
  - stress
- guide representation and dropout summaries

---

## Core Analyses

### 1) Run-level technical integrity (gating)

**POSH:**
- saturation and focus QC pass rates
- staining channel health checks (expected intensity ranges)
- spatial artifacts: edge effects, illumination gradients
- guide assignment yield and distribution

**Perturb-seq:**
- guide assignment rate
- UMI / gene count distributions
- mitochondrial fraction and cell QC distributions
- guide representation and dropout

**Pass condition:**
Both modalities clear minimum QC thresholds such that downstream analyses are meaningful. If either modality collapses, the run is not printable.

---

### 2) Effect distribution sanity (within each modality)

**POSH:**
- distribution of per-guide effect sizes vs non-targeting
- essential genes should populate the high-effect tail
- non-targeting should be tight and centered

**Perturb-seq:**
- transcriptional deviation magnitude per guide vs non-targeting
- essential genes should show strong signatures and/or dropout consistent with KO impact
- non-targeting should be tight

**Failure mode:**
If non-targeting is broad (noisy) or essentials are not separable, signal-to-noise is inadequate.

---

### 3) Stress gating exists (interaction signal)

Compute, per guide, a stress interaction score:

- **POSH interaction:** difference between (guide under stress) and (guide under vehicle), relative to non-targeting
- **Perturb-seq interaction:** same concept in expression space

**Deliverables:**
- interaction effect size distribution
- fraction of guides in the high-interaction tail

**Pass condition:**
There is a detectable, structured interaction tail beyond controls, not just uniform drift.

---

### 4) Internal consistency checks (n=1 substitutes for replication)

These are the "don't lie to yourself" tests.

**POSH:**
- split-half consistency: randomly split cells for each guide into two halves, compute signatures, compare agreement
- guide-to-gene agreement: for multiple guides per gene, do they roughly align (at least for strong-effect genes)

**Perturb-seq:**
- split-half consistency per guide
- guide-to-gene agreement where coverage permits

**Pass condition:**
Strong perturbations show internal reproducibility beyond what you see in non-targeting.

---

### 5) Cross-modality coherence (coarse)

We do not require gene-level matching.

We require that the run behaves like a shared biological object:

- guides with large POSH deviation tend to have larger Perturb-seq deviation (rank-level association)
- stress increases deviation in both modalities globally
- essentials behave as "strong" in both modalities in some form (phenotype or dropout)

**Failure mode:**
One modality behaves sensibly and the other looks random, indicating a pipeline or execution break.

---

## Outputs

Phase 1 must produce:

1. a POSH QC and effect summary report
2. a Perturb-seq QC and effect summary report
3. a joint "printability" verdict with:
   - QC thresholds met or not met
   - control behavior
   - effect size distributions
   - stress interaction tail presence
   - internal consistency results
   - top technical failure modes and fixes

---

## Success Criteria (n=1)

Phase 1 is successful if:

1. both modalities clear minimum QC gates
2. non-targeting controls are tight and stable
3. essential controls separate clearly from non-targeting in at least one strong axis per modality
4. there exists a non-trivial tail of perturbations with strong, internally consistent effects
5. stress gating produces interaction signal beyond drift
6. cross-modality coherence exists at rank or module scale

If any of these fail, the dataset is not printable and should not be used as tensor substrate.

---

## Notes (program alignment)

This Phase 1 pilot is not "the tensor." It is the first printing attempt on shared rails.

If it passes, then we invest in what makes printing real:

- replication
- additional cell lines
- additional stressors
- stability over time

**If it fails, we do not rationalize it. We fix the rails.**

---

## Unanswered Questions

1. If POSH looks great and Perturb-seq looks like garbage, do we still call it printable for the tensor, given our "shared rails" story?
2. What are the minimum QC gates for each modality that trigger an automatic "do not learn from"?
