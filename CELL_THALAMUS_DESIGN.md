How Cell Thalamus v1 fits the Printed Tensor program
This project is not the main printed tensor. It sits next to it and makes it possible to trust the big thing when we build it. Cell Thalamus is the variance-aware biological instrumentation layer that filters noise, anchors trust, and routes cell-level signals into a learnable structure for the tensor.
The printed tensor vision is:
cell line × stressor × perturbation × measurement
shared rails for POSH, Cell Painting and eventually FLEX based Perturb seq
stress axes that are conserved across lineages, with clear lineage specific twists
a reference atlas that future pooled screens can map onto instead of inventing a new coordinate system every time
Right now that world is aspirational. The company has fragments: disease driven pooled screens, focused pathway libraries, scattered stress models, each with its own readout recipe and variance structure. They do not compose.
Cell Thalamus v1 is the small, honest loop that sits upstream of that printed tensor. It is deliberately arrayed, cheap in comparison, and boring in the right ways.
Relationship to the printed tensor
You can think of the relationship like this:
Printed Tensor:
 Whole genome, pooled POSH on 3 to 6 lines, six stress axes, eventually with FLEX overlays. This is where we learn gene level structure across lineages and stressors.
Cell Thalamus v1:
 Two lines, arrayed chem first, then a small KO panel. Cell Painting plus a scalar viability anchor. This is where we prove that the rails are real, the variance is honest, and the stressors actually carve meaningful axes before we spend big on pooled.


They share the same core instincts:
same lineage backbone: A549 plus HepG2 or U2OS are core printed tensor candidates
same stress biology: oxidative, ER, mitochondrial, DNA damage and friends
same measurement philosophy: a high dimensional morphological manifold anchored by simple scalars
same obsession with variance partition and SPC on sentinels
The printed tensor is the full grammar. Cell Thalamus v1 is a syntax check.

What Cell Thalamus v1 is doing for the printed tensor
1. Validating the biological rails in a controlled setting
The printed tensor assumes that:
stress biology is low dimensional and conserved
the chosen stressors reliably excite those axes across lines
morphology plus a scalar anchor can resolve those axes
Phase 0 and Phase 1 test exactly that, but in an arrayed world where you can see every well and every factor clearly.
Phase 0 checks that a simple panel of stressors on A549 plus a second line produces a stable manifold where biological factors dominate and operators, days and plates are measurable, not mysterious.
Phase 1 adds clean KOs on top to show that genotype perturbations move along interpretable axes rather than adding noise.
If this fails, the printed tensor design is fantasy. Better to learn that while plating a few dozen 384s than while printing a whole genome library.
2. Tuning stressor and dose choices before they become rails
The printed tensor wants a disciplined stressor panel, one or two compounds per axis, with doses that reveal structure rather than simply killing cells.
Cell Thalamus v1 gives you:
dose response curves for scalar viability and morphology over time
a first view of which compounds actually produce separable morphological manifolds in these lines
early identification of stressors that are too flat, too lethal or too erratic for pooled work
Those results feed directly into:
which compounds make the cut for the printed tensor stress panel
which doses become standard rails for POSH and FLEX
which time points carry the most information


You do not need to guess. You can pick rails that are already proven to support a low dimensional, interpretable manifold.
3. Establishing variance models and SPC playbooks that will be reused
The printed tensor depends on:
understanding how much variance comes from cell line, stressor, dose and genotype
making sure plate, day and operator effects are non zero but controlled
having sentinels that flag bad runs before embeddings drift into nonsense


Phase 0 and Phase 1 bake this into the design:
explicit mixed models for both scalar and morphology
sentinels placed consistently across plates and days
SPC limits that define when a run is learnable versus unsafe


Those models and thresholds become the starting templates for POSH based tensor runs. Instead of inventing QC after the fact, you arrive with a tested variance model and sentinel regime.
4. Prototyping the morphological manifold that POSH will live in
The printed tensor will lean heavily on morphological embeddings from POSH and Cell Painting. You want to know in advance:
whether A549 and HepG2 or U2OS actually separate cleanly at baseline
whether stressors pull them along shared axes or into lineage specific branches
whether scalar anchors and morphology agree or produce useful tensions
Cell Thalamus v1 delivers a first pass at that manifold:
same imaging style as POSH, just arrayed instead of pooled
embeddings at the well level that can be used to design the downstream POSH analysis stack
early insight into which axes are robust across lines and which are fragile
This is the rehearsal stage for the manifold that POSH will ultimately print at scale.
5. Defining positive controls and “teaching genes” for the tensor
The printed tensor will need positive control genes and known regulators that act as anchors in the high dimensional space.
Phase 1 works with a small KO panel built around canonical stress regulators:
KEAP1, NFE2L2 for oxidative
ATF4, HSPA5, DDIT3 for ER stress
TP53, CDKN1A, BAX, BCL2L1, CDK1 for damage and cell fate
You learn:
which of these produce strong, clean phenotypes on the stress rails you care about
which are subtle but specific to certain axes
which are unreliable in your hands
Those become:
positive controls for future POSH runs
“teaching genes” the models can use to interpret unlabeled structure in the printed tensor
candidate sentinels for genetic performance checks in pooled experiments
Why this is orthogonal, not redundant
The printed tensor is pooled, whole genome, and expensive. It is built to maximize information per experiment once the rails are trusted.
Cell Thalamus v1 is:
arrayed, low complexity, two lines, small KO panel
explicitly focused on measurement quality, variance structure, stressor performance and genotype interpretability
designed to be run and iterated quickly while POSH and FLEX infrastructure continue to harden
It does not answer the same questions as the printed tensor. It answers the questions the tensor is built on:
Are the rails real
Is the biology low dimensional and conserved in practice, not just on slides
Are the technical terms under control
Do we have a QC and sentinel strategy that works before we embed millions of cells
Once those answers are in hand, the printed tensor program can proceed with much higher confidence and a clear playbook, instead of discovering basic measurement problems at whole genome scale.
Project: Cell Thalamus v1
Goal: Build a small, honest cell loop that
gives you a stable morphological manifold
anchors it with an orthogonal scalar
then hangs a few causal CRISPR levers on top
Think of Phase 0 as instrument calibration
and Phase 1 as causal annotation.
Phase 0 – Chemistry only, no CRISPR
1. Objective
Build a two cell line Cell Painting assay with an orthogonal scalar readout.
Show that biology dominates variance and technical noise is measurable, not mysterious.
Set up SPC-style monitoring on sentinels so you know when a run is untrustworthy.
No editing yet. Just cells plus compounds.
2. Core design
Cell lines
A549
HepG2 or U2OS


Media
Grow each line in its normal growth medium.
For assay: switch both into the same assay medium for the final 24 hours before treatment and readout.
Readouts
Rich: Cell Painting morphology (standard panel, no heroics).
Scalar (orthogonal): ATP-based viability on a plate reader, or similar luminescent viability assay.
Compounds
 Core 10 stressor panel:
tBHQ
Hydrogen peroxide
Tunicamycin
Thapsigargin
Etoposide
CCCP
Oligomycin A
2-deoxy-D-glucose
MG132
Nocodazole
Vehicle: DMSO (and aqueous vehicles as needed for compounds like H₂O₂ and 2-DG).
3. Doses, time points, replication
Doses
For each compound: 6 doses
vehicle
+5
Choose a wide but safe bracket for each compound, not hand tuned.
 The aim is to span subthreshold to near toxic, not to perfectly optimize.
Time points
Early: 12 hours post treatment
Late: 48 hours post treatment


Replication structure
For each combination of cell line × compound × dose × time:
Plates: at least 3 plates
Days: at least 2 experimental days
Operators: at least 2 operators, each handling a balanced subset of plates
Imaging: fixed settings, one or two sessions per run


Sentinels per plate
DMSO
One mild stressor at a fixed dose (for example low tBHQ)
One strong stressor at a fixed dose (for example mid-to-high ER or proteasome stress)
Sentinels are placed in fixed wells at the same doses on every plate.
4. Workflow outline
Day −1
Seed A549 and HepG2/U2OS into assay plates.
Switch to shared assay medium once attached and at the correct density.
Day 0
Apply compounds across doses.
Record plate layout, operator, day, and sentinel wells in a design file.
Day 0 + 12 h and Day 0 + 48 h
Run ATP assay on either
sibling plates, or
the same plates before fixation, depending on compatibility.
Fix and stain for Cell Painting.
Image all plates on the high-content system.


5. Analysis plan for Phase 0
Data prep
Extract morphology embeddings per well.
Aggregate scalar readout per well.
Merge with design metadata (cell line, compound, dose, time, plate, day, operator, sentinel flag).


Mixed models
For the scalar and for selected morphology dimensions or PCs, fit:
metric ~ 1
      + (1 | cell_line)
      + (1 | compound)
      + (1 | dose)
      + (1 | timepoint)
      + (1 | plate_id)
      + (1 | day)
      + (1 | operator)
Check that:
cell_line, compound, dose, and timepoint explain a large fraction of variance
plate_id, day, and operator are non-zero but not dominant
SPC on sentinels
Track sentinel values over time for the scalar and a small set of morphology scores.
Set control limits (for example mean ± 3 standard deviations).
Any run where sentinels breach limits is flagged as “do not learn from this.”


Phase 0 success criteria
Stable morphological manifold with recognizable axes (oxidative, ER stress, DNA damage, mitochondrial, etc).
Biological variance terms dominate technical ones.
Sentinels are stable enough to support SPC.
Scalar and morphology show sensible relationships
 (some stressors shift morphology with preserved scalar, others collapse both).


Once this looks sane, you move to editing.

Phase 0 Implementation Status
Current implementation provides a complete simulation and analysis infrastructure for Phase 0:

Backend simulation engine (src/cell_os/cell_thalamus/)
Biologically realistic cell response model with:
 Cell-line-specific sensitivity (A549 NRF2-primed, HepG2 ER/mito sensitive)
 Stress-axis-specific responses (oxidative, ER, mitochondrial, DNA damage, proteotoxic, cytoskeletal)
 Decoupled ATP and viability with metabolic penalties
 Proliferation-coupled microtubule sensitivity
 Time-dependent response curves (12h, 24h, 48h, 72h)
Five-channel Cell Painting simulation (ER, mitochondria, nucleus, actin, RNA)
Plate layout engine supporting 96-well and 384-well formats
Sentinel well placement and tracking
Design metadata (plate_id, day, operator, batch) for variance decomposition

Database layer (src/cell_os/database/cell_thalamus_db.py)
SQLite schema with physical well uniqueness constraints
Aggregation methods for dose-response with mean, std, n
Morphology matrix extraction for PCA
Sentinel data queries with control limits
Variance analysis queries by factor

Analysis and visualization dashboard (frontend/src/pages/CellThalamus/)
Tab 1: Run Simulation
 Four run modes: Demo (~7 wells, 30s), Quick (~48 wells, 3 min), Standard (~192 wells, 10 min), Full (~768 wells, 30 min)
 Plate template system (Minimal 2×2, Compact 4×3, Standard 4×6, Full 8×12)
 Live data streaming with real-time updates during simulation runs
 Status tracking and progress monitoring

Tab 2: Morphology Manifold
 Real PCA using sklearn eigendecomposition (not fake linear combinations)
 Interactive channel selection (ER, Mito, Nucleus, Actin, RNA) with minimum 2 channels
 Variance explained: PC1 and PC2 percentages displayed
 Color modes: cell line, compound, dose, timepoint
 Dose trajectory visualization showing paths through morphology space as dose increases
 Biplot arrows showing channel loadings (which features drive each PC)
 Sentinel highlighting mode (grey out experimental wells, focus on QC sentinels)
 Aggregated variance blob visualization (mean ± 2 SD ellipses)
 Live mode: auto-refresh every 5 seconds during running experiments

Tab 3: Dose Response Explorer
 Multi-timepoint dose-response curves with error bars (mean ± SD, n displayed)
 Cell-line-specific curves for each compound
 Normalized dose comparison across compounds
 ATP signal, viability, and morphology channel metrics
 Time-dependent shifts in IC50 and efficacy

Tab 4: Variance Analysis
 Mixed model variance decomposition by factor (cell_line, compound, dose, timepoint, plate_id, day, operator)
 Pie charts showing variance partition for ATP signal and morphology PCs
 Factor contribution tables with variance percentages
 Identifies whether biological or technical factors dominate

Tab 5: Sentinel SPC
 Statistical process control charts for sentinel wells over time
 Mean ± 3 SD control limits
 Flags out-of-control runs for exclusion from learning
 Tracks ATP signal and morphology stability across plates and days

Tab 6: Plate Viewer
 96-well plate heatmaps for each plate in the design
 Visual inspection of spatial patterns and edge effects
 Hover tooltips with well metadata

API layer (src/cell_os/api/thalamus_api.py)
FastAPI endpoints for all data retrieval operations
Real-time status polling for running simulations
PCA computation endpoint with channel selection support
Dose-response aggregation with statistics
Variance analysis computations
Sentinel data extraction

Execution infrastructure
Standalone script (standalone_cell_thalamus.py) with embedded biological parameters
Parallel runner (src/cell_os/cell_thalamus/parallel_runner.py) for multiprocessing
Jupyter notebook (notebooks/cell_thalamus_jupyterhub.ipynb) for interactive analysis
AWS/JupyterHub deployment documentation (JUPYTERHUB_SETUP.md, STANDALONE_USAGE.md)

What's still needed for wet lab Phase 0 execution:
Real Cell Painting data acquisition (currently simulated)
Integration with high-content imaging system
Plate reader integration for ATP measurements
Actual operator and day assignments
Connection to LIMS for sample tracking
Real-time microscope control and adaptive sampling
Validation that simulated variance structure matches reality

The current implementation allows complete dry-run of Phase 0 analysis workflows, visualization development, and QC logic validation before any wet lab execution begins.

Phase 1 – Mini CRISPR KO panel layered on top
You now rerun roughly the same world, with genetics used as causal probes.
1. Objective
Introduce a small, interpretable KO panel that perturbs specific stress pathways seen in Phase 0.
Use KOs to label and sharpen biological axes without destroying the variance structure.
Confirm technical noise remains controlled despite added handling and editing.
2. KO gene panel
Targets aligned with stress pathways:
KEAP1
NFE2L2
ATF4
HSPA5
DDIT3
TP53
CDKN1A
BAX
BCL2L1
CDK1
Controls:
AAVS1
Non-targeting control sgRNAs


Use bulk-edited populations per target at this stage, not clones.

3. Design changes from Phase 0
Everything from Phase 0 stays the same, except:
Genotype is now an additional factor.
You do not test the full compound × dose × time × genotype grid.


Strategy
Keep the full grid for wild-type cells (as in Phase 0).
For KOs, sample a reduced set of informative conditions:
a few representative compounds (for example oxidative, ER, mitochondrial, DNA damage)
two doses per compound
one or two timepoints (likely the most informative based on Phase 0)


WT and KO populations are plated together on the same plates to avoid confounding genotype with plate or day.
4. Workflow outline for Phase 1
KO generation
Generate bulk KO populations for each target in each cell line
 (or start with one line to keep it lean).
Confirm editing qualitatively (Western, qPCR, or targeted amplicon sequencing if desired).
Assay run
Seed WT and KO populations together.
Same media strategy as Phase 0.
Apply full compound set to WT and reduced set to KOs.
Same scalar and Cell Painting readouts.
Same replication rules and sentinel strategy.


5. Analysis plan for Phase 1
Update the model to include genotype:
metric ~ 1
      + (1 | cell_line)
      + (1 | genotype)        # WT vs each KO
      + (1 | compound)
      + (1 | dose)
      + (1 | timepoint)
      + (1 | plate_id)
      + (1 | day)
      + (1 | operator)
Questions of interest:
Do genotypes move along biological axes already observed in Phase 0
 (for example KEAP1 KO shifts along an oxidative axis, HSPA5 KO amplifies ER stress)?
Does adding genotype preserve the technical variance structure
 (plate, day, operator contributions should not inflate)?
Do KOs disambiguate compounds that were ambiguous in Phase 0
 (clusters that separate only in KO space)?


SPC and sentinel logic remains unchanged. Confirm sentinels behave similarly on plates containing KOs versus WT-only plates.
Phase 1 success criteria
Genotype effects align with Phase 0 biological axes.
Technical variance remains well behaved.
KOs clarify mechanisms for at least some compounds.
The manifold becomes more interpretable, not noisier
Phase 2 – Prove autonomy in a sandbox
Hold biology mostly constant
 Same cell lines, same core assay, same scalar and sentinels.
Introduce new perturbations and a small context shift
 New compounds, mild media or signaling changes.
Build a closed learning loop
 Model predicts morphology and scalar before the experiment, then updates after.
Let the model choose experiments
 Active learning under safety, balance, and QC constraints.
Benchmark against baselines
 Compare epistemic gain versus random, grid, or human-designed designs.
Use KOs surgically
 Targeted genetics to disambiguate ambiguous regions of the manifold.
Success looks like:
 Prediction error drops, uncertainty shrinks, variance structure stays sane.


Phase 3 – Scale and stress-test autonomy
Expand biological diversity
 More cell lines, new lineages, disease-relevant contexts.
Expand perturbation space
 More compounds, new pathways, CRISPRi/a, limited combinations.
Add new modalities
 RNA, secreted proteins, metabolites.
Increase real-world nuisance
 More days, operators, microscopes, reagent lots.
Run autonomy at scale
 Continues to outperform baselines as dimensionality explodes.
Success looks like:
 Biological axes persist, new ones emerge cleanly.


Phase 4 – Product-directed autonomy
Introduce goal-oriented objectives
 Beyond uncertainty reduction: TA relevance
Add long-horizon planning
 Multi-step experimental reasoning.
Move into real programs
 Translational constraints and timelines
Success looks like:
 Autonomous discovery produces product-relevant insights humans did not hand-design.







