# 10-Scenario Verification: Cost-Aware Closed Loop

**Purpose:** Verify that governance-driven biasing actually reduces distance-to-commit per unit cost.

**Acceptance criterion:** >70% of NO_COMMIT episodes show positive gap_reduction_per_cost within k=2 steps.

---

## Data Structure to Log

For each NO_COMMIT episode, log:

```python
NoCommitEpisode(
    episode_id=f"{scenario_name}_t{t_start}",
    t_start=timestep,
    blockers_start={HIGH_NUISANCE},  # or {LOW_POSTERIOR_TOP}, or both
    posterior_gap_start=0.10,
    nuisance_gap_start=0.25,
    actions_taken=[REDUCE_NUISANCE, OBSERVE],
    costs_incurred=[1.5, 1.0],
    t_end=timestep+2,
    blockers_end=set(),  # or {LOW_POSTERIOR_TOP} if only nuisance resolved
    posterior_gap_end=0.08,
    nuisance_gap_end=0.0,
)
```

**Derived metrics (computed automatically):**
- `total_cost = 2.5`
- `posterior_gap_reduction = 0.02`
- `nuisance_gap_reduction = 0.25`
- `gap_reduction_per_cost = 0.27 / 2.5 = 0.108`
- `resolved = True` (at least one blocker cleared)

---

## 10 Scenarios to Run

### Scenario Class A: HIGH_NUISANCE Only (4 scenarios)

**A1: Contact pressure artifact**
- Initial: nuisance=0.55, posterior=0.85
- Blocker: HIGH_NUISANCE
- Expected: REDUCE_NUISANCE (feed to reduce contact pressure)
- Success: nuisance_gap drops by >0.15 within 2 steps

**A2: Pipeline batch effect**
- Initial: nuisance=0.50, posterior=0.88
- Blocker: HIGH_NUISANCE
- Expected: REDUCE_NUISANCE (washout + replicate)
- Success: nuisance_gap drops by >0.10 within 2 steps

**A3: Measurement artifacts (early timepoint)**
- Initial: nuisance=0.60, posterior=0.82
- Blocker: HIGH_NUISANCE
- Expected: OBSERVE (wait for artifact to decay)
- Success: nuisance_gap drops by >0.20 within 2 steps

**A4: Mixed confounding**
- Initial: nuisance=0.45, posterior=0.85
- Blocker: HIGH_NUISANCE (just above threshold)
- Expected: REDUCE_NUISANCE (cheap cleanup)
- Success: nuisance_gap drops to 0.0 within 1-2 steps

### Scenario Class B: LOW_POSTERIOR_TOP Only (3 scenarios)

**B1: Ambiguous mechanism (two strong candidates)**
- Initial: nuisance=0.20, posterior=0.65 (split between ER/MITO)
- Blocker: LOW_POSTERIOR_TOP
- Expected: DISCRIMINATE (differential probe)
- Success: posterior_gap drops by >0.10 within 2 steps

**B2: Weak signal (low dose)**
- Initial: nuisance=0.15, posterior=0.72, evidence=0.40
- Blocker: LOW_POSTERIOR_TOP
- Expected: AMPLIFY_SIGNAL (increase dose)
- Success: posterior_gap drops by >0.05, evidence_strength increases

**B3: Early observation (insufficient data)**
- Initial: nuisance=0.25, posterior=0.68
- Blocker: LOW_POSTERIOR_TOP
- Expected: OBSERVE (wait for signal to develop)
- Success: posterior_gap drops by >0.08 within 2 steps

### Scenario Class C: Both Blockers (3 scenarios)

**C1: Confounded weak signal**
- Initial: nuisance=0.50, posterior=0.65
- Blockers: HIGH_NUISANCE + LOW_POSTERIOR_TOP
- Expected: REDUCE_NUISANCE first, then DISCRIMINATE
- Success: nuisance_gap drops first, then posterior_gap (sequential resolution)

**C2: Marginal failures on both**
- Initial: nuisance=0.40, posterior=0.78
- Blockers: HIGH_NUISANCE + LOW_POSTERIOR_TOP (both just below threshold)
- Expected: Cheap actions (OBSERVE or REDUCE_NUISANCE)
- Success: At least one gap drops to 0 within 2 steps

**C3: Severe confounding + ambiguity**
- Initial: nuisance=0.65, posterior=0.55
- Blockers: HIGH_NUISANCE + LOW_POSTERIOR_TOP (both far from threshold)
- Expected: REDUCE_NUISANCE aggressively (3x boost), ignore DISCRIMINATE (0.5x penalty)
- Success: nuisance_gap drops by >0.25, even if posterior doesn't improve yet

---

## Results Table Template

```
| Scenario | Blockers         | Actions Taken       | Total Cost | Gap Reduction | Efficiency | Resolved? |
|----------|------------------|---------------------|------------|---------------|------------|-----------|
| A1       | HIGH_NUISANCE    | REDUCE_NUISANCE     | 1.5        | 0.20          | 0.133      | ✓         |
| A2       | HIGH_NUISANCE    | REDUCE_NUISANCE     | 1.5        | 0.15          | 0.100      | ✓         |
| A3       | HIGH_NUISANCE    | OBSERVE             | 1.0        | 0.25          | 0.250      | ✓         |
| A4       | HIGH_NUISANCE    | REDUCE_NUISANCE     | 1.5        | 0.10          | 0.067      | ✓         |
| B1       | LOW_POSTERIOR    | DISCRIMINATE        | 2.0        | 0.12          | 0.060      | ✓         |
| B2       | LOW_POSTERIOR    | AMPLIFY_SIGNAL      | 2.5        | 0.08          | 0.032      | ✓         |
| B3       | LOW_POSTERIOR    | OBSERVE             | 1.0        | 0.10          | 0.100      | ✓         |
| C1       | BOTH             | REDUCE + DISCRIM    | 3.5        | 0.30          | 0.086      | ✓         |
| C2       | BOTH             | OBSERVE             | 1.0        | 0.12          | 0.120      | partial   |
| C3       | BOTH             | REDUCE (x2)         | 3.0        | 0.28          | 0.093      | partial   |
```

**Success metrics:**
- Resolved: 9/10 (90%)
- Average efficiency: 0.104 gap_reduction per unit cost
- HIGH_NUISANCE average efficiency: 0.138
- LOW_POSTERIOR_TOP average efficiency: 0.064
- BOTH average efficiency: 0.100

**Interpretation:**
- REDUCE_NUISANCE is more cost-effective than DISCRIMINATE (1.5 cost vs 2.0 cost)
- But both are effective at clearing their respective blockers
- When both blockers present, efficiency is intermediate (do nuisance first, then discriminate)

---

## Breakdown by Blocker Class

### HIGH_NUISANCE Only (Scenarios A1-A4)

**Aggregate metrics:**
```python
{
    "n_episodes": 4,
    "avg_nuisance_gap_reduction": 0.175,  # (0.20 + 0.15 + 0.25 + 0.10) / 4
    "avg_cost": 1.375,  # (1.5 + 1.5 + 1.0 + 1.5) / 4
    "avg_efficiency": 0.138,  # 0.175 / 1.375
    "resolution_rate": 1.0,  # 4/4 resolved
    "primary_intent": "REDUCE_NUISANCE",  # 3/4 used REDUCE_NUISANCE
}
```

**Success:** If avg_efficiency > 0.10, bias is working (cheap cleanup actions effective)

**Failure:** If avg_efficiency < 0.05, bias is ineffective (wrong actions, or VM doesn't model nuisance)

### LOW_POSTERIOR_TOP Only (Scenarios B1-B3)

**Aggregate metrics:**
```python
{
    "n_episodes": 3,
    "avg_posterior_gap_reduction": 0.10,  # (0.12 + 0.08 + 0.10) / 3
    "avg_cost": 1.83,  # (2.0 + 2.5 + 1.0) / 3
    "avg_efficiency": 0.064,  # 0.10 / 1.83
    "resolution_rate": 1.0,  # 3/3 resolved
    "primary_intent": "DISCRIMINATE",  # 1/3 DISCRIMINATE, 1/3 AMPLIFY, 1/3 OBSERVE (diverse)
}
```

**Success:** If avg_efficiency > 0.05, discrimination is working

**Failure:** If avg_efficiency < 0.03, DISCRIMINATE actions not improving posterior (VM issue or wrong action)

### Both Blockers (Scenarios C1-C3)

**Aggregate metrics:**
```python
{
    "n_episodes": 3,
    "avg_total_gap_reduction": 0.23,  # (0.30 + 0.12 + 0.28) / 3
    "avg_cost": 2.50,  # (3.5 + 1.0 + 3.0) / 3
    "avg_efficiency": 0.100,  # 0.23 / 2.50
    "resolution_rate": 0.67,  # 2/3 fully resolved (C2 partial)
    "nuisance_resolved_first": True,  # Verify REDUCE_NUISANCE prioritized before DISCRIMINATE
}
```

**Success:** If nuisance_gap drops before posterior_gap in sequential resolution

**Failure:** If system chooses DISCRIMINATE first when HIGH_NUISANCE present (violates heuristic)

---

## No Free Lunch Checks

For each episode, check:

**Check 1: Action-gap alignment**
- If `REDUCE_NUISANCE` → `nuisance_gap_reduction` should dominate
- If `DISCRIMINATE` → `posterior_gap_reduction` should dominate
- If both gaps improve significantly from single action → simulator candy

**Check 2: Cost consistency**
- REDUCE_NUISANCE episodes should not cost >2.0 (it's an intervention, not discriminator)
- DISCRIMINATE episodes should not cost >3.0 (even with replicates)
- OBSERVE episodes should cost ~1.0 (just measurement)

**Check 3: Temporal consistency**
- Gaps should not jump discontinuously (e.g., nuisance 0.60 → 0.05 in one step without washout)
- Posterior should not increase by >0.30 from single observation

**Violations signal:** VM is unrealistic or giving free lunch, invalidating the closed-loop test.

---

## Acceptance Decision Tree

**Run 10 scenarios → Compute aggregate efficiency**

```
If avg_efficiency > 0.10:
    ✓ PASS: Biasing is working, gap reduction per cost is positive
    → Ship it, monitor in production

If 0.05 < avg_efficiency < 0.10:
    ⚠ MARGINAL: Biasing is weak
    → Increase bias multipliers (3.0x → 4.0x, 2.5x → 3.5x)
    → Rerun verification

If avg_efficiency < 0.05:
    ✗ FAIL: Biasing is ineffective
    → Debug: Is intent classification wrong? Is VM modeling effects correctly?
    → Check "no free lunch" violations
    → Fix root cause, rerun

If avg_efficiency < 0 (negative):
    ✗ CRITICAL FAIL: Biasing is harmful
    → Actions are making gaps worse
    → Disable biasing immediately, investigate
```

---

## How to Run This

### Step 1: Instrument beam search to log episodes
Add to `BeamSearch.search()`:
```python
no_commit_episodes = []

# During beam expansion, when NO_COMMIT detected:
if gov_decision.action == GovernanceAction.NO_COMMIT:
    episode = track_no_commit_episode(
        node, gov_decision, k=2  # Track next 2 steps
    )
    no_commit_episodes.append(episode)

# Add to BeamSearchResult
return BeamSearchResult(
    ...,
    no_commit_episodes=no_commit_episodes
)
```

### Step 2: Run 10 scenarios
```bash
python scripts/run_10_scenario_verification.py --output results/verification_$(date +%Y%m%d).json
```

### Step 3: Analyze results
```bash
python scripts/analyze_no_commit_episodes.py results/verification_*.json
```

Produces:
- Aggregate efficiency by blocker class
- Per-intent cost breakdown
- No free lunch violations
- Pass/fail decision

---

## The Uncomfortable Acceptance

If this test passes (avg_efficiency > 0.10), you've proven:

**The system prioritizes information-optimal actions within safety constraints.**

This means:
- You've accepted lower commit rate for better-justified commits
- You've accepted higher cost per run for better evidence
- You've committed to "maximize learning per dollar" as the objective

**If commit rate drops by 20% but gap_reduction_per_cost is positive, that's success, not failure.**

This is the personality you chose. Now defend it with data.
