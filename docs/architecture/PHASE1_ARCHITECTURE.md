# Phase 1: Epistemic Agency Architecture

**Last Updated:** December 18, 2025
**Status:** Design Phase
**Goal:** Build an agent that learns about its world from scratch, earning its beliefs through experiments

---

## Core Philosophy

**"Make the agent earn its beliefs."**

The agent should:
- Start knowing the **knobs** (cell line, compound, dose, time, assay), not the **biology**
- Discover that edge effects exist (not be told)
- Learn that mid-dose is optimal (not be told it's special)
- Separate instrument truth from biological truth under budget pressure
- Be allowed to be wrong and stubborn (this is learning!)

---

## Two Systems: World vs Scientist

### System 1: The World (Simulator)

**What it contains:**
- True biology (dose-response curves, stress pathways, temporal dynamics)
- True technical artifacts (edge effects, batch effects, well failures)
- Hidden structure the agent must discover

**Key property:** Deterministic given inputs, but agent doesn't see the source code

**Current implementation:** `standalone_cell_thalamus.py::simulate_well()`

---

### System 2: The Scientist (Agent)

**What it maintains:**
- **Belief state:** Probabilistic model of how the world works
- **Uncertainty:** What it doesn't know yet
- **Experiment history:** What it has observed
- **Budget:** Wells remaining

**Key property:** Updates beliefs from observations, proposes next experiments to reduce uncertainty

**Not yet implemented:** This is what we're building

---

## Agent Architecture: LLM Strategist + Bayesian Core

### Why Hybrid?

**LLM Component:**
- Writes hypotheses in natural language
- Chooses among experiment templates
- Provides narration ("I believe X, so I'll test Y")

**Bayesian Component:**
- Computes expected information gain rigorously
- Proposes exact allocations (doses, replicates)
- Updates posterior distributions

**Benefit:** Watchable reasoning + mathematical rigor

---

## The Clean Interface

### `RUN_EXPERIMENT(proposal) -> observations`

**Proposal Schema:**
```python
{
    'design_id': str,           # Unique ID for this experiment batch
    'hypothesis': str,          # Natural language: what is this testing?
    'wells': [
        {
            'cell_line': str,        # 'A549' or 'HepG2'
            'compound': str,         # Name from available inventory
            'dose_uM': float,        # Micromolar concentration
            'time_h': float,         # Hours post-treatment
            'assay': str,            # 'cell_painting' or 'ldh_cytotoxicity'
            'position_tag': str,     # 'edge' or 'center' or 'any'
        },
        # ... batch of 8-24 wells
    ],
    'budget_limit_wells': int,  # System rejects if over
}
```

**Observations Schema:**
```python
{
    'design_id': str,
    'summary_stats': [
        {
            'condition': str,        # Human-readable description
            'cell_line': str,
            'compound': str,
            'dose_uM': float,
            'time_h': float,
            'assay': str,
            'position_tag': str,
            'n_wells': int,
            'mean': float,           # Mean response (viability or morphology)
            'std': float,            # Standard deviation
            'sem': float,            # Standard error of mean
            'cv': float,             # Coefficient of variation
        },
        # ... one per unique condition
    ],
    'wells_spent': int,
    'budget_remaining': int,
    'flags': [str],              # QC warnings (edge bias detected, outliers, etc.)
}
```

**Key Design Decisions:**

1. **No literal well positions** (A01, B03, etc.) unless testing spatial strategies
   - Agent uses `position_tag` ('edge' vs 'center' vs 'any')
   - System handles allocation

2. **Summary stats only** (not raw well values initially)
   - Agent sees mean, std, n per condition
   - If it wants distributions, it can request more replicates

3. **No variance partitioning labels** (plate effect, day effect, etc.)
   - Agent must infer structure from data

4. **QC flags** provided (but agent must interpret)
   - "Edge wells show 12% lower signal"
   - "2/24 wells flagged as outliers"
   - Agent decides what to do with this info

---

## Belief State: What the Agent Believes

### Early Phase (Cycles 1-5): Learn the Measurement Process

**Belief Model 1: Technical Noise Structure**

```python
class TechnicalNoiseModel:
    """Bayesian model of observation noise."""

    # Hierarchical model:
    # y_obs = y_true + ε_edge + ε_batch + ε_well

    params = {
        'baseline_cv': Beta(a=2, b=50),      # Prior: ~2-5% CV
        'edge_bias': Normal(μ=0, σ=0.2),     # Prior: unknown if exists
        'batch_variance': HalfNormal(σ=0.05), # Prior: small but nonzero
    }

    def update(self, observations):
        """Update posterior given new data (MCMC or variational)."""
        pass

    def predict_uncertainty(self, n_replicates, position_tag):
        """Given n replicates, what SEM do I expect?"""
        pass
```

**Success Metric:** After ≤96 wells, estimate `baseline_cv` within 20% relative error

---

### Mid Phase (Cycles 6-15): Learn Biological Response

**Belief Model 2: Dose-Response Curves**

```python
class DoseResponseModel:
    """Parametric model of biological response."""

    # Per compound-cell_line pair:
    # y(dose) = bottom + (top - bottom) / (1 + (IC50 / dose)^hill)

    params = {
        'IC50': LogNormal(μ=log(1.0), σ=2.0),  # Prior: ~0.1-10 µM
        'hill': Normal(μ=2.0, σ=1.0),          # Prior: ~1-4
        'top': Normal(μ=100, σ=10),            # Prior: ~90-110% (healthy)
        'bottom': Normal(μ=0, σ=20),           # Prior: ~0-20% (dead)
    }

    def update(self, dose, viability):
        """Bayesian curve fitting."""
        pass

    def optimal_dose_for_info(self):
        """Which dose maximizes learning about IC50?"""
        # Hint: Around IC50, slope is steepest
        pass
```

**Success Metric:** Predict held-out conditions with <15% error

---

### Late Phase (Cycles 16-20): Learn Mechanism Structure

**Belief Model 3: Stress Class Embedding (Optional)**

```python
class MechanismModel:
    """Learns that morphology encodes stress classes."""

    # Only unlocked after enough dose-response data exists
    # Discovers PCA structure, separation ratios, etc.
    pass
```

---

## Acquisition Function: Where to Look Next?

### Expected Information Gain

**Question:** Which experiment reduces posterior uncertainty the most per well?

**Formula:**
```
EIG(experiment) = H[posterior | history] - E[ H[posterior | history + outcome] ]

where H = entropy
```

**Practical implementation:**
1. Sample 100 plausible outcomes from predictive distribution
2. For each outcome, compute posterior entropy
3. Average: this is expected future uncertainty
4. Pick experiment with largest reduction

---

### Candidate Generator: Menu of Experiments

**Agent doesn't design arbitrary experiments—chooses from templates:**

#### Template 1: Baseline Characterization
```python
{
    'name': 'baseline_replicates',
    'description': 'Measure DMSO control variability',
    'wells': [
        {'compound': 'DMSO', 'dose_uM': 0, 'time_h': 12, 'position_tag': 'center'},
        # ... n=12 replicates
    ],
    'expected_learning': 'Estimate baseline_cv',
}
```

#### Template 2: Edge vs Center Test
```python
{
    'name': 'edge_center_test',
    'description': 'Test if well position affects signal',
    'wells': [
        # 6 DMSO edge, 6 DMSO center
        # 6 mild stressor edge, 6 mild stressor center
    ],
    'expected_learning': 'Detect edge_bias (if exists)',
}
```

#### Template 3: Coarse Dose Ladder
```python
{
    'name': 'dose_sweep',
    'description': 'Find IC50 for one compound',
    'wells': [
        # 4 doses: [0.01, 0.1, 1.0, 10.0] µM × n=3 replicates
    ],
    'expected_learning': 'Estimate IC50, hill slope',
}
```

#### Template 4: Time Probe
```python
{
    'name': 'time_course',
    'description': 'Test if timing matters',
    'wells': [
        # One compound, one dose, timepoints [6, 12, 24, 48]h × n=2
    ],
    'expected_learning': 'Temporal dynamics (cumulative vs commitment)',
}
```

#### Template 5: Cross-Cell-Line Transfer
```python
{
    'name': 'cell_line_comparison',
    'description': 'Test if response generalizes',
    'wells': [
        # Same condition, both cell lines × n=3
    ],
    'expected_learning': 'Cell-line-specific sensitivity',
}
```

---

## Learning Trajectory (Expected)

### Cycle 1-2: "What is the noise floor?"

**Hypothesis:** "I don't know if measurements are noisy or clean."

**Experiment:** Baseline replicates (16 DMSO wells, 12h, center)

**Observation:** Mean ≈ 100%, CV ≈ 2.5%

**Update:** "Measurements have ~2.5% noise. I need n≥3 for good estimates."

**Surprise:** None (this is just calibration)

---

### Cycle 3: "Does position matter?"

**Hypothesis:** "Position might affect signal (evaporation, temperature)."

**Experiment:** Edge vs center test (6+6 DMSO, 6+6 mild stressor)

**Observation:** Edge wells 12% lower signal on average

**Update:** "Edge bias exists! I should avoid edges or correct for it."

**Surprise:** Strong effect size (if agent didn't expect this)

---

### Cycle 4-6: "What dose kills cells?"

**Hypothesis:** "Compounds are toxic, but I don't know how much."

**Experiment:** Dose sweep (tunicamycin at [0.01, 0.1, 1.0, 10.0] µM)

**Observation:** Sigmoid curve, IC50 ≈ 0.3 µM

**Update:** "IC50 concept learned. Responses are smooth sigmoids."

**Surprise:** Smoothness (not threshold)

---

### Cycle 7-10: "Is mid-dose special?"

**Hypothesis:** "Maybe mechanism is visible at certain doses?"

**Experiment:** Morphology at low/mid/high doses for 3 compounds

**Observation:** Mid-dose shows diverse morphology, high-dose converges

**Update:** "High-dose looks the same for everything. Mid-dose is informative."

**Surprise:** Convergence at high dose (death signature discovery)

---

### Cycle 11-15: "Does timing matter?"

**Hypothesis:** "Maybe early timepoints capture different biology?"

**Experiment:** Time course (mid-dose tunicamycin at 6/12/24/48h)

**Observation:** Progressive toxicity, but morphology clearest at 12h

**Update:** "12h is mechanism window, 48h is just more death."

**Surprise:** Information moves earlier in time

---

### Cycle 16-20: "Can I generalize?"

**Hypothesis:** "If I learned ER stress on tunicamycin, does it work on thapsigargin?"

**Experiment:** Test held-out compound from same stress class

**Observation:** Similar morphology signature, validation works

**Update:** "Stress classes are real. I can transfer learning."

**Surprise:** Generalization works (validates world model)

---

## Success Criteria (Quantitative, Not Vibes)

### Criterion 1: Calibration Competence
- **Metric:** Estimate `baseline_cv` within 20% relative error
- **Budget:** ≤96 wells
- **Baseline:** Random sampling → ~40% error

### Criterion 2: Sample Efficiency
- **Metric:** Predict held-out conditions with <15% MSE
- **Budget:** <384 wells
- **Baseline:** Uniform sampling → ~25% MSE

### Criterion 3: Discovery of Mid-Dose Window
- **Metric:** Agent allocates >60% of morphology budget to 0.5-2×IC50 range by end
- **Budget:** Full campaign (384 wells)
- **Baseline:** Uniform → 33% allocation

### Criterion 4: Edge Effect Detection
- **Metric:** Agent detects edge bias with AUROC >0.8 or Bayes Factor >10
- **Budget:** ≤48 wells
- **Baseline:** No detection (assumes uniform)

### Criterion 5: Transfer Learning
- **Metric:** Predict held-out compound from same stress class with <20% error
- **Budget:** Test phase (separate from training)
- **Baseline:** No transfer → ~50% error

---

## Two Uncomfortable Questions (Answered)

### Q1: Should the agent be allowed to be wrong in a stubborn way?

**Answer:** YES.

If we hand-hold it with prompts when it makes "dumb" choices, we're just watching ourselves. The learning is in the mistakes.

**Example:**
- Agent wastes 48 wells on pure DMSO replicates (over-cautious)
- We watch it learn that n=16 doesn't gain much over n=8
- This is GOOD (learned sample sizing)

**Constraint:** Budget is finite, so waste is punished naturally

---

### Q2: Are we okay with "wasteful" experiments if EIG is high?

**Answer:** YES.

Pure replication might seem wasteful, but if posterior uncertainty about noise is high, it's actually optimal.

**Example:**
- Agent runs 24 DMSO replicates to nail down edge_bias
- Seems wasteful (it's just controls!)
- But if edge_bias is large and uncorrected, all future experiments are biased
- This is GOOD (calibration before measurement)

**Principle:** Information gain includes learning about the instrument, not just biology

---

## Implementation Phases

### Phase 1a: World Interface (Week 1)
- [ ] Create `ExperimentalSystem` class wrapping `simulate_well()`
- [ ] Implement `RUN_EXPERIMENT()` with proposal schema
- [ ] Return summary stats (not raw wells)
- [ ] Add QC flags (edge bias, outliers, failures)

### Phase 1b: Belief Models (Week 1-2)
- [ ] `TechnicalNoiseModel` (Bayesian linear model)
- [ ] `DoseResponseModel` (parametric sigmoid)
- [ ] Update functions (MCMC or variational inference)

### Phase 1c: Acquisition Function (Week 2)
- [ ] Expected information gain computation
- [ ] Monte Carlo rollouts over candidate experiments
- [ ] Candidate generator (5 templates)

### Phase 1d: LLM Strategist (Week 2-3)
- [ ] Prompt engineering for hypothesis generation
- [ ] Template selection logic
- [ ] Narration logging ("I believe X, so I'll test Y")

### Phase 1e: Full Loop (Week 3)
- [ ] Run 20-30 cycles autonomously
- [ ] Log belief updates, surprises, decisions
- [ ] Evaluate against success criteria

---

## File Structure

```
src/cell_os/epistemic_agent/
├── __init__.py
├── world.py                    # ExperimentalSystem (wraps simulate_well)
├── beliefs.py                  # TechnicalNoiseModel, DoseResponseModel
├── acquisition.py              # Expected information gain
├── candidates.py               # Experiment templates
├── strategist.py               # LLM component
└── loop.py                     # Main orchestration

scripts/
└── run_epistemic_agent.py      # Entry point for watching the movie

tests/
└── test_epistemic_agent.py     # Success criteria tests
```

---

## The Movie We Want to Watch

**Act 1: Humility (Cycles 1-5)**
- Agent realizes it knows nothing
- Runs boring calibration experiments
- Learns the measurement process is noisy
- Discovers edge effects exist

**Act 2: Exploration (Cycles 6-15)**
- Agent tries different doses, times, compounds
- Discovers dose-response curves are smooth sigmoids
- Stumbles on mid-dose informativeness by accident
- Realizes high-dose everything looks the same

**Act 3: Exploitation (Cycles 16-20)**
- Agent focuses budget on mid-dose 12h (discovered, not told)
- Tests generalization to held-out compounds
- Validates that stress classes transfer
- Achieves separation >4.0 with <384 wells

**Finale:**
- Agent writes summary: "Here's what I learned about this world"
- We compare to Phase 0 human-designed principles
- Success = agent discovered the same insights autonomously

---

## Next Immediate Steps

1. **Read current interface:** Review `standalone_cell_thalamus.py::simulate_well()` signature
2. **Map to clean API:** Create `world.py::RUN_EXPERIMENT()` wrapper
3. **Skeleton belief model:** Implement `TechnicalNoiseModel` with dummy posteriors
4. **First candidate:** Implement "baseline_replicates" template
5. **Run Cycle 0:** Agent proposes calibration, we execute, return results

**Question for you:** Should I start implementing `world.py` now, or do you want to refine the design first?
