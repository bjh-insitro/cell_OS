---
description: POSH Simulation Refactoring Plan
---

# POSH Cell Painting Simulation - Refactoring Plan

**Created:** 2025-12-02  
**Status:** Draft  
**Priority:** High

---

## Executive Summary

The POSH simulation has grown to include state-of-the-art Cell Painting features (channel-first simulation, embeddings, MoA classification, digital cell viewer). However, the codebase needs refactoring to improve maintainability, testability, and performance.

**Key Metrics:**
- `tab_campaign_posh.py`: 2,046 lines (should be <500)
- `posh_screen_wrapper.py`: 757 lines (manageable, but has dead code)
- Test coverage: 0% (critical functions untested)
- Magic numbers: ~30+ hardcoded values

---

## Phase 1: Quick Wins (High Impact, Low Effort)
**Estimated Time:** 2-3 hours  
**Goal:** Clean up technical debt without breaking functionality

### 1.1 Remove Dead Code
**File:** `src/cell_os/simulation/posh_screen_wrapper.py`

- [ ] Delete `_get_treatment_raw_measurement_effects()` (lines 394-455)
  - This function is no longer called after channel-first refactor
  - Verify no external dependencies
  
- [ ] Delete `_get_cell_line_baseline()` (lines 326-391)
  - Replaced by `_get_channel_baseline_intensities()`
  - Check for any lingering references

**Acceptance Criteria:**
- Simulation runs without errors
- All tests pass (once written)
- File size reduced by ~150 lines

---

### 1.2 Extract Magic Numbers to Constants
**File:** `src/cell_os/simulation/posh_screen_wrapper.py`

Create a configuration section at the top:

```python
# ===================================================================
# SIMULATION CONFIGURATION
# ===================================================================

# Channel normalization values (typical saturation points)
CHANNEL_MAX_VALUES = {
    "Hoechst": 45000,   # Nuclear DNA staining saturation
    "ConA": 25000,      # ER marker saturation
    "Phalloidin": 20000,  # Actin staining saturation
    "WGA": 18000,       # Golgi/membrane marker saturation
    "MitoProbe": 50000, # Mitochondrial probe saturation
}

# Cell line-specific nuclear sizes (µm²)
NUCLEAR_SIZE_RANGES = {
    "U2OS": (120, 200),
    "A549": (90, 150),
    "HepG2": (80, 130),
    "iPSC": (60, 110),
}

# Embedding configuration
EMBEDDING_DIMENSIONS = 128
EMBEDDING_PROJECTION_METHOD = "random_projection"  # or "pca"

# MoA classification thresholds
MOA_ALIGNMENT_THRESHOLD = 0.3  # Cosine similarity threshold
```

**Files to Update:**
- `posh_screen_wrapper.py`: Use constants in functions
- `tab_campaign_posh.py`: Import and use `CHANNEL_MAX_VALUES` in Digital Cell Viewer

**Acceptance Criteria:**
- All magic numbers replaced with named constants
- Constants documented with units and biological meaning
- No behavioral changes

---

### 1.3 Add Caching to Expensive Operations
**File:** `dashboard_app/pages/tab_campaign_posh.py`

```python
@st.cache_data
def generate_embeddings_cached(
    raw_measurements: pd.DataFrame,
    channel_intensities: pd.DataFrame,
    random_seed: int
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Cached wrapper for embedding generation."""
    df_combined = pd.merge(channel_intensities, raw_measurements, on="Gene")
    return _generate_embeddings(df_combined, random_seed=random_seed)
```

**Acceptance Criteria:**
- Switching between features doesn't regenerate embeddings
- Performance improvement measurable (>50% faster on feature switch)

---

## Phase 2: Architectural Refactoring (Medium Effort)
**Estimated Time:** 1-2 days  
**Goal:** Improve code organization and separation of concerns

### 2.1 Split Dashboard into Modules
**Current:** `dashboard_app/pages/tab_campaign_posh.py` (2,046 lines)  
**Target:** Multiple focused modules (<300 lines each)

**New Structure:**
```
dashboard_app/pages/tab_campaign_posh/
├── __init__.py                      # Exports render_posh_campaign_manager()
├── main.py                          # Main orchestration (200 lines)
├── config.py                        # UI configuration, defaults
├── visualization/
│   ├── __init__.py
│   ├── volcano_plot.py              # Volcano plot tab (150 lines)
│   ├── hit_list.py                  # Hit list tab (100 lines)
│   ├── raw_measurements.py          # Raw measurements tab (200 lines)
│   ├── channel_intensities.py       # Channel tab + Digital Cell Viewer (250 lines)
│   ├── embeddings.py                # Embeddings + MoA tab (300 lines)
│   └── operations.py                # Operations tab (150 lines)
├── components/
│   ├── digital_cell_viewer.py       # Synthetic cell renderer (150 lines)
│   └── moa_classifier.py            # MoA classification logic (100 lines)
└── utils/
    └── data_processing.py           # Helper functions
```

**Migration Steps:**
1. Create directory structure
2. Extract volcano plot to `visualization/volcano_plot.py`
3. Extract embeddings to `visualization/embeddings.py`
4. Extract Digital Cell Viewer to `components/digital_cell_viewer.py`
5. Extract MoA logic to `components/moa_classifier.py`
6. Update `main.py` to import and orchestrate
7. Update `__init__.py` to maintain backward compatibility

**Acceptance Criteria:**
- Each module <300 lines
- Clear separation of concerns
- No duplicate code
- All functionality preserved
- Dashboard loads without errors

---

### 2.2 Move MoA Classification to Simulation Layer
**Current:** MoA logic in dashboard (lines 1274-1380)  
**Target:** Simulation layer with dashboard just displaying results

**New Function in `posh_screen_wrapper.py`:**
```python
def classify_mechanism_of_action(
    embeddings: pd.DataFrame,
    hit_genes: List[str],
    control_genes: List[str],
    alignment_threshold: float = MOA_ALIGNMENT_THRESHOLD
) -> pd.DataFrame:
    """
    Classify hits by mechanism of action using embedding space geometry.
    
    Args:
        embeddings: High-dimensional embeddings (128-d)
        hit_genes: List of hit gene names
        control_genes: List of control gene names
        alignment_threshold: Cosine similarity threshold for classification
        
    Returns:
        DataFrame with columns: Gene, MoA, Alignment, Magnitude, Color
    """
    # ... implementation ...
```

**Update `POSHScreenResult`:**
```python
@dataclass
class POSHScreenResult:
    # ... existing fields ...
    moa_classification: pd.DataFrame  # NEW: MoA results
```

**Update `simulate_posh_screen()`:**
```python
# After embedding generation
if not hit_list.empty:
    moa_results = classify_mechanism_of_action(
        embeddings=df_embeddings,
        hit_genes=hit_list["Gene"].tolist(),
        control_genes=control_genes
    )
else:
    moa_results = pd.DataFrame()
```

**Acceptance Criteria:**
- MoA classification runs in simulation
- Dashboard just displays pre-computed results
- Logic testable independently
- Performance unchanged or improved

---

### 2.3 Extract Digital Cell Viewer to Visualization Module
**Current:** Matplotlib code embedded in dashboard  
**Target:** Reusable component

**New File:** `src/cell_os/visualization/synthetic_cell.py`

```python
class SyntheticCellRenderer:
    """Renders synthetic composite images of cells from channel intensities."""
    
    def __init__(self, channel_max_values: Dict[str, float] = CHANNEL_MAX_VALUES):
        self.channel_max = channel_max_values
        
    def render(
        self, 
        channel_data: Dict[str, float],
        figsize: Tuple[int, int] = (6, 6)
    ) -> plt.Figure:
        """
        Generate synthetic cell image.
        
        Args:
            channel_data: Dict with keys: Hoechst, ConA, Phalloidin, WGA, MitoProbe
            figsize: Figure size in inches
            
        Returns:
            Matplotlib Figure object
        """
        # ... implementation ...
```

**Usage in Dashboard:**
```python
from cell_os.visualization.synthetic_cell import SyntheticCellRenderer

renderer = SyntheticCellRenderer()
fig = renderer.render(gene_data.to_dict())
st.pyplot(fig)
```

**Acceptance Criteria:**
- Renderer works standalone (can be used in notebooks)
- Configurable colors, sizes, layout
- Unit testable
- Dashboard integration seamless

---

### 2.4 Architecture Decision: One Page vs Multiple Pages
**Question:** Should we split `tab_campaign_posh.py` into multiple separate Streamlit pages?

**Answer:** **NO - Keep as ONE page with modular structure**

**Rationale:**

**✅ Keep as Single Page (Recommended):**
```
POSH Campaign Sim (single page with tabs)
├── Configuration (inputs)
├── Volcano Plot (tab)
├── Hit List (tab)
├── Raw Measurements (tab)
├── Channel Intensities (tab)
├── Embeddings (tab)
└── Operations (tab)
```

**Benefits:**
- **Shared state**: All tabs access same simulation results via `st.session_state`
- **Better UX**: User sees all results in one place with tabs
- **Faster navigation**: No page reloads between views
- **Logical flow**: Configure → Run → Analyze in one workflow
- **Easier debugging**: All related code in one namespace

**❌ Don't Split into Multiple Pages:**
```
├── POSH: Configuration
├── POSH: Run Simulation
├── POSH: Results Analysis
└── POSH: Advanced Analysis
```

**Problems:**
- State management complexity (passing data between pages)
- User confusion (which page am I on?)
- More navigation clicks
- Duplicate configuration UI
- Harder to maintain workflow coherence

**Implementation:**
- Use Phase 2.1 approach (modular structure within single page)
- Each tab's logic in separate module
- Main page orchestrates tabs
- Shared utilities in `utils/`

**Exception:**
If POSH grows to include fundamentally different workflows (e.g., "POSH Design" vs "POSH Analysis"), then consider separate pages. But for now, the current workflow is cohesive.

**Acceptance Criteria:**
- Single page with clean tab structure
- Each tab module <300 lines
- Fast tab switching (<0.5s)
- Clear visual hierarchy

---

## Phase 3: Quality & Robustness (Long-term)
**Estimated Time:** 3-5 days  
**Goal:** Production-ready code with tests and documentation

### 3.1 Add Comprehensive Type Hints
**Target Files:**
- `posh_screen_wrapper.py`
- All new modules from Phase 2

**Example:**
```python
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

def _segment_nucleus_from_hoechst(
    hoechst_intensity: float, 
    cell_line: str
) -> Dict[str, float]:
    """
    Returns:
        Dict with keys:
            - Nucleus_Area: float (µm²)
            - Nucleus_Perimeter: float (µm)
            - Nucleus_Mean_Intensity: float (AFU)
            - Nucleus_Form_Factor: float (0-1)
            - Nucleus_Eccentricity: float (0-1)
    """
```

**Tools:**
- Run `mypy` for type checking
- Add to CI/CD pipeline

**Acceptance Criteria:**
- All public functions have type hints
- `mypy --strict` passes
- Return types documented

---

### 3.2 Write Unit Tests
**Target Coverage:** 80%+

**Priority Test Files:**
```
tests/unit/simulation/
├── test_posh_screen_wrapper.py
│   ├── test_get_channel_baseline_intensities()
│   ├── test_apply_treatment_to_channels()
│   ├── test_segment_nucleus_from_hoechst()
│   ├── test_segment_mitochondria_from_mitoprobe()
│   ├── test_generate_embeddings()
│   └── test_classify_mechanism_of_action()
├── test_synthetic_cell_renderer.py
└── test_moa_classifier.py
```

**Example Test:**
```python
def test_segment_nucleus_from_hoechst_u2os():
    """Test nuclear segmentation for U2OS cells."""
    # Baseline intensity
    result = _segment_nucleus_from_hoechst(28000, "U2OS")
    
    assert 120 <= result["Nucleus_Area"] <= 200  # U2OS range
    assert 0.4 <= result["Nucleus_Form_Factor"] <= 0.95
    assert result["Nucleus_Mean_Intensity"] == 28000
    
    # High intensity (condensation)
    result_condensed = _segment_nucleus_from_hoechst(40000, "U2OS")
    assert result_condensed["Nucleus_Area"] < result["Nucleus_Area"]
```

**Acceptance Criteria:**
- All critical functions tested
- Edge cases covered
- Tests run in <10 seconds
- CI/CD integration

---

### 3.3 Externalize Configuration
**Current:** Hardcoded in Python  
**Target:** YAML/JSON configuration files

**New File:** `config/cell_painting_simulation.yaml`

```yaml
# Cell Painting Simulation Configuration

# Channel baseline intensities (AFU)
channel_baselines:
  U2OS:
    Hoechst: 28000
    ConA: 15000
    Phalloidin: 12000
    WGA: 10000
    MitoProbe: 35000
  A549:
    Hoechst: 27000
    ConA: 14000
    # ... etc

# Treatment effects (multipliers)
treatments:
  tBHP:
    MitoProbe: 0.7      # Depolarization
    Hoechst: 1.15       # Condensation
    ConA: 1.1           # ER stress
    Phalloidin: 0.9     # Disruption
    WGA: 0.95           # Mild effect
    
  Staurosporine:
    MitoProbe: 0.5      # Severe depolarization
    Hoechst: 1.6        # Strong condensation
    # ... etc

# Nuclear size ranges (µm²)
nuclear_sizes:
  U2OS: [120, 200]
  A549: [90, 150]
  HepG2: [80, 130]
  iPSC: [60, 110]

# Embedding configuration
embeddings:
  dimensions: 128
  method: "random_projection"
  pca_components: 2  # For visualization

# MoA classification
moa:
  alignment_threshold: 0.3
  categories:
    - name: "Enhancer"
      color: "#FF4B4B"
    - name: "Suppressor"
      color: "#00CC66"
    - name: "Orthogonal"
      color: "#FFA500"
```

**Loading in Code:**
```python
import yaml
from pathlib import Path

def load_simulation_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "cell_painting_simulation.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)

CONFIG = load_simulation_config()
```

**Acceptance Criteria:**
- All configuration externalized
- Easy to add new cell lines/treatments
- Validation on load (schema checking)
- Backward compatible

---

## Phase 4: Advanced Features (Future)
**Estimated Time:** 1-2 weeks  
**Goal:** Research-grade capabilities

### 4.1 Dose-Response Trajectories
Simulate multiple doses and visualize phenotypic "paths" in embedding space.

### 4.2 Real UMAP Integration
Replace PCA with actual UMAP for better 2D projections.

### 4.3 Batch Effect Simulation
Add plate effects, batch variability for realistic data.

### 4.4 Export to Standard Formats
- CellProfiler CSV format
- Broad Institute's morphology database format
- Integration with `pycytominer`

---

## Success Metrics

**Code Quality:**
- [ ] `tab_campaign_posh.py` < 500 lines
- [ ] No functions > 50 lines
- [ ] Test coverage > 80%
- [ ] `mypy --strict` passes
- [ ] No magic numbers

**Performance:**
- [ ] Simulation runs in < 5 seconds (1000 genes)
- [ ] Dashboard loads in < 2 seconds
- [ ] Feature switching < 0.5 seconds (with caching)

**Maintainability:**
- [ ] New cell line added in < 5 minutes (just edit YAML)
- [ ] New treatment added in < 10 minutes
- [ ] New visualization added in < 1 hour

---

## Risk Assessment

**Low Risk:**
- Phase 1 (dead code removal, constants)
- Adding tests

**Medium Risk:**
- Dashboard refactoring (could break UI temporarily)
- MoA logic move (need careful testing)

**High Risk:**
- Configuration externalization (backward compatibility)

**Mitigation:**
- Feature flags for new code paths
- Comprehensive testing before merge
- Gradual rollout (Phase 1 → 2 → 3)

---

## Next Steps

1. **Review this plan** with team/stakeholders
2. **Create GitHub issues** for each phase
3. **Start Phase 1** (quick wins)
4. **Iterate** based on feedback

**Estimated Total Time:** 1-2 weeks for Phases 1-3

---

## Notes

- Keep simulation results backward compatible
- Document breaking changes
- Update user-facing documentation
- Consider adding a "What's New" section in dashboard
