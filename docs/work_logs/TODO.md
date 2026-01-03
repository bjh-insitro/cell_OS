# Cell OS - Things To Do

Last updated: December 16, 2025 (expanded with detailed context and implementation notes)

---

## Phase 0 Completed ✅

**What we proved:**
- ✅ Time-dependent death continuation works (ER/proteostasis show cumulative attrition)
- ✅ Mechanism recovery analysis shows system encodes biology, not just noise
- ✅ Mid-dose (0.5-2×IC50) at 12h gives 300× better stress class separation than all-doses mixed
- ✅ Mechanistic information moves earlier in time and lower in dose (design principle discovered)
- ✅ Dashboard visualization complete with dynamic PCA plots

**Key finding:** This is a world model, not a simulation.

---

## High Priority

### 1. Phase 1: Epistemic Agency
**Goal:** Agent learns to discover where information lives without being told

**Context:** We proved mid-dose 12h has 300× better separation than all-doses mixed. Now build an agent that discovers this on its own through active learning.

**Tasks:**
- [ ] **Design agent API that can query the simulation with well budgets**
  - Create endpoint that accepts: compound, dose, timepoint, cell_line, n_wells
  - Return: morphology features for those conditions
  - Track budget spent (e.g., 384 wells total)
  - Agent iteratively requests experiments, gets results, decides next query

- [ ] **Implement information content metrics (separation ratio, between/within variance)**
  - Already have this in `/api/thalamus/designs/{design_id}/mechanism-recovery`
  - Agent needs real-time version that computes on partial data
  - Metric: separation_ratio = between_var / within_var in PCA space
  - Higher ratio = better stress class discriminability

- [ ] **Build agent that allocates wells to maximize stress class discriminability**
  - Reinforcement learning or Bayesian optimization framework
  - State: current data collected, budget remaining
  - Action: choose next (compound, dose, timepoint, cell_line) to sample
  - Reward: improvement in separation ratio on held-out stress classes

- [ ] **Test: Can agent discover mid-dose is more informative than high-dose?**
  - Start agent with no prior knowledge
  - Does it converge to sampling 0.5-2×IC50 range?
  - Compare final allocation to uniform dose sampling

- [ ] **Test: Does agent learn to sample near boundaries (IC50 regions)?**
  - Check if agent learns to avoid vehicle (no signal) and saturating high-dose (death)
  - Does it focus on transition zones where mechanism is visible?

- [ ] **Compare agent allocation vs uniform sampling vs expert-designed experiment**
  - Uniform: equal wells per dose
  - Expert: manually designed mid-dose focus
  - Agent: learned allocation
  - Metric: separation ratio on held-out validation set

**Why this matters:** Transition from "running experiments" to "learning experimental design"

**Acceptance criteria:**
- Agent autonomously discovers mid-dose window yields higher information
- Agent allocates >60% of budget to 0.5-2×IC50 range without being told
- Agent-designed experiment outperforms uniform sampling on held-out validation

**Implementation notes:**
- Start with simple grid search agent as baseline
- Then add Bayesian optimization (Gaussian Process acquisition function)
- Advanced: RL agent with policy gradient (REINFORCE or PPO)

---

### 2. Predictive Modeling & Transfer Learning
**Goal:** Test if stress class structure generalizes to unseen compounds

**Context:** If PCA shows separable stress classes, can we train a classifier to predict mechanism from morphology? If transfer works, proves these are real biological fingerprints, not simulation artifacts.

**Tasks:**
- [ ] **Train classifier on morphology features to predict stress axis**
  - Input: 5-channel morphology scores (ER, mito, nucleus, actin, RNA) per well
  - Output: stress_axis label (er_stress, mitochondrial, oxidative, etc.)
  - Models to try: Random Forest, XGBoost, shallow neural net
  - Use mid-dose 12h data where separation is highest

- [ ] **Cross-validation: train on 8 compounds, test on 2 held-out compounds**
  - 10 compounds total: tBHQ, H2O2, tunicamycin, thapsigargin, CCCP, oligomycin, etoposide, MG132, nocodazole, paclitaxel
  - Leave-two-out CV: train on 8, test on 2 from same stress classes
  - Example: train on {tBHQ, H2O2, tunicamycin, thapsigargin, CCCP, oligomycin, etoposide, MG132}, test on {nocodazole, paclitaxel}
  - Metric: classification accuracy, confusion matrix

- [ ] **Test transfer: can model trained on tBHQ predict other oxidative stressors?**
  - Train on tBHQ only (oxidative stress)
  - Test on H2O2 (also oxidative stress)
  - Does model generalize within stress class?
  - Repeat for ER stress: train on tunicamycin, test on thapsigargin

- [ ] **Dose interpolation: predict mid-dose from low+high dose endpoints**
  - Train model with only low dose (0.1×IC50) and high dose (10×IC50)
  - Test: can it predict mid-dose (1×IC50) morphology?
  - Metric: MSE between predicted and actual morphology scores
  - Hard test: proves model learns dose-response relationship, not just memorizing

- [ ] **Cell-line transfer: train on A549, test on HepG2 (and vice versa)**
  - Do stress signatures transfer across cell types?
  - A549 = lung cancer, HepG2 = liver cancer
  - Expect: core mechanism visible in both, but magnitude/IC50 differs
  - Feature normalization critical here

**Why this matters:** Validates that morphology fingerprints encode generalizable mechanism

**Acceptance criteria:**
- >70% accuracy predicting stress axis from held-out compounds
- Dose interpolation error <20% for mid-dose predictions

**Data files:**
- Results stored in `cell_thalamus.db` table `experimental_results`
- Morphology columns: `morph_er`, `morph_mito`, `morph_nucleus`, `morph_actin`, `morph_rna`
- Metadata: `stress_axis`, `compound`, `dose_um`, `timepoint_hours`, `cell_line`

---

### 3. Documentation & Knowledge Capture
**Goal:** Make the mechanism recovery insights legible to future work

**Context:** We've discovered critical design principles through Phase 0. Document them before they get lost or forgotten.

**Tasks:**
- [ ] **Write "Design Principles" doc synthesizing key insights**
  - Core principle: mechanistic information moves earlier in time and lower in dose
  - Mid-dose window (0.5-2×IC50) at 12h optimal for stress class separation
  - High-dose/late-time dominated by death signature (cell loss, not mechanism)
  - All-doses-mixed collapses classes due to dose-dependent trajectory shifts
  - Include: separation ratio data, PCA plots, interpretation guide

- [ ] **Document the "where information lives" landscape (dose/time space)**
  - Create 2D heatmap: dose (x-axis) vs time (y-axis) colored by separation ratio
  - Annotate regions: "no signal zone" (vehicle), "mechanism window" (mid-dose 12h), "death zone" (high-dose 48h)
  - Explain why: adaptive stress responses visible before commitment to death
  - Reference: ER stress shows cumulative attrition, mito shows early fragmentation

- [ ] **Create reference guide for Phase 1 autonomous loop design**
  - Agent architecture options (RL, Bayesian opt, active learning)
  - API design for querying simulation
  - Reward function engineering (separation ratio, query efficiency)
  - Baselines to compare against (uniform, expert, random)

- [ ] **Add mechanism recovery findings to main README**
  - Update README.md with Phase 0 results summary
  - Link to mechanism recovery dashboard tab
  - Show before/after: all-doses (sep=0.018) vs mid-dose (sep=5.372)
  - Add citation-ready figure with PCA plots

- [ ] **Write up time-dependent attrition implementation rationale**
  - Why we need time-dependent death continuation
  - ER/proteostasis stresses show cumulative attrition (cells die over time)
  - Implementation: `prob_death = base_prob * (1 + time_hours/24)` for ER stresses
  - Validation: cumulative death curves match Cell Painting Consortium data
  - Code location: `src/cell_os/modeling.py` in `generate_experimental_results()`

**Why this matters:** Consolidate learnings so future phases don't reinvent the wheel

**Files to create:**
- `docs/DESIGN_PRINCIPLES.md` - Core insights about information landscape
- `docs/PHASE1_ROADMAP.md` - Detailed plan for epistemic agency
- `docs/MECHANISM_RECOVERY.md` - Full writeup of PCA analysis results
- `docs/TIME_DEPENDENT_ATTRITION.md` - Implementation notes for death model

**Quick wins:** Start with DESIGN_PRINCIPLES.md - can knock out in one session, high value

---

## Medium Priority

### 4. Additional Mechanism Recovery Analysis
**Goal:** Squeeze more insights from current Phase 0 dataset

**Context:** We have full dose-response + time-course data for 10 compounds × 2 cell lines × 5 morphology channels. Mine this dataset for additional biological insights before moving to Phase 1.

**Tasks:**
- [ ] **Temporal trajectory clustering (does attrition encode mechanism?)**
  - Plot each well's trajectory from 12h → 48h in morphology space
  - Cluster trajectories: do ER stressors show distinct paths vs mitochondrial?
  - Hypothesis: ER stress = gradual cumulative decline; DNA damage = sudden transition
  - Visualization: animated 2D PCA showing temporal evolution of stress responses
  - Code location: could extend `MechanismRecoveryPCAViz.tsx` to show time arrows

- [ ] **Feature importance analysis (which morphology channels matter most?)**
  - Train Random Forest classifier (stress_axis from 5 morphology features)
  - Extract feature importances: which organelles drive classification?
  - Hypothesis: ER/mito dominate early, nucleus dominates late (apoptosis)
  - Per-compound analysis: does tunicamycin signature rely heavily on morph_er?
  - Visualization: bar chart of feature importances per stress axis

- [ ] **Dose-response curve fitting for each stress axis**
  - Fit 4-parameter Hill equation: y = bottom + (top-bottom)/(1+(IC50/dose)^hill)
  - Extract IC50, Hill slope, max effect per compound-cellline-metric combo
  - Compare Hill slopes: steep = switch-like, shallow = graded response
  - Store fits in database for quick lookup
  - Visualization: already have dose-response plots, add fitted curve overlay + parameters

- [ ] **Identify which morphology channels and LDH scores show non-sigmoidal dose-response**
  - Fit Hill curve to each channel, compute R² goodness-of-fit
  - Flag curves with R² < 0.7 as "non-sigmoidal"
  - Look for: threshold responses (stress granules), biphasic (hormesis), U-shaped (hyperfusion→fragmentation)
  - Example expectations:
    - morph_rna (stress granules): threshold-like above critical stress level
    - morph_mito at low dose: potential hormetic response (mild stress → fusion)
    - viability_pct: should be sigmoidal (textbook)
  - Document patterns in `docs/NON_SIGMOIDAL_RESPONSES.md`

- [ ] **Cell-line vulnerability fingerprints (systematic A549 vs HepG2 comparison)**
  - For each compound, compare IC50 ratio (A549/HepG2)
  - Identify cell-line-specific vulnerabilities (e.g., HepG2 more sensitive to ER stress?)
  - Morphology comparison: same stress, different cell lines → similar or divergent patterns?
  - Heatmap: compounds (rows) × cell lines (cols), colored by IC50
  - Biological interpretation: does liver cell line show hepatotoxic signatures?

- [ ] **Sentinel drift analysis across plates/days/operators**
  - Sentinels = control wells (DMSO) monitoring batch effects
  - Already have SentinelTab showing SPC charts (mean ± 2σ control limits)
  - New analysis: test for temporal drift (linear regression of DMSO over time)
  - Spatial analysis: do edge wells differ from center wells? (plate effects)
  - Operator analysis: if multi-day runs, does baseline shift between sessions?
  - Result: validates simulation doesn't have spurious drift (should be stable)

**Why this matters:** Understand structure of existing data before Phase 1

**Non-sigmoidal analysis:** Some readouts may show threshold, biphasic, or hormetic responses instead of classic Hill curves. Characterizing these patterns reveals mechanism-specific signatures (e.g., stress granules appear suddenly above threshold, mitochondrial hyperfusion before fragmentation).

**Data access:** All in `cell_thalamus.db`, query via `/api/thalamus/designs/{design_id}/results`

---

### 5. Simulation Realism Improvements
**Goal:** Add biological realism without breaking separability

**Context:** Current simulation has unrealistically tight DMSO controls (CV ~0.1%). Real assays have 2-5% CV. Adding realistic noise helps Phase 1 agent learn robust strategies, but risks obscuring mechanism.

**Tasks:**
- [ ] **Implement control distribution jitter (2-3% CV on DMSO wells)**
  - Current: DMSO wells nearly identical (baseline = 100.0 for all)
  - Real assay: DMSO has normal distribution (mean=100, std=2-3)
  - Implementation: add Gaussian noise to baseline in `modeling.py`
  - Effect: sentinel charts show realistic variation, agent learns to handle noisy controls
  - Validation: check mid-dose separation ratio still >5.0 after adding noise

- [ ] **Dose-dependent morphology noise (higher CV at high stress)**
  - Hypothesis: dying cells show more variability (heterogeneous death timing)
  - Implementation: scale noise by stress level (low dose = 2% CV, high dose = 10% CV)
  - Biological rationale: adaptive responses coordinated, death responses stochastic
  - Code location: `generate_experimental_results()` in `modeling.py`
  - Test: does this make high-dose separation worse? (expected and desired)

- [ ] **Validate improvements preserve mechanism recovery metrics**
  - After adding noise, re-run mechanism recovery analysis
  - Target: mid-dose separation ratio should remain >5.0 (currently 5.372)
  - If separation drops below 3.0, noise is too high (obscures mechanism)
  - Document noise levels that maintain separability

- [ ] **Document trade-offs in `SIMULATION_IMPROVEMENTS.md`**
  - Noise improves realism but reduces statistical power
  - Agent learning benefit: learns to allocate more wells to noisy conditions
  - Trade-off: agent must balance exploration (get enough replicates) vs exploitation (sample informative doses)
  - Decision rule: add noise only if Phase 1 agent performs suspiciously well on unrealistic data

**Why this matters:** Prepare for Phase 2+ where noise structure becomes a feature

**Note:** Only implement if Phase 1 epistemic agent needs more realistic noise to learn proper strategies. If agent already struggles with current clean data, defer this.

**Testing protocol:**
1. Run baseline mechanism recovery (no noise)
2. Add DMSO jitter only, re-measure separation
3. Add dose-dependent noise, re-measure
4. Compare: noise impact on separation ratio vs agent learning benefit

---

## Low Priority / Future

### 6. Portfolio Optimization
**Goal:** Multi-objective experiment design (maximize info + minimize cost)

**Context:** Phase 1 agent maximizes information only. Real labs have budget constraints: reagent costs, plate space, imaging time. Phase 2 adds resource accounting.

**Tasks:**
- [ ] **Implement resource accounting (time, reagent costs, plate utilization)**
  - Track costs per well: compound cost (expensive drugs), cell cost, imaging time
  - Example: paclitaxel = $50/well, tunicamycin = $5/well
  - Plate utilization: 384-well plate has fixed geometry, can batch similar conditions
  - Imaging time: 5-channel fluorescence takes 2min/well (bottleneck)
  - Database schema: add `cost_per_well` column to experimental_results

- [ ] **Multi-objective optimization: separability vs cost**
  - Pareto frontier: trade-off between separation ratio (quality) and total cost
  - Agent objective: maximize (separation_ratio / total_cost) = info per dollar
  - Test: does agent learn to avoid expensive compounds when cheap ones give similar info?
  - Visualization: 2D scatter (cost vs separation), show Pareto-optimal designs

- [ ] **Test adaptive strategies (sequential allocation based on interim results)**
  - Current: agent allocates all wells upfront (batch design)
  - Adaptive: agent sees partial results, decides next batch dynamically
  - Example: "I see oxidative stress separates well, skip more oxidative compounds"
  - Implementation: multi-round game where agent allocates 96 wells at a time
  - Challenge: sequential designs harder to optimize, but more realistic

**Why this matters:** Phase 2+ real-world constraints

**Decision criteria:** Only implement after Phase 1 agent working. Don't prematurely optimize.

**Real-world application:** Drug screening campaigns have fixed budgets. This helps decide "test 10 compounds at 8 doses each" vs "test 20 compounds at 4 doses each".

---

### 7. Visualization Enhancements
**Goal:** Make dashboard even more useful for exploration

**Context:** Dashboard has core functionality. These are polish items for better UX and publication-ready figures.

**Tasks:**
- [ ] **Add temporal trajectory view (animate 12h→48h morphology changes)**
  - Extend PCA visualization in Mechanism Recovery tab
  - Show arrows from 12h position to 48h position for each well
  - Animation: smoothly interpolate between timepoints
  - Color by stress axis, thickness by dose
  - Insight: visualize "attrition trajectories" (ER stress moves gradually, DNA damage jumps)
  - Component: add to `MechanismRecoveryPCAViz.tsx`

- [ ] **Interactive dose-response curve viewer with IC50 annotations**
  - Already have dose-response plots in `DoseResponseTab.tsx`
  - Enhancement: add fitted Hill curve overlay (dashed line)
  - Annotate IC50 point with vertical line + label
  - Display curve parameters: IC50, Hill slope, Emax in tooltip
  - Click compound legend → show IC50 comparison table across cell lines
  - Export curve + parameters as CSV for Excel analysis

- [ ] **Plate heatmap showing spatial batch effects**
  - Extend PlateViewerTab with heatmap view
  - Show 96-well or 384-well plate layout
  - Color wells by metric value (viability, morphology score)
  - Overlay: edge wells highlighted (test for edge effects)
  - Analysis: compute edge vs center well statistics
  - Detect: "gradient effects" (left side different from right side)
  - Use case: validates simulation doesn't have spurious spatial patterns

- [ ] **Export mechanism recovery plots as publication-ready figures**
  - Add "Export" button to Mechanism Recovery tab
  - Save PCA plots as SVG (vector graphics for papers)
  - Export data as CSV: PC1, PC2, stress_axis, condition
  - Generate figure caption automatically from separation ratios
  - Publication-ready styling: larger fonts, 600 DPI, colorblind-friendly palette
  - Optional: export to matplotlib/seaborn for final tweaking

**Why this matters:** Nice-to-have for data exploration and presentations

**Priority:** Low because doesn't affect scientific conclusions, just makes things prettier. Do after Phase 1 agent working.

**Quick wins:** IC50 annotations easiest (already have curve fitting math), do that first if needed for presentations.

---

## Parking Lot (Not Yet)

**Context:** These add biological realism but don't enable new experiments or agent capabilities. Defer until Phase 3+ when core loop is working.

**Deferred items:**

- **Combination treatment modeling (synergy/antagonism)**
  - Two-drug interactions: synergistic (1+1=3) vs antagonistic (1+1=1)
  - Example: ER stress + proteasome inhibition = synergistic toxicity
  - Why defer: Phase 1 focuses on single-compound mechanism discovery first
  - Complexity: combinatorial explosion (10 compounds = 45 pairs)

- **Cell cycle synchronization simulation**
  - Model G1, S, G2, M phase distributions and progression
  - Compounds affect cells differently by phase (e.g., paclitaxel arrests mitosis)
  - Why defer: adds 4× complexity (track phase per cell), unclear if improves separability
  - Decision: implement only if Phase 2 agent needs this for temporal precision

- **Metabolic flux modeling**
  - Track glucose uptake, ATP production, lactate secretion (Warburg effect)
  - Mitochondrial compounds affect flux dynamics
  - Why defer: need ODE system for metabolism, high complexity
  - Alternative: approximate with "energy state" scalar variable first

- **Spatial morphology (pixel-level image generation)**
  - Generate actual microscopy images instead of feature vectors
  - Enables computer vision / deep learning approaches
  - Why defer: current feature-based approach working, images = 100× more data
  - Use case: Phase 4+ when transitioning to real microscopy data

- **Single-cell heterogeneity modeling**
  - Currently: well = average of 100-500 cells (population mean)
  - Enhancement: track individual cell states, capture variability
  - Example: 10% of cells die early, 90% adapt (bimodal distribution)
  - Why defer: adds stochasticity without clear epistemic benefit yet
  - Decision: add only if Phase 2 agent needs to reason about heterogeneity

**Rationale:** Complexity doesn't justify insight gain yet. Wait for Phase 3+.

**Review criteria:** Revisit parking lot when:
1. Phase 1 agent masters single-compound active learning
2. Transfer learning validates mechanism generalization
3. Real experimental data shows feature gaps in simulation

---

## Decision Criteria

**Work on it if:**
1. Enables Phase 1 epistemic agency
2. Tests if mechanism encodes generalizable knowledge
3. Documents hard-won insights for future phases

**Defer if:**
1. Adds complexity without new questions
2. Only matters for Phase 3+ edge cases
3. Can be approximated by existing features

**Never if:**
1. Breaks separability at mid-dose
2. Obscures where information lives
3. Just adds "realism" without enabling new experiments

---

## Next Session - Quick Start Guide

**Pick based on your goal:**

### Want to build something exciting? → **Phase 1 Epistemic Agency**
- Most challenging, most impactful
- Start with: design agent API endpoint (query simulation with budgets)
- Expected time: 2-3 sessions for basic agent, 5+ for RL version
- Prereq: comfortable with reinforcement learning or Bayesian optimization

### Want a quick win? → **Write Design Principles Doc**
- 1-2 hour task, high value for future work
- Captures hard-won insights before they're forgotten
- Create `docs/DESIGN_PRINCIPLES.md` synthesizing mechanism recovery findings
- Content ready: mid-dose optimal, 300× improvement factor, information landscape

### Want to validate the science? → **Transfer Learning Test**
- Proves mechanism signatures generalize to unseen compounds
- Start with: train Random Forest on 8 compounds, test on 2 held-out
- Expected time: 1 session (code + analysis)
- High impact if works: validates this is real biology, not simulation artifact

### Want to explore the data? → **Non-Sigmoidal Dose-Response Analysis**
- Identify morphology channels with threshold/biphasic responses
- Reveals mechanism-specific patterns (stress granules, mito fusion→fragmentation)
- Start with: fit Hill curves to all channels, flag low R²
- Expected time: 1 session
- Quick insight generation from existing data

### Want to polish the dashboard? → **Add IC50 Annotations**
- Easiest visualization enhancement
- Overlay fitted Hill curves on dose-response plots
- Display IC50, Hill slope, Emax parameters
- Expected time: <1 hour
- Nice for presentations/publications

---

## Context Quick Reference

**Where are we?**
- ✅ Phase 0 complete: proved simulation encodes mechanism (300× separation improvement)
- 🎯 Next: Phase 1 epistemic agency (agent learns experimental design)
- 📊 Data: 10 compounds × 2 cell lines × 5 morphology channels × dose/time series
- 🗄️ Storage: SQLite database `cell_thalamus.db`
- 🌐 API: FastAPI backend at `localhost:8000/api/thalamus`
- 💻 Frontend: React dashboard at `localhost:5173`

**Key files:**
- Simulation logic: `src/cell_os/modeling.py` (generate_experimental_results)
- Database: `src/cell_os/database/cell_thalamus_db.py`
- API endpoints: `src/cell_os/api/thalamus_api.py`
- Dashboard: `frontend/src/pages/CellThalamus/`
- Mechanism recovery viz: `frontend/src/pages/CellThalamus/components/MechanismRecoveryTab.tsx`

**Key insights to remember:**
- Mid-dose (0.5-2×IC50) at 12h = optimal mechanism visibility
- High-dose/late-time = death signature dominates (less informative)
- All-doses-mixed = classes collapse (separation 0.018 vs 5.372)
- Design principle: "information moves earlier in time and lower in dose"
