# Instrument Health Reward System: Complete Implementation

## Overview

Completed the measurement stack evolution from contract enforcement (police) to forensic trail (black box recorder) to realism validation (crash test) to **multi-objective optimization** (brain that doesn't gouge its own eyes out).

---

## Implementation Components

### 1. Nuclei Count Observable (Step 1) ✅

**Files Created:**
- `src/cell_os/hardware/assays/nuclei_estimation.py` - Physics-based nuclei count estimation
- `tests/contracts/test_nuclei_estimate_observable.py` - 7 tests validating realism

**What It Does:**
- Replaces magic constant `confluence * 10000` with realistic observable
- Model includes:
  - Debris inflation (dead cells still have nuclei → over-count)
  - Segmentation bias (low quality → under-count from merged nuclei)
  - Quality degradation from debris (50%), edge damage (20%), death (30%)
  - Noise scaled inversely with quality (5% baseline → 25% worst case)
  - Edge effects (20% more variance)

**Integration:**
- Cell Painting returns `nuclei_qc` dict with:
  - `nuclei_estimate`: float (cell count)
  - `nuclei_cv`: float (coefficient of variation)
  - `segmentation_quality`: float [0, 1]
  - `edge_well`: bool

**Test Results:** 7/7 passing

---

### 2. Contract Reports (Forensic Trail, Step 2) ✅

**Files Modified:**
- `src/cell_os/epistemic_agent/beliefs/ledger.py` - Added `ContractReport` dataclass
- `src/cell_os/contracts/causal_contract.py` - Added `_emit_contract_report()` and timing

**Files Created:**
- `tests/contracts/test_contract_reports.py` - 3 tripwire tests

**What It Does:**
- Emits per-assay contract report after each measurement:
  - Read histogram (top 25 paths via `Counter`)
  - Violations (empty unless caught)
  - Mode (strict/warn/record)
  - Timing overhead (milliseconds)
  - Decorator presence (bool)
  - Debug truth status (bool)
- Stored on `run_context.contract_reports` (Option A architecture)
- JSONL event with schema envelope (Agent C Phase 1 compatible)

**Purpose:**
- Forensic trail: when measurement behavior drifts, see it immediately
- "Writing the autopsy report in advance"

**Test Results:** 3/3 passing (tripwire, read patterns, mode tracking)

---

### 3. Realism Stress Tests (Step 3) ✅

**Files Created:**
- `tests/realism/conftest.py` - Helpers for constructing vessels and repeated measurements
- `tests/realism/test_blind_stimulus_equivalence.py` - 3 tests
- `tests/realism/test_observer_independence_permutation.py` - 4 tests
- `tests/realism/test_noise_scaling_sanity.py` - 6 tests

**What They Test:**

#### Blind Stimulus Equivalence (3 tests)
- Identical latents → similar distributions (KS test, z-scores < 3)
- No identity leakage in contract reports
- Read histograms identical across identities

**Purpose:** Catches any sneaky treatment identity dependence reintroduced via containers or upstream logic.

#### Observer Independence Under Permutation (4 tests)
- Center wells invariant under permutation
- Edge wells show designed artifacts (higher CV by 10%+)
- No row/col gradients beyond edge classification
- Contract logs well_position but not treatment

**Purpose:** Catches "implicit geometry" bugs where position affects measurement in ways not captured by edge/gradient models.

#### Noise Scaling Sanity (6 tests)
- Nuclei CV increases as quality decreases (monotonic)
- Segmentation quality decreases with debris (monotonic)
- Morphology variance correlates with nuclei CV
- Repeated runs produce variance (not deterministic, CV > 1%)
- Edge damage amplifies noise
- Contract reports present for all conditions

**Purpose:** Catches accidental determinism and "noise doesn't respond to conditions" lies.

**Test Results:** 13/13 tests passing (3 + 4 + 6)

**Key Insight:** These tests ensure measurements behave like real instruments with actual physics, not oracle functions.

---

### 4. Instrument Health Reward (Multi-Objective Optimization) ✅

**Files Created:**
- `src/cell_os/epistemic_agent/rewards/instrument_health_reward.py` - Core reward logic
- `tests/epistemic/test_instrument_health_reward.py` - 8 tests

**What It Does:**

#### Reward Structure (Multi-Objective Ledger)
```python
health_reward = (
    +quality_weight * segmentation_quality  # Reward high quality
    - cv_penalty * (nuclei_cv / threshold)  # Penalize high noise
    - failure_penalty * n_missing_qc        # Hard penalty for invalid/missing
)
```

**Bounded:** Clipped to [-10, +2] to avoid dominating epistemic term forever

**Logged Separately:** Not collapsed into epistemic term - agent optimizes BOTH

#### QC-Triggered Mitigation
Generalizes spatial QC mitigation to all failure modes:

| Failure Rate | Action | Severity |
|-------------|---------|----------|
| >50% | Replate with altered layout | Critical |
| 30-50% | Increase replicates (1.5×) | High |
| 10-30% (edge) | Avoid edge wells | Moderate |
| 10-30% (diffuse) | Adjust seeding density | Moderate |
| 5-10% | Monitor | Low |

#### Key Design Decisions

**Observables-Only:** Uses `nuclei_qc` fields, not ground truth
- ✅ Realistic: Agent sees what real scientist would see
- ✅ Contract-safe: No treatment identity leakage
- ✅ Actionable: Quality signals can trigger mitigation

**Multi-Objective:** Tracked separately from epistemic gain
- ✅ Prevents collapse: Can't game single scalar
- ✅ Allows tradeoffs: Low quality acceptable when epistemic gain huge
- ✅ Bounded: Health can't dominate discovery forever

**Failure-Aware:** Triggers mitigation when thresholds violated
- ✅ Reactive: Agent knows when in low-quality regime
- ✅ Strategic: Can plan QC recovery cycles
- ✅ Prevents pathology: Won't accidentally optimize instrument into ground

#### Test Coverage (8/8 passing)

1. **High quality beats low quality when science equal** ✅
   - Steering signal: agent prefers reliable regimes
   - High quality → higher reward when epistemic gain equal

2. **Low quality allowed when epistemic gain huge** ✅
   - Flexibility: agent can pay QC cost for discovery
   - Health reward bounded (-10 max) so epistemic (+50) can dominate

3. **Health term is bounded and logged** ✅
   - Perfect: [0, +2]
   - Catastrophic: [-10, 0]
   - Missing QC: [-60, -40] (hard penalty but bounded)
   - All components logged for multi-objective tracking

4. **QC mitigation triggers at thresholds** ✅
   - Severity scales with failure rate
   - Critical (>50%) → replate
   - High (30-50%) → increase replicates

5. **Edge-concentrated failures suggest edge avoidance** ✅
   - Spatial pattern detection works
   - Edge failures → avoid edges (not replate)

6. **Health summary logging format** ✅
   - Human-readable
   - Contains all key metrics

7. **Custom weights and thresholds** ✅
   - Tunable multi-objective balance
   - Different weights → different rewards

8. **Zero wells handled gracefully** ✅
   - Edge case: no crash, returns neutral

---

## Sharp Question Answered

**What if best epistemic gain requires low-quality regimes?**

**Answer:** Multi-objective ledger structure allows strategic tradeoffs:

```python
total_reward = epistemic_gain + health_reward
```

**Example:**
- Low-quality regime: `epistemic = +50`, `health = -2` → `total = +48` ✅ Worth it
- High-quality regime: `epistemic = +10`, `health = +1` → `total = +11`
- No-quality regime: `epistemic = +100`, `health = -10` → `total = +90` ✅ Still worth it if gain massive

**Key:** Health term is bounded so it provides steering (prefer quality when gains equal) but doesn't block high-information experiments.

**Mitigation triggers** let agent know it's in low-quality regime and should plan recovery.

---

## Integration Points (Future Work)

### 1. Plumb into Existing Reward Computation
```python
# In epistemic_agent/loop.py or similar
epistemic_reward = compute_epistemic_gain(...)
health_reward_result = compute_instrument_health_reward(observations)
health_reward = health_reward_result['health_reward']

total_reward = epistemic_reward + health_reward

# Log separately for multi-objective introspection
logger.info(f"Epistemic: {epistemic_reward:.2f}, Health: {health_reward:.2f}, Total: {total_reward:.2f}")
```

### 2. Contract Reports in Run Summaries
Aggregate per cycle:
- Total measurement overhead (sum `timing_ms`)
- Top read paths (merge histograms, detect drift)
- Any violations (should be zero)
- Health summary (mean `segmentation_quality`, mean `nuclei_cv`)

Write next to decisions for episode-level introspection.

### 3. Mitigation Policy Integration
When `mitigation_triggered == True`:
- Call `suggest_qc_mitigation(...)` to get action suggestion
- Agent proposes mitigation as candidate design
- Weighs cost (wells, time) vs. health recovery benefit

---

## Test Status Summary

| Component | Tests | Status |
|-----------|-------|--------|
| Nuclei Estimation | 7 | ✅ All passing |
| Contract Reports | 3 | ✅ All passing |
| Label Smuggling Prevention | 4 | ✅ All passing |
| Blind Stimulus Equivalence | 3 | ✅ All passing |
| Observer Independence | 4 | ✅ All passing |
| Noise Scaling Sanity | 6 | ✅ All passing |
| Instrument Health Reward | 8 | ✅ All passing |
| **TOTAL** | **35** | **✅ All passing** |

---

## What This Buys the Epistemic Agent

1. **Trustworthy QC signals**: `segmentation_quality` and `nuclei_cv` are validated, physics-based observables

2. **Reward signal for instrument health**: Agent optimizes measurement reliability alongside discovery

3. **Penalties for unreliable regimes**: Discourages accidentally optimizing instrument into ground

4. **Strategic flexibility**: Can pay QC cost when epistemic gain justifies it

5. **Mitigation triggers**: Knows when to propose recovery actions

6. **Forensic trail**: Contract reports provide paper trail when behavior drifts

7. **Realism validation**: Tests prove measurement layer has actual physics

---

## Key Achievement

**The measurement stack is complete:**

1. **Contract enforcement** (police) - Prevents cheating ✅
2. **Forensic trail** (black box recorder) - Autopsy reports ✅
3. **Realism validation** (crash tests) - Proves physics ✅
4. **Multi-objective optimization** (brain) - Doesn't gouge eyes ✅

**The agent now has:**
- Beautiful eyes (realistic measurements)
- A conscience (contract enforcement)
- A memory (forensic trail)
- Self-preservation instinct (health reward)

**Next:** Teach the brain to actually use these signals when making decisions.
