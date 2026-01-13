# CellPaintingChannel Enum: Translation Kill #3

**Date:** 2025-12-21
**Status:** ✅ SHIPPED
**Commit message:** `core: introduce CellPaintingChannel enum for channel identity`

---

## What Changed

### The Problem

Channel names had multiple variants with no normalization:
- `'nucleus'` vs `'DNA'` vs `'nuclei'`
- `'er'` vs `'ER'` vs `'endoplasmic_reticulum'`
- `'mito'` vs `'mitochondria'` vs `'Mitochondria'`
- No distinction between channel identity and feature names

This led to:
- String comparison fragility
- Mixing channel identity with feature extraction
- No way to enumerate valid channels
- Ambiguity in cross-modal reasoning

### The Solution

**Channel is an identity. Features are projections OF that identity.**

```python
class CellPaintingChannel(Enum):
    """Channel identity, not feature name."""
    NUCLEUS = "nucleus"
    ER = "er"
    MITO = "mito"
    ACTIN = "actin"
    AGP = "agp"

    @property
    def display_name(self) -> str:
        return "DNA / Nucleus"  # Biological context

    @classmethod
    def from_string(cls, s: str) -> "CellPaintingChannel":
        """Normalize any legacy variant."""
```

**Features are derived FROM channels:**
```python
channel = CellPaintingChannel.NUCLEUS
feature_name = f"{channel.short_name}_intensity"  # "nucleus_intensity"
```

**NOT:** `CellPaintingChannel.NUCLEUS_INTENSITY` (mixes layers)

---

## Files Created/Modified

### 1. `src/cell_os/core/cell_painting_channel.py` (NEW - 153 lines)

Canonical channel enum with:

```python
class CellPaintingChannel(Enum):
    # Five standard channels
    NUCLEUS = "nucleus"  # DNA stain
    ER = "er"            # Endoplasmic reticulum
    MITO = "mito"        # Mitochondria
    ACTIN = "actin"      # Cytoskeleton
    AGP = "agp"          # Golgi / Plasma membrane

    @property
    def display_name(self) -> str:
        """Human-readable name with biological context."""
        return "DNA / Nucleus"  # etc.

    @property
    def short_name(self) -> str:
        """Short name for compact display (matches enum value)."""
        return self.value

    @classmethod
    def from_string(cls, s: str) -> "CellPaintingChannel":
        """Normalize legacy strings (case-insensitive).

        Normalization map:
        - "nucleus", "DNA", "nuclei" → NUCLEUS
        - "er", "ER", "endoplasmic_reticulum" → ER
        - "mito", "mitochondria" → MITO
        - "actin" → ACTIN
        - "agp", "golgi", "rna" → AGP
        """

    @classmethod
    def all_channels(cls) -> list["CellPaintingChannel"]:
        """Return all five channels in canonical order."""
```

**Key features:**
- Channel identity, not feature names
- Normalization in one place
- Display names with biological context
- `all_channels()` for iteration

### 2. `tests/unit/test_channel_semantics.py` (NEW - 210 lines)

Semantic teeth tests:

```python
def test_channel_normalization():
    """All variants must normalize correctly."""
    assert CellPaintingChannel.from_string("nucleus") == CellPaintingChannel.NUCLEUS
    assert CellPaintingChannel.from_string("DNA") == CellPaintingChannel.NUCLEUS
    # etc.

def test_channel_identity_not_feature_name():
    """Channels are identities, not feature names.

    Channel: CellPaintingChannel.NUCLEUS (identity)
    Feature: "nucleus_intensity" (projection)

    Do NOT create NUCLEUS_INTENSITY enum member.
    """

def test_feature_dict_should_use_channel_enum():
    """Feature dicts should be keyed by CellPaintingChannel."""
    features = {
        CellPaintingChannel.NUCLEUS: 1.0,
        CellPaintingChannel.ER: 0.98,
    }
```

### 3. `src/cell_os/core/__init__.py` (MODIFIED)

Exported CellPaintingChannel:

```python
from .cell_painting_channel import CellPaintingChannel

__all__ = [..., 'CellPaintingChannel']
```

### 4. `docs/CANONICAL_MODEL_RULES.md` (MODIFIED)

Added rule for channel identity:

```markdown
### Channel Identity
- **Canonical:** `CellPaintingChannel` enum for channel identity
- **Meaning:** Channel is an identity (NUCLEUS, ER, MITO), NOT a feature name
- **Features:** Derived FROM channels (e.g., `f"{channel.short_name}_intensity"`)
- **Banned:** Raw strings (`'nucleus'`, `'DNA'`, etc.) in canonical types
- **Banned:** Feature names in enum (e.g., `NUCLEUS_INTENSITY` - mixes layers)
```

---

## What This Unlocks

### 1. **Channel Identity is Explicit**

**Before:**
```python
channel = "nucleus"  # Could mean identity OR feature name
feature = "nucleus_intensity"  # Same prefix, but different concept
```

**After:**
```python
channel = CellPaintingChannel.NUCLEUS  # Identity (enum)
feature = f"{channel.short_name}_intensity"  # Feature (derived string)
```

### 2. **Normalization in One Place**

**Before:**
```python
# In file A
if channel.lower() == "nucleus":

# In file B
if channel == "DNA":

# In file C
if channel in ["nucleus", "dna", "nuclei"]:
```

**After:**
```python
# Everywhere
channel = CellPaintingChannel.from_string(channel_string)
```

### 3. **Enumeration**

**Before:**
```python
channels = ["nucleus", "er", "mito", "actin", "rna"]  # Hardcoded lists
```

**After:**
```python
channels = CellPaintingChannel.all_channels()  # Canonical list
```

### 4. **Type-Safe Feature Dictionaries**

**Before:**
```python
features = {
    "nucleus": 1.0,  # String key (fragile)
    "dna": 0.98,     # Different variant won't match
}
```

**After:**
```python
features = {
    CellPaintingChannel.NUCLEUS: 1.0,  # Enum key (type-safe)
    CellPaintingChannel.ER: 0.98,
}
```

### 5. **Display vs Internal**

**Before:**
```python
print(f"Channel: {channel}")  # "nucleus" (not informative)
```

**After:**
```python
print(f"Channel: {channel.display_name}")  # "DNA / Nucleus" (clear)
```

---

## Key Design Decision: Identity vs Feature

### ✓ **Correct:** Channel is identity, features are projections

```python
# Channel identity
channel = CellPaintingChannel.NUCLEUS

# Features derived from identity
features = {
    f"{channel.short_name}_intensity": 1.0,
    f"{channel.short_name}_texture": 0.5,
    f"{channel.short_name}_area": 2.0,
}
# Result: {"nucleus_intensity": 1.0, "nucleus_texture": 0.5, ...}
```

### ❌ **Wrong:** Mixing identity with features in enum

```python
# DO NOT DO THIS
class CellPaintingChannel(Enum):
    NUCLEUS = "nucleus"
    NUCLEUS_INTENSITY = "nucleus_intensity"  # ❌ Feature, not identity
    NUCLEUS_TEXTURE = "nucleus_texture"      # ❌ Feature, not identity
```

**Why this is wrong:**
- Mixing layers (identity vs projection)
- Explosion of enum members (5 channels × N features = huge enum)
- Features can't be composed programmatically
- Mechanism signatures become rigid

**The right pattern:**
- Channel = identity (5 enum members)
- Features = derived strings (programmatic)
- Feature extraction = function of channel

---

## Testing

### Unit Tests
```bash
$ python3 tests/unit/test_channel_semantics.py
✓ All channel semantic teeth tests passed
✓ CellPaintingChannel enum is canonical
✓ String variants normalized via from_string()
✓ Channel identity != feature name
✓ No raw channel strings in canonical paths
```

### Integration Test
```bash
$ python3 [integration test]
[1/5] Normalization...
      ✓ All variants normalize correctly

[2/5] Display names...
      nucleus    → DNA / Nucleus
      er         → Endoplasmic Reticulum
      mito       → Mitochondria
      actin      → Actin / Cytoskeleton
      agp        → Golgi / Plasma Membrane

[3/5] Channel identity vs feature names...
      Channel identity: nucleus
      Derived features: ['nucleus_intensity', 'nucleus_texture']
      ✓ Features are projections OF channel

[4/5] Enum iteration...
      5 channels: ['nucleus', 'er', 'mito', 'actin', 'agp']

[5/5] Type safety...
      Dict keyed by enum: 3 entries

✓ CellPaintingChannel working end-to-end
```

---

## Migration Impact

### Breaking Changes

**None.** This is additive.

Old code still uses strings. New code should use `CellPaintingChannel`.

Future work: Update aggregation code to use channel enum for feature dictionaries.

### Files Changed: 4
- ✅ Created: `core/cell_painting_channel.py` (153 lines)
- ✅ Created: `tests/unit/test_channel_semantics.py` (210 lines)
- ✅ Modified: `core/__init__.py` (export CellPaintingChannel)
- ✅ Modified: `docs/CANONICAL_MODEL_RULES.md` (added channel rule)

### Lines Changed: ~370 added
**Net:** Channel identity + semantic teeth + constitution update

---

## Normalization Map

All variants (case-insensitive):

| Input String | Canonical CellPaintingChannel |
|-------------|-------------------------------|
| `nucleus`, `DNA`, `nuclei` | `CellPaintingChannel.NUCLEUS` |
| `er`, `ER`, `endoplasmic_reticulum` | `CellPaintingChannel.ER` |
| `mito`, `mitochondria`, `Mitochondria` | `CellPaintingChannel.MITO` |
| `actin`, `Actin` | `CellPaintingChannel.ACTIN` |
| `agp`, `AGP`, `golgi`, `rna` | `CellPaintingChannel.AGP` |

**Note:** `rna` normalizes to AGP because some legacy code uses 'rna' to refer to the AGP/Golgi channel.

---

## Usage Examples

### Converting Legacy Strings

```python
from cell_os.core import CellPaintingChannel

# Normalize legacy strings
ch1 = CellPaintingChannel.from_string("nucleus")
ch2 = CellPaintingChannel.from_string("DNA")      # Different variant
ch3 = CellPaintingChannel.from_string("nuclei")   # Another variant

assert ch1 == ch2 == ch3 == CellPaintingChannel.NUCLEUS
```

### Creating Feature Names

```python
# Channel is identity
channel = CellPaintingChannel.NUCLEUS

# Derive feature names
feature_names = [
    f"{channel.short_name}_intensity",
    f"{channel.short_name}_texture",
    f"{channel.short_name}_area",
]
# Result: ["nucleus_intensity", "nucleus_texture", "nucleus_area"]
```

### Type-Safe Feature Dictionaries

```python
# Feature dict keyed by channel enum
features_by_channel = {
    CellPaintingChannel.NUCLEUS: 1.0,
    CellPaintingChannel.ER: 0.98,
    CellPaintingChannel.MITO: 1.02,
}

# Access is type-safe
nucleus_signal = features_by_channel[CellPaintingChannel.NUCLEUS]
```

### Display Names

```python
# For logging/UI
for channel in CellPaintingChannel.all_channels():
    print(f"{channel.short_name}: {channel.display_name}")

# Output:
# nucleus: DNA / Nucleus
# er: Endoplasmic Reticulum
# mito: Mitochondria
# actin: Actin / Cytoskeleton
# agp: Golgi / Plasma Membrane
```

---

## Adding New Channels

If Cell Painting evolves to include new channels:

1. Add to `CellPaintingChannel` enum:
   ```python
   class CellPaintingChannel(Enum):
       # Existing members...
       LIPID_DROPLET = "lipid_droplet"
   ```

2. Add display name:
   ```python
   _DISPLAY_NAMES = {
       # ...
       CellPaintingChannel.LIPID_DROPLET: "Lipid Droplets",
   }
   ```

3. Add to normalization map:
   ```python
   _NORMALIZATION_MAP = {
       # ...
       "lipid_droplet": cls.LIPID_DROPLET,
       "lipid": cls.LIPID_DROPLET,
   }
   ```

4. Update `all_channels()` if needed (currently returns all enum members)

5. Update semantic teeth test

---

## Next Translation Kills

Translation kills in order of leverage:

1. ✅ Time semantics (`observation_time_h`) - DONE
2. ✅ Assay strings (`AssayType` enum) - DONE
3. ✅ Channel identity (`CellPaintingChannel` enum) - DONE
4. **Next:** Position semantics OR decision objects (see "The Fork" below)

---

## The Fork in the Road

With time, assay, and channel canonical, we've stabilized the **axes of observation**.

Two paths forward:

### Path A: Position Semantics
- Make `SpatialLocation` real (used in aggregation, not just storage)
- Remove `position_tag` → `well_id` → `position_tag` circus
- Clean execution and aggregation boundaries
- **Touches:** World, aggregation, maybe simulation

### Path B: Decision Objects
- Kill `last_decision_event` side channel
- Make decisions first-class returned objects
- Clean epistemic provenance
- **Touches:** Agent policy, loop, ledgers

**Both are important.**
**Only one touches simulator boundary** (Position).

Your call which to kill next.

---

## Verification

Run the tests:
```bash
# Semantic teeth
python3 tests/unit/test_channel_semantics.py

# Integration
python3 [integration test code]
```

Expected output:
```
✓ All channel semantic teeth tests passed
✓ CellPaintingChannel enum is canonical
✓ String variants normalized via from_string()
✓ Channel identity != feature name

✓ CellPaintingChannel working end-to-end
✓ Channel identity is canonical
✓ Features are projections, not identities
```

---

## Summary

**What we built:** A canonical `CellPaintingChannel` enum that represents channel identity (not features).

**What we killed:** Channel string ambiguity. Raw channel strings must be normalized.

**What we gained:**
- Channel identity is explicit (enum, not string)
- Features are projections OF channels (programmatic)
- Type-safe feature dictionaries
- Enumeration of valid channels
- Foundation for cross-modal reasoning

**Key principle:** Channel is an identity. Features are derived FROM channels.

**Lines of code:** +370, including tests and constitution update.

**Time to implement:** ~30 minutes.

**Leverage:** Stabilizes observation axes (time, assay, channel). Enables clean cross-modal reasoning.

---

**Translation Kills Complete: 3/3 of observation axes**

1. ✅ `observation_time_h` - When we observe
2. ✅ `AssayType` - How we observe
3. ✅ `CellPaintingChannel` - What we observe (for Cell Painting)

The ontology is taking shape. String ambiguity can't spread anymore.

*"Channel is an identity. Features are projections. Never mix them."*
