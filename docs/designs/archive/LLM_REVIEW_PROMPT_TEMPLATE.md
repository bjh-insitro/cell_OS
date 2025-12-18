# LLM Review Prompt Template

Use this template when feeding designs to an LLM (e.g., ChatGPT) for feedback.

## Prompt for Design Quality Feedback

```
I'm designing high-throughput screening experiments for cell biology. I need your feedback on this design.

**CONTEXT (Design Space):**
<paste contents of DESIGN_SPACE_SPECIFICATION.json>

**DESIGN REPORT (Current Design):**
<paste contents of design_report.json>

**QUESTIONS:**
1. Does this design satisfy the stated goals (identifiability, batch orthogonality, spatial scatter)?
2. Are there any red flags in the spatial dispersion metrics?
3. What would you change to improve the design?
4. Are the tradeoffs (per-cell-line shuffle making design "rigid") acceptable for Phase 0 goals?

**IMPORTANT CONSTRAINTS:**
- Phase 0 requires: fixed scaffold, position stability, batch orthogonality
- Spatial scatter MUST have bounding box area ≥ 40 (sequential fill ≈ 12 is BAD)
- Position = identity within cell line (same position across plates must be same condition)
- Cell lines are SEPARATE (no mixing on same plate)

Please analyze and provide feedback.
```

## Prompt for Parameter Suggestion

```
I'm designing high-throughput screening experiments for cell biology. I need your help choosing parameters.

**DESIGN SPACE:**
<paste contents of DESIGN_SPACE_SPECIFICATION.json>

**MY GOALS:**
- Test [describe compounds/mechanisms]
- Measure at [describe timepoints]
- Compare [describe cell lines]
- Stay within [describe constraints: plate count, budget, time]

**QUESTIONS:**
1. What parameter combination would you recommend?
2. How many plates will this require?
3. What are the tradeoffs I'm accepting?
4. Are there any invariants I'm likely to violate?

Please suggest a parameter set as JSON, following the structure in the specification.
```

## Prompt for Debugging Violations

```
My design failed validation with the following violations:

**VIOLATIONS:**
<paste violation list from validation certificate>

**DESIGN PARAMETERS:**
<paste parameters section from design_report.json>

**QUESTION:**
What did I do wrong? Which parameter choices caused these violations? How should I fix them?

**CONTEXT:**
<paste relevant sections of DESIGN_SPACE_SPECIFICATION.json>
```

## Example LLM Conversation

**User:**
```
I'm designing a Phase 0 experiment. Here's my current design:

DESIGN SPACE: <...paste DESIGN_SPACE_SPECIFICATION.json...>

CURRENT DESIGN: <...paste design_report.json...>

The design passes all invariants (0 violations), but I'm wondering:
1. Is avg bounding box area = 76.6 good enough? Specification says ≥40 is threshold.
2. Should I add a 72h timepoint? That would increase plates from 24 → 32.
3. Would per-plate shuffle be better than per-cell-line shuffle for future phases?
```

**Expected LLM Response:**
```
1. **Spatial dispersion (76.6):** Excellent. Way above threshold (40) and close to theoretical
   max (88 for 12 wells on 8×12 plate). Your compounds are well-scattered. Sequential fill
   would be ≈12, so you're 6x better than the bad baseline.

2. **Adding 72h timepoint:**
   - Pros: Better temporal resolution for late-onset effects
   - Cons: 33% more plates (24→32), 33% more time/cost
   - Critical: Condition multiset MUST match across all 4 timepoints (invariant enforces this)
   - Recommendation: Only add if you care about >48h dynamics. Most acute stress is visible by 48h.

3. **Per-plate vs per-cell-line shuffle:**
   - Current (per-cell-line): Position is fixed fingerprint within cell line. Good for Phase 0
     (calibration/identifiability), but carries plate-specific artifacts consistently.
   - Alternative (per-plate): Breaks position stability (triggers experimental_position_instability
     violation), but decorrelates position from plate history. Better for adaptive sampling phases.
   - Recommendation: Keep per-cell-line for Phase 0. Switch to per-plate in future phases when
     position-as-identity is less critical.
```

## Files You Need

1. **DESIGN_SPACE_SPECIFICATION.json** - Explains what parameters exist and what they mean (this is static, same for all designs)
2. **design_report.json** - Generated per design using `export_design_report.py` (this is specific to one design)
3. **This template** - Shows how to structure your prompts

## Workflow

```bash
# 1. Generate a design
python scripts/design_generator_phase0.py

# 2. Export design report
python scripts/export_design_report.py \
    data/designs/phase0_founder_v2_regenerated.json \
    data/design_reports/phase0_founder_v2_report.json

# 3. Open ChatGPT and paste:
#    - DESIGN_SPACE_SPECIFICATION.json (parameter reference)
#    - design_report.json (your specific design)
#    - Your questions

# 4. Get feedback and iterate
```

## Tips for Good LLM Feedback

1. **Be specific about goals** - Don't just ask "is this good?", ask "does this achieve X goal?"
2. **Include constraints** - Tell the LLM your plate count budget, time constraints, etc.
3. **Ask about tradeoffs** - "What am I giving up by choosing X over Y?"
4. **Request JSON output** - "Suggest parameters as JSON" gets you machine-readable responses
5. **Iterate** - Use LLM suggestions to generate new designs, then review those too

## Advanced: Using LLM to Generate Designs

```
PROMPT:
"Based on the design space specification, generate parameters for an experiment that:
- Tests oxidative stress compounds (tBHQ, H2O2, CCCP) on neurons (iPSC_NGN2)
- Measures at 3 timepoints (12h, 24h, 48h)
- Fits in 96-well plates
- Uses ≤20 plates total

Return parameters as JSON that I can feed to the generator."

EXPECTED OUTPUT:
{
  "cell_lines": ["iPSC_NGN2"],
  "compounds": ["tBHQ", "H2O2", "CCCP"],
  "doses": [0.3, 1.0, 3.0, 10.0, 30.0],
  "replicates": 2,
  "timepoints_h": [12.0, 24.0, 48.0],
  "days": [1, 2],
  "operators": ["Operator_A", "Operator_B"],
  "plate_format": 96,
  "design_seed": 42
}

Analysis:
- 3 compounds × 5 doses × 2 reps = 30 experimental wells
- 30 + 28 sentinels = 58 wells (fits 96-well)
- 1 cell line × 3 timepoints × 2 days × 2 operators = 12 plates ✓ (under 20 limit)
```
