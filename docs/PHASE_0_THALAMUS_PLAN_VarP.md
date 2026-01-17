# Phase 0 Thalamus Plan

## A549 + Menadione Instrument Calibration

### Phase 0 Objective

The goal of Phase 0 is to identify a single menadione dose and timepoint in A549 cells that:

- Induces a reproducible morphological shift
- Exceeds technical sources of variation (plate, day, operator)
- Preserves viability in a regime compatible with pooled screening
- Is suitable as an operating point for downstream POSH and Perturb-seq work

---

## Scope

### In Scope

- **Goal:** Nominate one dose and one timepoint
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

### Out of Scope (explicitly deferred)

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

Doses should bracket sub-threshold through near-toxic based on prior knowledge or a brief scout. Perfect optimization is not required.

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

---

## Feature Representation

### Primary (required)

Hand-engineered morphology features:
- Intensity
- Texture
- Spatial organization
- Lipid-associated features where applicable

### Optional (exploratory only)

- DINO embeddings may be generated for visualization
- DINO is **not** used for Phase 0 go/no-go decisions

---

## Core Analyses

### 1. Stress-induced signal vs technical noise

- Compute centroids for vehicle and treated conditions in feature space
- Measure magnitude of shift induced by menadione
- Compare to:
  - Replicate-to-replicate variance
  - Plate/day variance

**Criterion:** Stress-induced shift must clearly exceed technical variation.

### 2. Reproducibility

- Assess correlation of treated-vs-vehicle shifts across plates and days
- Confirm replicates cluster by condition, not by plate or day

**Failure mode:** If embeddings cluster by technical factors, Phase 0 does not pass.

### 3. Viability anchoring

- Plot scalar viability against morphological shift across doses
- Identify operating region where:
  - Morphology shifts meaningfully
  - Viability remains compatible with pooled screening

This defines the candidate operating point.

### 4. Sentinel stability (lightweight SPC)

- Track sentinel wells across plates and days
- Flag runs with gross deviation as "do not learn from"
- Formal SPC limits may be added later if needed

---

## Phase 0 Outputs

Phase 0 analysis must produce:

1. A nominated menadione dose and timepoint
2. Evidence that morphology shifts:
   - Are reproducible
   - Exceed technical variance
3. Confirmation that viability is preserved
4. Identification of any obvious technical risks for pooled execution

**No biological claims are made at this stage.**

---

## Phase 0 Success Criteria

Phase 0 is considered successful if:

1. A single operating point is nominated
2. Replicate agreement is high (e.g. cosine similarity > 0.7 across replicates, the median within-condition replicate distance, by a fixed factor e.g. ≥2×)
3. Technical noise is measurable and subordinate to biological signal

If these criteria are not met, Phase 0 iterates or stops.

---

## Notes on Downstream Phases (for context only)

- Genetic perturbations and directionality testing are deferred to Phase 1
- Cross-line generalization and tensor-level analysis are deferred to later phases
- Phase 0 exists to earn the right to start pooled screens

---

## Variance Partition Model

You label anything that could plausibly move the readout while pretending it's biology.

For Phase 0 A549 + menadione, there are two buckets:
1. **Factors you intend to learn from (biology)**
2. **Nuisance factors you must not confuse with biology (technical + environment)**

Here's the minimal schema that actually lets you do variance partitioning without turning your life into a metrology thesis.

### 1) Biology factors (fixed effects you care about)

These are the ones you want to explain variance:

- `cell_line` (constant for now: A549)
- `treatment` (vehicle vs menadione)
- `dose` (categorical or numeric)
- `timepoint` (if you run more than one)
- `stain_panel_version` (if you change anything in Cell Painting panel, treat it as a different world)

If you only do one operating point, dose and timepoint collapse into "condition". That's fine.

### 2) Technical execution factors (random effects / nuisance)

These are the usual suspects.

#### Plate and layout

- `plate_id` (unique ID for each physical plate)
- `plate_layout_template` (if you use multiple templates)
- `well_id` (A01…P24)

Useful because edge effects are real and they recur.

**Important nuance:** You usually do not model "well" as random by itself unless you have repeated measures at same well positions across many plates. But you do want it recorded so you can add it as row, column, edge flag.

Store:
- `row`
- `column`
- `is_edge_well` (boolean)

#### Time and people

- `day` (date or run_day index)
- `operator` (who handled plating, dosing, staining)
- `instrument_run_id` (imaging session identifier)
- `imaging_order` (first vs last can matter)
- `incubator_id` (if multiple incubators)
- `hood` / `bench` (optional, only if you know it varies)

#### Reagents and lots

- `menadione_lot`
- `dmso_lot`
- `stain_lot` (or panel lot bundle)
- `media_lot`
- `FBS_lot` (if relevant)
- `plasticware_lot` (rarely, but if you suspect it, track it)

If you don't have the discipline to track every lot, pick the ones most likely to bite you: compound, stains, serum.

### 3) Sample state covariates (quiet confounders)

These are not "technical noise", they're the biology you accidentally changed.

Track them even if you don't model them initially:

- `seeding_density_target`
- `seeding_density_actual` (or cell count used)
- `confluence_at_treatment` (estimate or measured)
- `passage_number`
- `days_since_thaw` / `batch_id`
- `cell_batch_id` (the vial or expansion batch)

This category is the one that causes "mysterious irreproducibility" while everyone blames the microscope.

### 4) What not to label (yet)

These either explode complexity or aren't identifiable in Phase 0:

- "well" as a standalone random effect without row/col structure
- per-pipette channel IDs, unless you already have them
- micro-events like "time out of incubator" unless you can measure it reliably

Start with what you can actually record cleanly.

### 5) The minimum metadata table

For every well you need:

| Field | Description |
|-------|-------------|
| `plate_id` | Unique plate identifier |
| `well_id` | Well position (e.g., A01) |
| `row` | Row letter/number |
| `column` | Column number |
| `is_edge` | Boolean edge well flag |
| `day` | Experimental day |
| `operator` | Who executed |
| `instrument_run_id` | Imaging session ID |
| `condition` | Vehicle vs menadione |
| `dose` | Dose level |
| `timepoint` | 24h or 48h |
| `cell_batch_id` | Cell expansion batch |
| `passage_number` | Or proxy |
| `menadione_lot` | Compound lot |
| `stain_panel_version` | Panel version |
| `stain_lot` | Stain lot bundle |

That is enough to separate:
- Biology vs plate/day/operator
- Layout effects
- Batch drift

### 6) One blunt truth

Variance partition only works if the nuisance factors are not perfectly confounded with biology.

If "menadione plates were all run on Tuesday by Jana on microscope 2", the model can't save you. Your design has already lied.

**So the real answer is:** label everything above, but design so those labels are mixed, not segregated.

---

## Justification of Plate Selection, Treatment Days, and Plate Maps

### Overall design rationale

Phase 0 is designed to establish a reliable operating point, not to exhaustively partition all sources of variance.

The goal is to confirm that biological signal from menadione in A549 is reproducible and exceeds technical noise, while remaining compatible with downstream POSH and Perturb-seq.

### Plate and passage structure

Three plates are run per passage across three independent passages.

This provides:
- **Within-passage replication** to estimate execution and measurement variability
- **Across-passage replication** to assess stability over time and passage-associated drift

For each passage, 24h and 48h timepoints are seeded from the same cell split to avoid confounding timepoint with passage or batch effects.

### Treatment layout and plate maps

Sentinel wells are fixed in the same positions on every plate:
- Vehicle control
- A fixed mild menadione dose
- A fixed strong menadione dose

Fixed sentinels enable SPC-style monitoring and rapid identification of untrustworthy runs.

All non-sentinel treatment wells are randomized.

### Within-day layout strategy

The three plates run on the same day use different, pre-defined randomized layouts.

This prevents treatment effects from being confounded with row, column, or edge effects while preserving within-day comparability.

### Across-day layout strategy

A small set of plate templates is generated in advance.

These templates are rotated across passages rather than regenerated each day.

Template rotation ensures:
- Treatment positions vary across days
- Template-specific artifacts do not masquerade as day or passage effects
- Layouts remain debuggable and comparable over time

### Net outcome

- Position effects are measurable but not dominant
- Biological signal can be evaluated for reproducibility across plates and passages
- The design supports honest variance assessment and operating-point selection without unnecessary complexity at Phase 0
