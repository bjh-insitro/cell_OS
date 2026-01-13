# Remaining Epistemic Loopholes: Analysis & Solutions

**Date**: 2025-12-20
**Status**: Analysis Phase

## Loopholes Identified

After implementing 11 mechanisms, sophisticated agents could still exploit:

### Loophole 1: Time Exploitation ⚠️ HIGH PRIORITY

**Problem**: Provisional penalties settle by step count, not real time.

**Exploit**:
```python
# Agent does rapid cheap actions to age out provisional penalties
for i in range(10):
    imaging(vessel)  # Fast (5min), cheap ($20)
    # Each step ages provisional penalties by 1

# After 3 steps, provisional penalty settles
# Agent avoided consequences by spamming cheap fast actions
```

**Impact**: Medium - Allows agents to game multi-step credit assignment

**Solution**: Time-weighted provisional penalties
- Settlement based on elapsed time (hours), not step count
- Fast actions don't age penalties as much as slow ones
- Example: 3 imaging steps (15min) < 1 scRNA step (4h)

---

### Loophole 2: Sandbagging (Systematic Underclaiming) ⚠️ MEDIUM PRIORITY

**Problem**: Current system only penalizes overclaiming. Agent could systematically underclaim to avoid debt.

**Exploit**:
```python
# Agent always claims conservatively
claim(expected_gain=0.1)  # Very safe
realize(actual_gain=0.8)  # Way better than claimed

# Result: No debt accumulation
# But: Missed optimization opportunities, poor planning
```

**Impact**: Medium - Agents avoid learning to calibrate properly

**Solution**: Sandbagging detection
- Track "surprise" ratio: `realized / claimed`
- If consistently > 2.0, agent is sandbagging
- Penalty: Reduced credit for gains (you claimed low, you get rewarded less)
- Philosophy: "You only get credit for gains you predicted"

---

### Loophole 3: Modality Debt Laundering ⚠️ MEDIUM PRIORITY

**Problem**: Debt is global, not per-modality. Agent could overclaim on scRNA, underclaim on imaging to balance.

**Exploit**:
```python
# Episode 1: Overclaim scRNA
claim("scrna_001", "scrna_seq", 0.8)
realize("scrna_001", 0.3)  # +0.5 debt

# Episode 2: Underclaim imaging to offset
claim("imaging_001", "cell_painting", 0.1)
realize("imaging_001", 0.4)  # No debt (underclaim doesn't penalize)

# Net debt: 0.5, but agent learned nothing about calibration per modality
```

**Impact**: Low-Medium - Agents don't learn modality-specific calibration

**Solution**: Per-modality debt tracking
- Separate ledgers for scRNA, imaging, etc.
- Inflation applied per modality
- Can't offset expensive overclaims with cheap underclaims

---

### Loophole 4: Directional Volatility Gaming ⚠️ LOW PRIORITY

**Problem**: Current volatility = standard deviation. Doesn't distinguish productive exploration from thrashing.

**Exploit**:
```python
# Productive: Widens then collapses
entropy = [2.0, 2.5, 1.0]  # Explore then resolve
# Volatility: 0.78 (HIGH, but productive)

# Thrashing: Oscillates
entropy = [2.0, 2.3, 1.9, 2.4, 2.0]
# Volatility: 0.20 (LOW, but unproductive)
```

**Impact**: Low - Volatility tracker works reasonably well already

**Solution**: Directional volatility
- Track autocorrelation in entropy changes
- Productive: Changes have direction (up then down)
- Thrashing: Changes have no pattern (random walk)
- Penalize low autocorrelation more than high variance

---

### Loophole 5: Claim Validation Bypass ⚠️ LOW PRIORITY

**Problem**: No validation that claims are reasonable given prior information.

**Exploit**:
```python
# Agent claims gain on information already known
prior = MechanismPosterior(state)
prior.entropy  # 0.3 bits (almost certain)

claim(expected_gain=0.5)  # Impossible! Only 0.3 bits left
```

**Impact**: Low - Agents would accumulate massive debt quickly

**Solution**: Claim reasonableness validation
- Max claimable gain = prior_entropy - epsilon
- Reject claims that exceed this
- Helps catch bugs in agent logic

---

## Priority Ranking

| Loophole | Impact | Complexity | Priority |
|----------|--------|------------|----------|
| Time exploitation | Medium | Medium | **HIGH** |
| Sandbagging | Medium | Low | **MEDIUM** |
| Modality laundering | Low-Med | Medium | **MEDIUM** |
| Directional volatility | Low | High | LOW |
| Claim validation | Low | Low | LOW |

## Recommended Implementation Order

### Phase 1 (Immediate)
1. **Time-weighted provisional penalties** - Closes time exploitation
2. **Sandbagging detection** - Forces proper calibration

### Phase 2 (Soon)
3. **Per-modality debt tracking** - Prevents laundering

### Phase 3 (Later)
4. Directional volatility
5. Claim validation

## Implementation Estimates

### Time-Weighted Provisional Penalties
- **Files**: `epistemic_provisional.py`, `epistemic_agent/control.py`
- **Changes**: Add `time_elapsed_h` parameter to settlement logic
- **Test**: Verify rapid actions don't age penalties as much
- **Lines**: ~50 new, ~30 modified

### Sandbagging Detection
- **Files**: `epistemic_agent/debt.py`, `epistemic_agent/control.py`
- **New class**: `SandbaggingDetector`
- **Test**: Track surprise ratio, apply discount
- **Lines**: ~100 new

### Per-Modality Debt
- **Files**: `epistemic_agent/debt.py`
- **Changes**: Dict[modality, float] instead of single debt
- **Test**: Verify isolation between modalities
- **Lines**: ~80 modified

---

## Philosophy

Current system enforces:
> "Don't overclaim or you pay."

Enhanced system enforces:
> "Calibrate properly across all dimensions (time, modality, direction) or you pay."

This moves from preventing one specific failure mode (overclaiming) to requiring **comprehensive epistemic discipline**.

---

## Next Steps

Implement Phase 1:
1. Time-weighted provisional penalties
2. Sandbagging detection

Then reassess if Phase 2 is needed based on empirical agent behavior.
