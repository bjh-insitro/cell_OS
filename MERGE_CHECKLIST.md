# Merge Checklist for Mitigation Implementation

## Pre-Merge Verification

### 1. Syntax and Compilation ✓
```bash
python3 -m py_compile src/cell_os/epistemic_agent/loop.py
python3 -m py_compile src/cell_os/epistemic_agent/beliefs/state.py
python3 -m py_compile src/cell_os/epistemic_agent/mitigation.py
```
Status: PASSED

### 2. File Changes Persisted ✓
```bash
git diff --stat src/cell_os/epistemic_agent/
```
Expected:
- loop.py: +151 lines (orchestration + guardrails)
- beliefs/state.py: +16 lines (TypeError + semantic contract)
- mitigation.py: NEW file
- schemas.py: +1 line (layout_seed)
- world.py: ~30 lines (layout seed support)

Status: VERIFIED

### 3. Run Regression Tests
```bash
# Core cycle invariants
pytest tests/integration/test_mitigation_cycle_invariants.py -xvs

# Expected: 3 tests pass
# - test_mitigation_uses_integer_cycles
# - test_beliefs_see_monotonic_integers
# - test_mitigation_cycle_sequence
```
Status: [ ] TODO before merge

### 4. Run Existing Integration Tests
```bash
# Ensure no breakage
pytest tests/integration/test_world_observation_determinism.py -xvs
pytest tests/integration/test_real_run_cycle_causality_and_determinism.py -xvs
```
Status: [ ] TODO before merge

### 5. Verify Log Files
Check that mitigation JSONL contains:
- Only integer cycle numbers
- No "1.5" or float patterns
- Proper structure: cycle_type, flagged_cycle, action, reward

```bash
# After running a test with mitigation
cat results/*/run_*_mitigation.jsonl | grep '"cycle"'
# Should see: "cycle": 0, "cycle": 1, etc. (no floats)
```
Status: [ ] TODO before merge

### 6. Check Platform Path Stability
```bash
# Ensure mitigation_file path is stable
grep "mitigation_file" src/cell_os/epistemic_agent/loop.py
# Should use: self.log_dir / f"{self.run_id}_mitigation.jsonl"
```
Status: ✓ VERIFIED

## Critical Invariants to Verify

1. [ ] Mitigation cycles are integers (no floats)
2. [ ] Cycles are strictly monotonic
3. [ ] `begin_cycle()` raises TypeError for non-int (not just assert)
4. [ ] Semantic contract documented in code comments
5. [ ] Regression tests exist and pass
6. [ ] Guardrails can't be disabled by -O flag

## Post-Merge Monitoring

After merge, watch for:
- Any temporal provenance errors in logs
- Float cycle numbers appearing in JSONL
- Assertion errors from begin_cycle()
- Non-monotonic cycle sequences

## Rollback Plan

If issues found:
1. Revert commit
2. Check: Did someone use `python -O`?
3. Check: Did beliefs see a float cycle?
4. Check: Did mitigation set pending but not clear it?

## Commit Message

```
Add closed-loop QC mitigation cycles with epistemic rewards and strict integer cycle invariants

Implements minimal closed-loop agent capability that responds to spatial QC flags
with mitigation actions (REPLATE/REPLICATE/NONE) and computes epistemic rewards
based on QC resolution.

[See COMMIT_MESSAGE.txt for full details]
```

## Sign-off

- [x] Code review: Self-reviewed with user guidance
- [x] Syntax verified
- [x] Guardrails in place
- [x] Semantic contract documented
- [ ] Tests pass (run before merge)
- [ ] No regressions (run before merge)

## Ready to Merge

Once all TODO items checked:
```bash
git add src/cell_os/epistemic_agent/
git add tests/integration/test_mitigation_cycle_invariants.py
git commit -F COMMIT_MESSAGE.txt
git push origin agent-accountability-spatial-qc
```

---

**The universe taught us manners about time. Ship it.**
