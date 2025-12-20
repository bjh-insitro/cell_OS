# Epistemic Charter

**Version**: 0.5.0 (Measurement Ladder)
**Last Updated**: 2025-12-18

## Core Principle

Build an autonomous cell biology system that treats **measurement trust as the primary object of learning**, and only allows biological claims to emerge when that trust has been **earned, recorded, and defended**.

We are building toward learning **causal biology** across many cell lines and compounds, while pretending we have **never seen a lab before**.

## The Seven Covenants

### 1. Assays Are Not Biology. They Are Instruments.

**What this means**: LDH, Cell Painting, and scRNA are measurement devices with different cost, noise, and epistemic power. Before any biological conclusion, the system must prove it understands the instrument.

**Code audit**:
- [ ] Each assay has independent gate tracking (`ldh_sigma_stable`, `cell_paint_sigma_stable`, `scrna_sigma_stable`)
- [ ] Gates track degrees of freedom, relative CI width, and metric source
- [ ] No biological template runs without earning its instrument gate first

**Violations to watch for**:
- Assuming measurements are "just true" without calibration
- Mixing assay reliability estimates across instruments
- Running experiments before proving measurement repeatability

---

### 2. Calibration Is Not a Setup Step. It Is the First Experiment.

**What this means**: The first thing the system ever learns is not "what does CCCP do," but "how repeatable is this measurement under DMSO."

**Code audit**:
- [ ] First cycle always runs baseline replicates (noise gate calibration)
- [ ] `choose_next()` forces calibration before biology via `must_calibrate` trigger
- [ ] Pay-for-calibration regime: no gate = abort or forced calibration

**Violations to watch for**:
- Templates that skip calibration in "setup mode"
- Hardcoded noise assumptions from literature
- Calibration as optional parameter instead of mandatory first step

---

### 3. Cheap Truth Gates Expensive Truth.

**What this means**: Economic logic enforces measurement ladder:
- LDH answers "is the system alive enough to interpret?"
- Cell Painting answers "is there structured phenotypic variation?"
- scRNA answers "what mechanism is responsible?"

You do not pay for the next layer until the previous layer has earned trust.

**Code audit**:
- [ ] Global enforcement loop forces LDH + CP before biology (`for assay in ["ldh", "cell_paint"]`)
- [ ] scRNA never forced globally (expensive, upgrade-only)
- [ ] `_required_gates_for_template()` defines ladder constraints per template
- [ ] Ladder rule: scRNA requires CP gate (`"scrna_upgrade_probe": {"cell_paint"}`)

**Violations to watch for**:
- scRNA added to global enforcement loop (breaks economic logic)
- Templates that bypass ladder by claiming no gate requirements
- Cost-agnostic calibration decisions

---

### 4. Knowledge and Action Are Separate.

**What this means**: Beliefs can update passively (shadow stats, proxy metrics). Actions are gated by policy. The system may *know something* without being *allowed to act on it*.

**Code audit**:
- [ ] scRNA shadow stats tracked (`scrna_df_total`, `scrna_rel_width`) but gate never earned with proxy
- [ ] `gate_shadow:scrna` events emitted with `"actionable": false`
- [ ] `scrna_metric_source = "proxy:noisy_morphology"` marks non-actionable data
- [ ] Policy validation (`_validate_template_selection`) blocks expensive actions regardless of knowledge

**Violations to watch for**:
- Shadow stats used to justify actions ("metrics look good, let's use them")
- Knowledge fields (rel_width, df_total) directly triggering actions
- Missing `metric_source` labeling on derived knowledge

---

### 5. Refusal Is a First-Class Scientific Act.

**What this means**: "I will not run this experiment because it would be epistemically invalid or economically unjustified" is as important as "I ran this experiment."

**Code audit**:
- [ ] Abort templates exist (`abort_insufficient_calibration_budget`, `abort_policy_violation`)
- [ ] Affordability checks before forcing calibration (fail-fast if can't afford)
- [ ] Decision receipts record abort reason, calibration_plan, attempted_template
- [ ] Policy boundaries enforced (`calibrate_scrna_baseline` requires `allow_expensive_calibration=True`)

**Violations to watch for**:
- Silently skipping experiments without recording why
- "Best effort" actions that exceed budget
- Missing provenance for blocked templates

---

### 6. Every Decision Must Have a Receipt.

**What this means**: For any action or non-action, you must be able to ask:
- Which gate was missing?
- Which policy enforced it?
- What evidence supported that decision?
- What alternative was blocked?

**Code audit**:
- [ ] `_set_last_decision()` called for every `choose_next()` return path
- [ ] Decision receipts include: `trigger`, `regime`, `gate_state`, `enforcement_layer`
- [ ] Enforcement overrides include: `blocked_template`, `missing_gates`, `calibration_plan`
- [ ] All returns go through `_finalize_selection()` choke point (policy → gates → decision)
- [ ] Split-brain contract enforced: if enforcement overrides, it must write receipt

**Violations to watch for**:
- Return paths that skip `_set_last_decision()`
- Missing `enforcement_layer` in forced calibration decisions
- Templates that bypass `_finalize_selection()`
- Decisions without `gate_state` provenance

---

### 7. We Optimize for Causal Discoverability, Not Throughput.

**What this means**: The goal is not to run many experiments. The goal is to run experiments such that, later, a causal story can be reconstructed without archaeology.

**Code audit**:
- [ ] Evidence ledger (`EvidenceEvent`) tracks belief changes with supporting conditions
- [ ] Decision ledger (`DecisionEvent`) tracks template selection with full candidate provenance
- [ ] Diagnostic ledger (`NoiseDiagnosticEvent`) tracks calibration progress across cycles
- [ ] Gate events (`gate_event:*`, `gate_loss:*`, `gate_shadow:*`) mark trust transitions
- [ ] All events include `cycle`, `supporting_conditions`, `note` fields

**Violations to watch for**:
- Beliefs updated without emitting events
- Missing `supporting_conditions` (which wells justified this claim?)
- Decisions without candidates list (what was considered?)
- Events without human-readable `note` field

---

## Audit Protocol

### Before Merging Any PR

1. **Does it change a decision path?**
   - Verify receipt is written via `_finalize_selection()` or enforcement
   - Check that `enforcement_layer` appears when applicable
   - Confirm abort paths include attempted_template provenance

2. **Does it add a new template?**
   - Define gate requirements in `_required_gates_for_template()`
   - Verify returns go through `_finalize_selection()`
   - Add test proving template is blocked when gates missing

3. **Does it add a new assay or measurement?**
   - Add independent gate fields (df_total, rel_width, sigma_stable, metric_source)
   - Implement `_update_assay_gates()` with proxy blocking if applicable
   - Emit `gate_event:*` when earned, `gate_shadow:*` if non-actionable
   - Add to `_get_gate_state()` for decision provenance

4. **Does it modify belief updates?**
   - Verify `_set()` is called to record evidence
   - Check that `supporting_conditions` list actual wells/conditions
   - Ensure `metric_source` is set explicitly (derived, not default)

5. **Does it change enforcement logic?**
   - Add test proving enforcement fires when expected
   - Verify `enforcement_layer` field is set correctly
   - Check invariant: enforcement must write receipt when overriding

### Red Flags (Immediate Rejection)

- ❌ Decisions without receipts
- ❌ Actions without gate checks
- ❌ Knowledge used as action justification (violates Covenant 4)
- ❌ Static defaults for `metric_source` (must be derived)
- ❌ Templates that bypass `_finalize_selection()`
- ❌ Calibration as optional instead of forced
- ❌ Biological claims before instrument trust earned

---

## Implementation Status

### ✅ Implemented (v0.5.0)

1. **Assay-specific gates**: LDH, Cell Painting, scRNA gates with independent tracking
2. **Measurement ladder**: CP required before scRNA, enforced via `_required_gates_for_template()`
3. **Pay-for-calibration regime**: Forced calibration before biology, abort if unaffordable
4. **Shadow stats**: scRNA tracked but not actionable (`gate_shadow:*` events)
5. **Policy boundaries**: `calibrate_scrna_baseline` requires explicit authorization
6. **Decision provenance**: `enforcement_layer` distinguishes global vs safety net
7. **Single choke point**: `_finalize_selection()` ensures all returns validated
8. **Split-brain contract**: Invariant checks when enforcement overrides

### 🚧 Partial (Needs Work)

1. **Upgrade triggers**: CP → scRNA upgrade disabled (TODO: requires real CP features + LDH viability)
2. **Real assay models**: All assays use `proxy:noisy_morphology` (TODO: implement real LDH, CP, scRNA)
3. **Cost model**: Wells-based budget only (TODO: add reagent costs, time costs)

### ❌ Not Yet Implemented

1. **Multi-objective scoring**: Currently simple fallback logic (TODO: Pareto frontier for calibration vs biology)
2. **Causal inference**: No mechanism discovery yet (TODO: requires real scRNA + structural models)
3. **Failure modes**: No handling of broken instruments, contamination, drift beyond thresholds

---

## How to Keep This Alive

1. **Link PRs to covenants**: Every significant change should cite which covenant it upholds or extends
2. **Audit quarterly**: Run through checklist with grep/tests, fix any violations before they ossify
3. **Update when reality changes**: If you discover a covenant is wrong, update the charter AND the code together
4. **Teach with examples**: When onboarding, walk through one violation of each covenant and show how code prevents it

---

## The One-Sentence Version

**Build an autonomous cell biology system that treats measurement trust as the primary object of learning, and only allows biological claims to emerge when that trust has been earned, recorded, and defended.**

If your change makes this sentence harder to defend, reconsider.
