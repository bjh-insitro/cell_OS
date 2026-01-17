# Cell Thalamus — Dose and Timepoint Calibration

**Last update: Jan 16, 2026**

This document defines Cell Thalamus, a narrow, intentional calibration program that sits upstream of the printed tensor.

Its purpose is explicit and limited:

> Identify stressor doses and timepoints that produce maximal, reproducible morphological separation without viability collapse.

Nothing more is claimed. Nothing else is optimized.

If this calibration cannot be done cleanly in an arrayed, visible setting, then pooled, whole-genome experiments are not yet justified.

---

## Relationship to the Printed Tensor

The printed tensor is the large-scale commitment:

- **Structure:** cell line × stressor × perturbation × measurement
- **Mode:** pooled, genome-wide POSH, eventually with FLEX overlays
- **Goal:** learn gene-level structure across lineages and stress contexts

It is expensive and difficult to debug. It only makes sense after stressor doses and timepoints are known to operate in a signal-rich regime.

**Cell Thalamus exists solely to determine those operating points.**

---

## Scope and Philosophy

This effort is deliberately constrained:

- Arrayed, not pooled
- Small number of cell lines
- Chemistry only
- No mechanism claims
- No disease claims
- No generalization claims

The only question being asked, repeatedly, is:

> Does this stressor, at this dose and timepoint, move cells in a reproducible way that is clearly larger than technical noise and prior to viability collapse?

---

## Structure

The program proceeds in three sequential phases. Each phase earns the right to proceed to the next.

---

## Phase 0 — Single-Stressor Calibration

**Focus:** menadione in A549

### Objective

Nominate one dose and one timepoint for menadione in A549 where:

- morphology shifts monotonically relative to vehicle
- the shift is reproducible across plates and days
- the shift clearly exceeds technical variation
- viability shows early stress but has not collapsed

No cross-stressor or cross-line claims are made.

### Experimental Design

| Parameter | Value |
|-----------|-------|
| **Cell line** | A549 |
| **Stressor** | Menadione |
| **Readouts** | Cell Painting morphology (standard panel), Stress-specific endpoint appropriate to the axis under test (e.g. γ-H2AX antibody labeling for DNA damage stress), Simple viability collapse check (e.g. CytoTox-Glo assay) |
| **Doses** | Vehicle + 5 doses spanning subthreshold to near-toxic |
| **Timepoints** | 24 h and 48 h |

### Replication and Stability

- ≥3 plates
- ≥2 experimental days
- Fixed sentinel wells per plate (vehicle + fixed menadione dose)
- Sentinels are used only to assess run-to-run stability, not biological interpretation.

### Core Analyses

1. Compute centroids for vehicle and treated conditions in a predefined morphology feature space
2. Measure magnitude of morphology shift across doses and timepoints
3. Compare shifts to replicate and plate/day variation
4. Plot morphology shift versus CytoTox-Glo to identify the pre-collapse shoulder region
5. Use γ-H2AX as a sanity check to flag regimes dominated by overt DNA damage or signal saturation

**Decision rule:** nominate the dose/timepoint with the largest reproducible morphology shift that occurs before the CytoTox-Glo collapse inflection. γ-H2AX is not optimized; it is used only to flag pathological regimes.

### Phase 0B — Optional bulk RNA-seq anchoring (post-nomination)

Once a menadione dose is nominated by morphology separation and lack of collapse, optionally run a small bulk RNA-seq follow-up at two timepoints at the nominated dose (plus vehicle) to capture transcriptomic changes.

**Timepoint rule:** timepoints are selected per stressor to match nominated kinetics, but must include one 24 h and one 48 h sample (to preserve comparability and operational simplicity).

This provides an interpretable anchor for later Perturb-seq overlays while keeping Phase 0 selection purely morphology-first.

**Outcome:** one nominated menadione dose and one nominated timepoint in A549. Phase 0B optionally adds two-timepoint bulk RNA-seq characterization at the nominated dose.

### Phase 0 Success Criteria

Phase 0 is successful if:

- A single dose and timepoint are nominated at maximal, reproducible separation
- Replicate agreement is high (e.g. cosine similarity > 0.7 or within-condition distances tighter than between-condition)
- Condition-driven shifts clearly exceed technical variation

If these criteria are not met, Phase 0 iterates or stops.

---

## Phase 1 — Multi-Stressor Calibration in A549

**Focus:** extend calibrated logic to the remaining stressors

### Objective

Using A549 only, identify usable doses and timepoints for the remaining compounds that:

- produce reproducible morphology shifts
- exceed technical variation
- avoid catastrophic viability loss

The goal is consistent operating logic, not matching effect sizes across compounds.

### Experimental Design

| Parameter | Value |
|-----------|-------|
| **Cell line** | A549 |
| **Stressors** | Remaining 9 compounds in the core stressor panel |
| **Doses** | Vehicle + 5 doses per compound |
| **Dose nomination rule** | Nominate one operating dose per stressor total (shared across 24 h and 48 h) |
| **Tie-breaker principle** | If 24 h and 48 h disagree, prefer the dose that is safe at both timepoints (conservative, pooled-friendly). The goal is robustness, not maximal separation at a single timepoint. |
| **Imaging timepoints** | Fixed at 24 h and 48 h for every stressor |

### Phase 1 Success Criteria

For each compound:

- A usable operating dose and timepoint is nominated
- Morphology shifts are reproducible and larger than technical noise
- Failure modes (too flat, too lethal, too erratic) are explicitly documented

Compounds that fail are not rescued.

### Phase 1B — Optional bulk RNA-seq anchoring (post-nomination)

For each stressor in Phase 1 where an operating dose is nominated by Cell Painting separation without collapse, optionally run bulk RNA-seq at 24 h and 48 h at the nominated dose (plus vehicle).

**Timepoint rule:** timepoints are fixed at 24 h and 48 h (to preserve comparability and operational simplicity).

This adds transcriptomic anchors for later Perturb-seq overlays, without changing the Phase 1 selection criterion.

---

## Phase 2 — Multi-Line Calibration (HepG2 + LX-2)

**Focus:** determine cell-line–specific operating doses across additional cell types, with A549 retained as a reference

### Objective

Extend calibration beyond A549 to establish cell-line–specific operating doses for each stressor.

We explicitly assume that doses will not transfer cleanly across cell lines due to differences in potency, tolerance, and stress handling. Phase 2 therefore re-runs full dose curves in each additional cell line rather than transferring a single dose from A549.

### Experimental Design

| Parameter | Value |
|-----------|-------|
| **Cell lines** | A549 (reference), HepG2, LX-2 (hepatic stellate cells; includes a TGF-β–based fibrotic stress axis) |
| **Stressors** | All stressors carried forward from Phase 1 |
| **Doses** | Vehicle + 5 doses per stressor per cell line |
| **Imaging timepoints** | Fixed at 24 h and 48 h |
| **Dose nomination rule** | Nominate one operating dose per stressor per cell line, shared across 24 h and 48 h |
| **Tie-breaker principle** | If 24 h and 48 h disagree, prefer the dose that is safe at both timepoints (conservative, pooled-friendly). The goal is robustness, not maximal separation at a single timepoint. |

### Phase 2 Success Criteria

- Stress-induced morphology shifts are observable in HepG2 and LX-2 for a meaningful subset of stressors
- A549 remains a stable reference across runs
- Signal remains larger than technical noise within each cell line
- Clear failures are documented rather than averaged away
- No claims of conservation, universality, or disease relevance are made at this stage.

---

## What Comes Next (and Why It Stops Here for Now)

This calibration program is intentionally scoped to stop after Phase 2.

Decisions about extending Cell Thalamus into additional cell systems (for example iPSC-derived NGN2 neurons or iPSC-derived microglia) are not pre-committed in this document. Instead, they are deferred deliberately.

The rationale is not technical immaturity or fear of complexity. It is **strategic sequencing**.

By the end of Phase 2, the program will have produced:

- Calibrated, cell-line–specific operating doses across multiple stressors
- A clear picture of which stress axes are signal-rich versus fragile
- Empirical evidence about assay robustness, failure modes, and throughput cost

At that point, the highest-value next step should be chosen in consultation with the senior steering committee, informed by the data generated so far and aligned with company priorities at that time.

**Cell Thalamus exists to generate that decision leverage. It does not presume the answer in advance.**
