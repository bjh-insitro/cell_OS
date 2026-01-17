# Phase 0 Thalamus Analysis Plan

## A549 + Menadione Instrument Calibration

**Ask:** Compute centroids for vehicle and menadione-treated conditions in a predefined, interpretable morphology feature space. Measure the magnitude of the treatment-induced shift and compare it to replicate-to-replicate and plate/day variance.

---

## Phase 0 Objective

Phase 0 aims to nominate a **maximal-separation, non-collapse operating point**.

The selected menadione dose and timepoint should maximize morphological separation from vehicle in the predefined feature space while remaining on the viability shoulder, not in the collapse regime.

This is not an EC-based criterion and is not defined by a fixed viability percentage. The operating point is defined empirically as the highest dose at which all of the following hold:

- the treatment-induced morphology shift increases relative to lower doses
- technical variance remains subordinate to biological signal
- viability has not entered abrupt or catastrophic decline

---

## Scope

### In scope

- **Goal:** nominate one dose and one timepoint
- **Cell line:** A549 only
- **Stressor:** Menadione
- **Readouts:** Immunofluorescence

### Stains + Acquisition Details

Data can be acquired in pyxscope on any available scope in lab 250. Slack #nikon-users for training.

#### Fluorescence Acquisition (20xHighNa-PoshPaintWidefield template in pyxscope)

| Channel Name | Stain |
|--------------|-------|
| DAPI | DAPI/Hoechst |
| AF488 | γ-H2AX Antibody + AF488 |
| AF555 | WGA |
| AF568 | Phalloidin |
| AF647 | MitoProbe |

#### Phasics + DAPI Acquisition (40x-PhasicsDAPI template in pyxscope)

| Channel Name | Stain |
|--------------|-------|
| DAPI | DAPI/Hoechst |
| Phasics | Phasics |

### Out of scope (explicitly deferred)

- Additional cell lines (e.g. HepG2, U2OS)
- Genetic perturbations (CRISPR, KO libraries)
- Directional correctness relative to known biology
- Clinical or disease relevance

---

## Experimental Design (Phase 0)

### Doses

| Dose Level |
|------------|
| Vehicle |
| Point1 |
| Point2 |
| Point3 |
| Point4 |
| Point5 |

The intent is to identify the shoulder of the stress–viability curve, not to optimize to a predefined EC value.

### Timepoints

- 24 hours
- 48 hours

### Replication

- ≥3 plates
- ≥2 experimental days

### Sentinels (per plate)

- Vehicle control
- Fixed menadione dose (same wells across plates)

Sentinels are used to assess run-to-run stability, not biological interpretation.

---

## Processing

- Full-well stitching using PyxCell3
- Feature extraction at FOV or well level
- No single-cell segmentation required for Phase 0
- Standard QC filters for focus, illumination, and saturation
- Agentic QC may be used to flag gross acquisition failures
- Nuclei based pixel intensity analysis

---

## Feature Representation

### Primary (required)

Hand-engineered morphology features:
- intensity
- texture
- spatial organization
- lipid-associated features where applicable

### Optional (exploratory only)

- DINO embeddings may be generated for visualization
- DINO is **not** used for Phase 0 go/no-go decisions

---

## Core Analyses

### 1. Stress-induced signal vs technical noise

- Compute centroids for vehicle and treated conditions in feature space
- Measure magnitude of shift induced by menadione
- Compare to:
  - replicate-to-replicate variance
  - plate/day variance

**Criterion:** Stress-induced shift must clearly exceed technical variation.

### 2. Reproducibility

- Assess correlation of treated-vs-vehicle shifts across plates and days
- Confirm that condition-associated shifts are reproducible across plates and days, and that technical factors do not dominate the condition-induced signal used for dose/timepoint selection

**Failure mode:** If embeddings cluster by technical factors, Phase 0 does not pass.

### 3. Viability and pathology anchoring

#### 3a. Pathology exclusion gate (γ-H2AX)

γ-H2AX is used solely as a pathology exclusion flag to identify dose–timepoint regimes dominated by overt DNA damage. It is not optimized, ranked, or used to nominate the operating point.

A dose–timepoint is disqualified as a saturated damage regime if either of the following plate-local criteria are met:

- ≥60% of nuclei exceed the vehicle P95 γ-H2AX nuclear intensity threshold, or
- ≥40% of nuclei exceed the vehicle P95 threshold and median nuclear γ-H2AX intensity is ≥3× vehicle.

These regimes are excluded even if morphology separation is large, because morphology here reflects damage dominance rather than structured stress response.

In this regime, perturbational effects are expected to flatten and converge, making the condition unsuitable for pooled perturbation analysis.

#### 3b. Viability shoulder identification

- Plot scalar viability against morphological shift across doses
- Identify the operating region where:
  - morphology shifts increase monotonically in magnitude from vehicle in morphology feature space, without reversal across adjacent doses
  - viability shows early stress but has not collapsed
  - γ-H2AX pathology flags remain below saturation thresholds

The candidate operating point is selected as the maximum morphology separation observed prior to viability inflection, not at a predefined viability threshold.

Dose nomination follows the decision order: morphology separation → reproducibility → viability → pathology exclusion.

### 4. Sentinel stability (lightweight SPC)

- Track sentinel wells across plates and days
- Flag runs with gross deviation as "do not learn from"
- Formal SPC limits may be added later if needed

---

## Phase 0 Outputs

Phase 0 analysis must produce:

1. A nominated menadione dose and timepoint selected at the maximal-separation, non-collapse operating point described above
2. Evidence that morphology shifts:
   - are reproducible
   - exceed technical variance
3. Confirmation that viability is preserved
4. Identification of any obvious technical risks for pooled execution
5. Documentation that the nominated operating point lies upstream of γ-H2AX-defined saturated damage regimes

**No biological claims are made at this stage.**

---

## Phase 0 Success Criteria

Phase 0 is considered successful if:

1. A single dose and timepoint are nominated that produce the largest reproducible morphology shift prior to viability inflection or collapse
2. Replicate agreement is high (e.g. cosine similarity > 0.7 across replicates, or median within-condition distance ≥ 2× tighter than between-condition distance)
3. Technical noise is measurable and subordinate to biological signal

If these criteria are not met, Phase 0 iterates or stops.

---

## Notes on Downstream Phases

- Genetic perturbations and directionality testing are deferred to Phase 1
- Cross-line generalization and tensor-level analysis are deferred to later phases
- Phase 0 exists to earn the right to start pooled screens
