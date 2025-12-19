# Morphology Readout Model

## Two-Component Architecture (Model B)

Structural morphology has **two independent components**:

### 1. Acute Compound Effects (Immediate)
- **Source:** Direct stress axis effects from compounds present
- **Dynamics:** Appears instantly when compound applied, disappears instantly when washed out
- **Location:** Applied in `cell_painting_assay()` lines 1790-1818
- **Formula:** `dose_effect = intensity * (dose^h) / (EC50^h + dose^h)`

### 2. Chronic Latent Effects (Persistent)
- **Source:** Accumulated dysfunction in latent states
- **Dynamics:** Builds up over hours (k_on), decays slowly after washout (k_off)
- **Location:** Applied in `cell_painting_assay()` lines 1847-1858
- **Formula:** `latent_effect = alpha * latent_state` (for each latent)

## Combined Structural Formula

```python
morph_struct[channel] = baseline[channel] * (1 + acute_compound_effect) * (1 + latent_effect)
```

### Example: Actin with Paclitaxel

**During compound exposure:**
```python
actin_struct = baseline_actin
               * (1 + stress_axis_effect_from_paclitaxel)  # Acute
               * (1 + 0.6 * transport_dysfunction)          # Chronic
```

**After washout:**
```python
actin_struct = baseline_actin
               * (1 + 0)  # Acute: compound removed, effect gone
               * (1 + 0.6 * transport_dysfunction)  # Chronic: latent persists
```

**Numerical example (from test):**
- Before washout (6h): actin_struct = 209.5 (baseline ~100, acute ~1.1×, chronic ~1.9×)
- After washout (6h+1min): actin_struct = 178.1 (baseline ~100, acute ~1.0×, chronic ~1.8×)
- Transport dysfunction: 0.808 → 0.807 (latent unchanged, decays slowly)

## Why Model B (Not Model A)?

**Model A (rejected):** Pure latent drives structure
```python
actin_struct = baseline * g(transport_dysfunction)
```
- Washout wouldn't change structure immediately
- No way to distinguish acute vs chronic signatures

**Model B (implemented):** Latent + acute drives structure
```python
actin_struct = baseline * g(compound_present) * h(latent_state)
```
- Washout removes acute component immediately
- Chronic component decays naturally via k_off
- Agent can learn temporal signatures (fast vs slow recovery)

## Consequences for Policy Learning

### 1. Washout Reveals Latent State
After washout, structural morphology reflects **only** the chronic latent component. This creates a diagnostic:
- Measure actin before washout → acute + chronic
- Washout
- Measure actin immediately after → chronic only
- Difference = acute component

### 2. Recovery Has Two Timescales
- **Acute recovery:** Instant (washout removes compound)
- **Chronic recovery:** Gradual (k_off decay of latent)

This prevents "washout = instant fix" policies.

### 3. Mechanism Hit Should Use Acute + Chronic
For reward functions, "mechanism engaged" should use the **full structural signature** (before washout), not just the latent:
```python
mechanism_hit = (actin_struct_12h / baseline_actin) >= 1.4
```

This rewards engaging the mechanism, not just building up dysfunction.

## Readout Function Ordering

**Critical ordering in `cell_painting_assay()`:**

1. Start with baseline (lines 1782-1788)
2. Apply acute compound effects (lines 1790-1818)
3. Apply chronic latent effects (lines 1847-1858)
4. **Copy to morph_struct** (line 1866) ← Structural features frozen here
5. Apply viability scaling (lines 1889-1903) → Measured features

**Invariant:** Washout does NOT directly modify latent states. Structure changes because the readout function reads from `vessel.compounds` (now empty) and `vessel.transport_dysfunction` (unchanged).

## Why This Matters

This is a **modeling choice with consequences**:
- It enables temporal credit assignment (acute vs chronic)
- It prevents "washout = magic fix" bugs
- It creates richer policy pressure (pulse dosing beats continuous)

**Design principle:** Washout removes compounds and adds costs. Structure changes because the readout function depends on compounds. This is observer independence, not a bug.
