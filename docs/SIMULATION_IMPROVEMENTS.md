# Cell Thalamus Simulation Improvements

Future enhancements to increase biological realism without breaking identifiability.

---

## Implemented ✅

### 1. Time-Dependent Death Continuation (Dec 16, 2025)
**Problem:** 48h viability was too generous at high doses for ER/proteostasis stressors.
**Solution:** Added cumulative attrition for high stress (>IC50) at late timepoints.

**Attrition Rates:**
- ER stress: 40% (tunicamycin, thapsigargin → apocalyptic by 48h)
- Proteasome: 35% (MG132 → persistent toxicity)
- Oxidative: 15% (tBHQ, H2O2 → some adaptation possible)
- Mitochondrial: 10% (CCCP, oligomycin → early commitment dominates)
- DNA damage: 20% (etoposide → apoptosis cascade)
- Microtubule: 5% (paclitaxel, nocodazole → rapid commitment)

**Example:** Tunicamycin 1 µM in HepG2
- 12h: 44% viable (mid-dose stress)
- 48h: 10% viable (**34% attrition** → cumulative UPR failure)

**Result:** High-dose ER/proteostasis stress now shows single-digit viability at 48h, matching wet lab expectations.

---

## Planned (Second-Order Refinements)

### 2. Control Distribution (Not Urgent)
**Current:** Vehicle controls are exactly 100% viability (normalized reference point).
**Future:** Add biological jitter to controls: `100% ± ~2-3%` (plate-correlated noise).

**Why wait:**
- Current approach optimizes identifiability (clean origin for dose-response)
- Good for Phase 0 (learning separable axes)
- Adding jitter is a "realism" improvement, not a bug fix

**When to implement:**
- Phase 1+ when system starts reasoning about plate-to-plate variance
- When control stability becomes a biological question (not just normalization)

**Implementation sketch:**
```python
# Control viability with plate-correlated biological jitter
control_viability = np.random.normal(1.0, 0.02)  # 98-102% nominal
# But clamp normalization at 100% for display
normalized_viability = min(100.0, (sample_viability / control_viability) * 100)
```

### 3. Dose-Dependent Morphology Noise (Optional)
**Current:** Morphology CV is constant across all doses.
**Future:** Increase CV at high stress (dying cells are more heterogeneous).

**Why wait:**
- Current structure already shows separable axes
- Adding dose-dependent noise complicates PCA interpretation
- Not blocking any Phase 0-1 goals

**When to implement:**
- When modeling single-cell heterogeneity (Phase 2+)
- When trying to predict "how variable will this measurement be?"

### 4. Compound Interaction Effects (Future)
**Current:** Each compound acts independently (Hill equation).
**Future:** Model synergy/antagonism for combination treatments.

**Why wait:**
- Phase 0 is single-compound screening
- Interaction effects require factorial designs (10× more wells)
- Need baseline single-agent data first

**When to implement:**
- Phase 3+ combination screening
- When asking "does tunicamycin + CCCP kill more than additive?"

---

## Not Planned (Complexity vs Insight Trade-off)

### A. Cell Cycle Synchronization
**Idea:** Model G1/S/G2/M phase distributions and compound sensitivity.
**Why not:** Adds 4× state complexity for minimal identifiability gain. Current proliferation index captures the important biology (faster cycling = more sensitive to microtubule drugs).

### B. Metabolic Flux Modeling
**Idea:** Simulate ATP production, ROS generation, NADPH consumption.
**Why not:** Overkill for phenotypic screening. Current stress-axis categories already separate mitochondrial vs oxidative effects. Flux models are for mechanistic follow-up, not screening.

### C. Spatial Morphology Simulation
**Idea:** Generate actual Cell Painting images (pixel-level).
**Why not:** Current feature vectors (ER, Mito, Nucleus, Actin, RNA) capture the relevant biology. Image synthesis is computationally expensive and doesn't improve axis separability. Real images are available from Broad's BBBC datasets for validation.

---

## Decision Criteria

**Implement if:**
1. Improves biological realism **without breaking identifiability**
2. Addresses user feedback from real dataset inspection
3. Enables new Phase 0-2 questions

**Defer if:**
1. Adds complexity without improving axis separability
2. Only matters for edge cases (Phase 3+ questions)
3. Can be approximated by existing parameters

**Never if:**
1. Breaks monotonic dose-response structure
2. Makes mid-dose resolution worse
3. Only adds "realism" without enabling new questions

---

## Changelog

- **2025-12-16:** Added time-dependent death continuation (ER/proteostasis cumulative attrition)
- **2025-12-16:** Documented control distribution jitter as future improvement
