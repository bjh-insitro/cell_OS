# Multi-Cell-Line POSH Campaign: Capability Audit & Integration Plan

**Date:** 2025-11-29  
**Objective:** Audit existing capabilities and identify gaps for simulating a complete 3-cell-line (U2OS, HepG2, A549) POSH campaign from vendor vials through analysis.

---

## 1. EXISTING CAPABILITIES

### 1.1 MCB & WCB Workflows ✅

**Status:** FULLY IMPLEMENTED

**Files:**
- `src/cell_os/mcb_crash.py` - MCB simulation with failure modes
- `src/cell_os/wcb_crash.py` - WCB simulation
- `src/cell_os/workflows/__init__.py` - WorkflowBuilder with MCB/WCB methods

**Key Classes:**
- `MCBSimulation` - Simulates MCB generation from vendor vials
  - Handles thawing, expansion, passaging, freezing
  - Tracks contamination, failures, resource usage
  - Returns daily metrics (cells, confluence, viability, costs)
- `WCBSimulation` - Similar structure for WCB from MCB vials
- `WorkflowBuilder.build_master_cell_bank()` - Creates MCB workflow
- `WorkflowBuilder.build_working_cell_bank()` - Creates WCB workflow

**Capabilities:**
- ✅ Thaw vendor vials
- ✅ Expand cells through passages
- ✅ Track growth, viability, confluence
- ✅ Freeze into cryovials
- ✅ QC operations (mycoplasma, sterility, karyotype)
- ✅ Resource tracking (media, BSC hours, staff time)
- ✅ Failure mode simulation (contamination)

**Cell Line Support:**
- Currently supports: U2OS, HEK293T, HeLa, iPSC
- **HepG2 and A549:** Parameters exist in `simulation_parameters.yaml` but need verification

---

### 1.2 POSH Library Design ✅

**Status:** FULLY IMPLEMENTED

**Files:**
- `src/cell_os/posh_library_design.py`
- `src/cell_os/create_library.py`
- `src/cell_os/guide_design_v2.py`

**Key Functions:**
- `design_posh_library()` - Creates whole genome gRNA library
- `design_library_for_genes()` - Subset library for specific genes
- Supports Twist, Cellecta vendor formats

**Capabilities:**
- ✅ Whole genome library design
- ✅ Custom gene list libraries
- ✅ gRNA design with scoring
- ✅ Barcode assignment
- ✅ Vendor format export

---

### 1.3 LV Batch Design & Titering ✅

**Status:** FULLY IMPLEMENTED

**Files:**
- `src/cell_os/posh_lv_moi.py` - Core LV physics and MOI modeling
- `src/cell_os/titration_loop.py` - Autonomous titration agent

**Key Classes:**
- `LVBatch` - Represents viral batch with titer
- `LVTitrationPlan` - Defines titration experiment
- `LVTitrationResult` - Stores titration data
- `LVTransductionModel` - Poisson-based MOI model
  - `predict_bfp(volume_ul)` - Predicts transduction efficiency
  - `volume_for_moi(target_moi)` - Calculates volume for target MOI
- `LVAutoExplorer` - Suggests next titration points
- `ScreenSimulator` - Estimates probability of screen success
- `AutonomousTitrationAgent` - Runs multi-round titration campaigns

**Key Functions:**
- `design_lv_batch()` - Creates LV batch specification
- `design_lv_titration_plan()` - Plans titration experiment
- `fit_lv_transduction_model()` - Fits Poisson model to data
- `design_lv_for_scenario()` - End-to-end LV design

**Capabilities:**
- ✅ LV batch design with aliquoting
- ✅ Titration plan generation (volumes, replicates)
- ✅ Non-linear Poisson curve fitting with RANSAC outlier detection
- ✅ Bayesian posterior over titer
- ✅ MOI prediction and volume calculation
- ✅ Autonomous multi-round titration with budget constraints
- ✅ Probability of success estimation
- ✅ Adaptive sampling (LVAutoExplorer)

**Cell Line Support:**
- Generic framework supports any cell line
- Needs cell-line-specific parameters (cells_per_well, etc.)

---

### 1.4 POSH Screen Execution ✅

**Status:** FULLY IMPLEMENTED

**Files:**
- `src/cell_os/posh_complete_workflow.py` - Complete POSH workflow
- `src/cell_os/posh_screen_designer.py` - Screen design calculations
- `src/cell_os/workflows/__init__.py` - WorkflowBuilder.build_zombie_posh()

**Key Functions:**
- `get_complete_posh_screen_workflow()` - Full POSH workflow from transduction to analysis
- `get_complete_posh_screen_engine_workflow()` - Returns Workflow object
- `create_screen_design()` - Calculates cell counts, plates, costs

**Workflow Phases:**
1. ✅ Transduction (spinoculation)
2. ✅ Selection (puromycin)
3. ✅ Expansion for banking
4. ✅ Cryopreservation
5. ✅ Thaw and recovery
6. ✅ Flask expansion
7. ✅ Plate seeding
8. ✅ Growth to confluence
9. ✅ Fixation
10. ✅ Zombie POSH (decrosslinking, T7 IVT)
11. ✅ SBS imaging (13 cycles)
12. ✅ Image analysis pipeline

**Capabilities:**
- ✅ Complete workflow generation
- ✅ Resource calculation (cells, plates, media, virus)
- ✅ Cost estimation
- ✅ Banking strategy (4 screens)
- ✅ Multiple screen execution from banked cells

---

### 1.5 POSH Analysis ✅

**Status:** FULLY IMPLEMENTED

**Files:**
- `src/cell_os/phenotype_clustering.py` - Clustering and summarization
- `src/cell_os/phenotype_aggregation.py` - Feature aggregation
- `src/cell_os/morphology_engine.py` - Morphology feature extraction
- `src/cell_os/dino_analysis.py` - DINO embedding analysis
- `src/cell_os/posh_viz.py` - Visualization

**Key Functions:**
- `cluster_hits()` - Clusters genes by morphology
- `summarize_clusters()` - Generates cluster summaries
- `aggregate_phenotypes()` - Aggregates features per gene
- `extract_features()` - Morphology feature extraction
- `compare_conditions()` - Control vs treatment comparison (in dino_analysis)

**Capabilities:**
- ✅ Morphology feature extraction
- ✅ DINO embedding generation
- ✅ Clustering (HDBSCAN)
- ✅ Hit calling
- ✅ Phenotype summarization
- ✅ Visualization (heatmaps, UMAP, etc.)

---

### 1.6 Perturbation Loop (Gene Selection) ✅

**Status:** FULLY IMPLEMENTED

**Files:**
- `src/cell_os/perturbation_loop.py` - Autonomous perturbation selection
- `src/cell_os/perturbation_goal.py` - Goals and posteriors
- `src/cell_os/plate_constraints.py` - Plate capacity constraints

**Key Classes:**
- `PerturbationAcquisitionLoop` - Selects genes/guides for screens
- `PerturbationGoal` - Defines screening objectives
- `PerturbationPosterior` - Bayesian model of gene effects
- `PlateConstraints` - Physical plate limits

**Capabilities:**
- ✅ Autonomous gene selection
- ✅ Diversity-aware sampling
- ✅ Plate capacity constraints
- ✅ Multi-cycle campaigns
- ✅ Posterior updating with results

---

### 1.7 Inventory & Cost Tracking ✅

**Status:** FULLY IMPLEMENTED

**Files:**
- `src/cell_os/inventory.py` - Inventory management
- `src/cell_os/inventory_manager.py` - Stock tracking
- `src/cell_os/budget_manager.py` - Budget tracking
- `data/raw/pricing.yaml` - Pricing database

**Capabilities:**
- ✅ Reagent pricing
- ✅ Consumable tracking
- ✅ Stock management
- ✅ Cost accumulation
- ✅ Budget constraints

---

### 1.8 BiologicalVirtualMachine ✅

**Status:** FULLY IMPLEMENTED (Recently Enhanced)

**Files:**
- `src/cell_os/hardware/biological_virtual.py`

**Capabilities:**
- ✅ Cell growth simulation with doubling times
- ✅ Viability tracking
- ✅ Passage stress
- ✅ Compound treatment (dose-response)
- ✅ Confluence effects
- ✅ **NEW:** Lag phase dynamics
- ✅ **NEW:** Spatial edge effects
- ✅ Multiple vessel tracking
- ✅ Time-based simulation

**Cell Line Support:**
- ✅ U2OS, HEK293T, HeLa, iPSC in database
- ⚠️ HepG2, A549 need parameter verification

---

## 2. MISSING CAPABILITIES & GAPS

### 2.1 tBHP Dose Finding Workflow ❌

**Status:** NOT IMPLEMENTED

**What's Missing:**
- No specific tBHP dose-response workflow
- No oxidative stress readout simulation (CellROX)
- No segmentation quality metric
- No multi-objective optimization (high signal + good viability + good segmentation)
- No per-cell-line dose finding loop

**Existing Related Code:**
- `acquisition.py` - Generic dose-response acquisition (for viability)
- `modeling.py` - Dose-response GP modeling
- Could be adapted but needs:
  - Multi-readout support (viability + CellROX + segmentation)
  - tBHP-specific compound parameters
  - Optimization criteria for "optimal stress dose"

**Impact:** CRITICAL - Cannot determine optimal tBHP dose per cell line

---

### 2.2 Multi-Condition POSH Execution ❌

**Status:** PARTIALLY IMPLEMENTED

**What's Missing:**
- No framework for running same library under multiple conditions (control vs tBHP)
- Current `posh_complete_workflow.py` assumes single condition
- No condition tracking in workflow metadata
- No paired control/treatment plate layout

**Existing Code:**
- `posh_complete_workflow.py` - Single condition only
- Would need:
  - `MultiConditionPOSHWorkflow` class
  - Condition parameter in screen design
  - Plate layout with control/treatment pairing
  - Metadata tracking for condition

**Impact:** HIGH - Cannot run control vs tBHP screens

---

### 2.3 Multi-Cell-Line Campaign Orchestrator ❌

**Status:** NOT IMPLEMENTED

**What's Missing:**
- No top-level campaign manager for 3 cell lines
- No state machine for: vendor → MCB → WCB → tBHP → LV → POSH → analysis
- No cross-line result aggregation
- No campaign-level checkpointing/resumption
- No dependency tracking between stages

**Existing Code:**
- `campaign.py` - Generic campaign goals (potency, selectivity)
- `campaign_manager.py` - Job scheduling, not full campaign orchestration
- `titration_loop.py` - Has multi-line support but only for LV titering

**What's Needed:**
- `MultiCellLinePOSHCampaign` class
- State tracking per cell line per stage
- Result propagation (e.g., optimal tBHP dose → POSH screen)
- Cross-line comparison utilities

**Impact:** CRITICAL - Cannot orchestrate full campaign

---

### 2.4 Parameter Propagation Between Stages ❌

**Status:** NOT IMPLEMENTED

**What's Missing:**
- No mechanism to store "optimal tBHP dose" from dose finding
- No mechanism to store "chosen LV volume" from titering
- No campaign-level parameter database
- No workflow input/output schema for stage results

**Existing Code:**
- `experimental_db.py` - Stores measurements but not campaign parameters
- `campaign_db.py` - Stores campaign metadata but not stage results

**What's Needed:**
- `CampaignParametersDB` or extension to `CampaignDatabase`
- Schema for stage outputs:
  - `tBHP_dose_finding` → `optimal_dose_uM`
  - `LV_titering` → `optimal_volume_ul`, `estimated_titer`, `target_MOI`
- API to retrieve parameters for downstream stages

**Impact:** HIGH - Cannot pass results between stages

---

### 2.5 HepG2 & A549 Cell Line Parameters ⚠️

**Status:** PARTIALLY IMPLEMENTED

**What's Missing:**
- Parameters exist in `simulation_parameters.yaml` but may be incomplete
- No validation that all required parameters are present
- No tBHP sensitivity data for these lines
- No CellROX response curves

**Existing Code:**
- `simulation_parameters.yaml` - Has some HepG2/A549 data
- `simulation_params_db.py` - Loads parameters

**What's Needed:**
- Verify/complete parameters:
  - `doubling_time_h`
  - `max_confluence`
  - `passage_stress`
  - `lag_duration_h`
  - `edge_penalty`
- Add tBHP sensitivity (IC50, Hill slope)
- Add CellROX response parameters

**Impact:** MEDIUM - Can simulate but may not be realistic

---

### 2.6 tBHP Compound Definition ❌

**Status:** NOT IMPLEMENTED

**What's Missing:**
- No tBHP compound entry in `simulation_parameters.yaml`
- No tBHP dose-response parameters per cell line
- No CellROX readout simulation

**Existing Code:**
- `simulation_parameters.yaml` - Has staurosporine, tunicamycin, etc.
- `BiologicalVirtualMachine.treat_with_compound()` - Generic compound treatment

**What's Needed:**
- Add tBHP to compound database with:
  - Cell-line-specific IC50 values
  - Hill slopes
  - CellROX EC50 (concentration for half-max signal)
  - Segmentation quality degradation curve
- Extend `BiologicalVirtualMachine` or create `OxidativeStressSimulator`

**Impact:** CRITICAL - Cannot simulate tBHP dose finding

---

### 2.7 Multi-Readout Assay Support ❌

**Status:** NOT IMPLEMENTED

**What's Missing:**
- Current assays return single readout (viability OR morphology)
- No framework for multi-readout optimization
- No Pareto frontier calculation for multi-objective optimization

**Existing Code:**
- `simulation_executor.py` - Single readout handlers
- `acquisition.py` - Single objective acquisition

**What's Needed:**
- `MultiReadoutAssay` class
- Handlers for:
  - `viability` (existing)
  - `cellrox_signal` (new)
  - `segmentation_quality` (new)
- Multi-objective acquisition function
- Scalarization or Pareto ranking

**Impact:** HIGH - Cannot optimize tBHP dose properly

---

### 2.8 Cross-Line Comparison Utilities ⚠️

**Status:** PARTIALLY IMPLEMENTED

**What's Missing:**
- No dedicated cross-line comparison module
- Existing analysis is per-line
- No statistical tests for line differences
- No visualization for 3-line comparison

**Existing Code:**
- `phenotype_clustering.py` - Single condition clustering
- `dino_analysis.py` - Has `compare_conditions()` but for control vs treatment, not lines

**What's Needed:**
- `CrossLineAnalysis` class
- Functions:
  - `compare_lines_control()` - Baseline differences
  - `compare_lines_treatment()` - Treatment response differences
  - `identify_line_specific_hits()` - Genes unique to one line
  - `identify_shared_hits()` - Genes common across lines
- Visualization:
  - Venn diagrams for hits
  - Heatmaps across lines
  - Differential response plots

**Impact:** MEDIUM - Can analyze but not compare systematically

---

### 2.9 Workflow Integration Tests ⚠️

**Status:** PARTIALLY IMPLEMENTED

**What's Missing:**
- No end-to-end integration test for full campaign
- Existing tests are per-module
- No test for data flow between stages

**Existing Code:**
- `tests/integration/` - Has POSH-specific tests
- `tests/integration/test_mcb_crash_test.py` - MCB tests
- No multi-stage test

**What's Needed:**
- `test_multi_cell_line_posh_campaign.py`
- Test full flow: vendor → MCB → WCB → tBHP → LV → POSH → analysis
- Mock execution to verify data flow
- Checkpoint/resume testing

**Impact:** LOW - Nice to have for validation

---

## 3. MINIMAL IMPLEMENTATION PLAN

### 3.1 tBHP Dose Finding Module

**File:** `src/cell_os/tbhp_dose_finder.py` (NEW)

**Classes:**

```python
@dataclass
class TBHPDoseResult:
    """Result of tBHP dose finding for one cell line."""
    cell_line: str
    optimal_dose_uM: float
    viability_at_optimal: float
    cellrox_signal_at_optimal: float
    segmentation_quality_at_optimal: float
    dose_response_curve: pd.DataFrame
    
@dataclass
class TBHPOptimizationCriteria:
    """Criteria for optimal tBHP dose."""
    min_viability: float = 0.7  # At least 70% viable
    target_cellrox_signal: float = 2.0  # 2× baseline
    min_segmentation_quality: float = 0.8  # 80% cells segmentable
    
class TBHPDoseFinder:
    """Autonomous dose finding for tBHP oxidative stress."""
    
    def __init__(self, vm: BiologicalVirtualMachine, criteria: TBHPOptimizationCriteria):
        self.vm = vm
        self.criteria = criteria
        
    def run_dose_finding(self, cell_line: str, dose_range: Tuple[float, float], 
                        n_doses: int = 8) -> TBHPDoseResult:
        """Run dose-response experiment and find optimal dose."""
        # 1. Generate dose grid
        # 2. For each dose, simulate:
        #    - Viability (from BiologicalVirtualMachine)
        #    - CellROX signal (new simulation)
        #    - Segmentation quality (new simulation)
        # 3. Find dose meeting all criteria
        # 4. Return result
        pass
```

**Integration:**
- Extend `BiologicalVirtualMachine` with `simulate_cellrox_signal()`
- Extend `BiologicalVirtualMachine` with `simulate_segmentation_quality()`
- Add tBHP parameters to `simulation_parameters.yaml`

**Tests:**
- `tests/unit/test_tbhp_dose_finder.py`
- Test dose finding for U2OS, HepG2, A549
- Test criteria satisfaction
- Test edge cases (no dose meets criteria)

---

### 3.2 Multi-Condition POSH Workflow

**File:** `src/cell_os/posh_complete_workflow.py` (MODIFY)

**New Function:**

```python
def get_multi_condition_posh_workflow(
    ops: ParametricOps,
    library_name: str,
    num_genes: int,
    cell_type: str,
    conditions: List[Dict[str, Any]],  # [{"name": "control"}, {"name": "tBHP", "dose_uM": 50}]
    viral_titer: float = 1e7,
    target_cells_per_grna: int = 750,
    moi: float = 0.3
) -> Workflow:
    """
    Generate POSH workflow for multiple conditions.
    
    Each condition gets its own set of plates with shared transduction/banking.
    """
    # 1. Single transduction and banking (shared)
    # 2. For each condition:
    #    - Thaw aliquot
    #    - Expand
    #    - Seed plates
    #    - Apply condition (e.g., add tBHP)
    #    - Fix and process
    # 3. Return combined workflow
    pass
```

**Integration:**
- Modify `create_screen_design()` to accept conditions
- Update plate layout to track condition
- Modify metadata to include condition info

**Tests:**
- `tests/integration/test_multi_condition_posh.py`
- Test 2-condition workflow (control + tBHP)
- Verify plate counts
- Verify condition tracking

---

### 3.3 Campaign Orchestrator

**File:** `src/cell_os/multi_cell_line_campaign.py` (NEW)

**Classes:**

```python
@dataclass
class CampaignStageResult:
    """Result from one campaign stage."""
    stage_name: str
    cell_line: str
    status: str  # "success", "failed", "pending"
    outputs: Dict[str, Any]  # Stage-specific outputs
    timestamp: datetime
    
class MultiCellLinePOSHCampaign:
    """Orchestrates full POSH campaign across multiple cell lines."""
    
    STAGES = [
        "mcb_generation",
        "wcb_generation",
        "tbhp_dose_finding",
        "lv_titering",
        "lv_transduction",
        "posh_screening",
        "analysis"
    ]
    
    def __init__(self, cell_lines: List[str], library: POSHLibrary, 
                 campaign_db: CampaignDatabase):
        self.cell_lines = cell_lines
        self.library = library
        self.db = campaign_db
        self.results = {}  # {(cell_line, stage): CampaignStageResult}
        
    def run_campaign(self):
        """Execute full campaign with checkpointing."""
        for stage in self.STAGES:
            for cell_line in self.cell_lines:
                if self._is_stage_complete(cell_line, stage):
                    continue
                    
                result = self._run_stage(cell_line, stage)
                self._save_result(cell_line, stage, result)
                
    def _run_stage(self, cell_line: str, stage: str) -> CampaignStageResult:
        """Run one stage for one cell line."""
        if stage == "mcb_generation":
            return self._run_mcb(cell_line)
        elif stage == "wcb_generation":
            return self._run_wcb(cell_line)
        elif stage == "tbhp_dose_finding":
            return self._run_tbhp_dose_finding(cell_line)
        # ... etc
        
    def get_stage_output(self, cell_line: str, stage: str, key: str) -> Any:
        """Retrieve output from previous stage."""
        result = self.results.get((cell_line, stage))
        if result:
            return result.outputs.get(key)
        return None
```

**Integration:**
- Uses `MCBSimulation`, `WCBSimulation`, `TBHPDoseFinder`, `AutonomousTitrationAgent`, etc.
- Stores results in `CampaignDatabase`
- Provides resume capability

**Tests:**
- `tests/integration/test_multi_cell_line_campaign.py`
- Test full campaign for 1 cell line
- Test resume after failure
- Test parameter propagation

---

### 3.4 Campaign Parameters Database

**File:** `src/cell_os/campaign_db.py` (MODIFY)

**Schema Extension:**

```python
# Add to CampaignDatabase

CREATE TABLE IF NOT EXISTS stage_outputs (
    id INTEGER PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    cell_line TEXT NOT NULL,
    stage_name TEXT NOT NULL,
    output_key TEXT NOT NULL,
    output_value TEXT NOT NULL,  -- JSON serialized
    timestamp REAL NOT NULL,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
)

def save_stage_output(self, campaign_id: str, cell_line: str, stage: str, 
                     key: str, value: Any):
    """Save output from a campaign stage."""
    
def get_stage_output(self, campaign_id: str, cell_line: str, stage: str, 
                    key: str) -> Any:
    """Retrieve output from a campaign stage."""
```

**Integration:**
- Used by `MultiCellLinePOSHCampaign`
- Stores:
  - `optimal_tbhp_dose_uM`
  - `lv_optimal_volume_ul`
  - `lv_estimated_titer`
  - `mcb_vial_count`
  - `wcb_vial_count`

**Tests:**
- `tests/unit/test_campaign_db.py` (extend existing)
- Test save/retrieve stage outputs
- Test JSON serialization

---

### 3.5 Cell Line Parameter Completion

**File:** `data/simulation_parameters.yaml` (MODIFY)

**Add/Verify:**

```yaml
cell_lines:
  HepG2:
    doubling_time_h: 48.0  # Verify
    max_confluence: 1.5
    passage_stress: 0.02
    lag_duration_h: 16.0  # Slower than U2OS
    edge_penalty: 0.15
    
  A549:
    doubling_time_h: 22.0  # Verify
    max_confluence: 1.5
    passage_stress: 0.02
    lag_duration_h: 12.0
    edge_penalty: 0.15

compounds:
  tbhp:
    description: "tert-Butyl hydroperoxide (oxidative stress)"
    sensitivity:
      U2OS:
        ic50_uM: 100.0  # Estimate
        hill_slope: 2.0
        cellrox_ec50_uM: 50.0  # Half-max CellROX signal
        cellrox_max_fold: 5.0  # Max fold increase
        segmentation_degradation_ic50_uM: 200.0  # Dose where segmentation fails
      HepG2:
        ic50_uM: 150.0  # More resistant
        hill_slope: 2.0
        cellrox_ec50_uM: 75.0
        cellrox_max_fold: 4.0
        segmentation_degradation_ic50_uM: 250.0
      A549:
        ic50_uM: 80.0  # More sensitive
        hill_slope: 2.5
        cellrox_ec50_uM: 40.0
        cellrox_max_fold: 6.0
        segmentation_degradation_ic50_uM: 150.0
```

**Integration:**
- Run `scripts/migrate_simulation_params.py` to update database
- Verify with `BiologicalVirtualMachine` tests

**Tests:**
- `tests/unit/test_simulation_params_db.py` (extend)
- Test HepG2/A549 parameter loading
- Test tBHP compound loading

---

### 3.6 Cross-Line Analysis Module

**File:** `src/cell_os/cross_line_analysis.py` (NEW)

**Functions:**

```python
def compare_lines_baseline(results: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compare baseline morphology across cell lines (control condition)."""
    # results = {"U2OS": df_u2os_control, "HepG2": df_hepg2_control, ...}
    # Returns comparison table
    
def compare_lines_treatment_response(
    results: Dict[str, Tuple[pd.DataFrame, pd.DataFrame]]
) -> pd.DataFrame:
    """Compare treatment response across cell lines."""
    # results = {"U2OS": (df_control, df_tbhp), ...}
    # Returns differential response table
    
def identify_shared_hits(
    hits: Dict[str, List[str]], 
    min_lines: int = 2
) -> List[str]:
    """Find genes that are hits in at least min_lines cell lines."""
    
def identify_line_specific_hits(
    hits: Dict[str, List[str]]
) -> Dict[str, List[str]]:
    """Find genes that are hits in only one cell line."""
    
def visualize_cross_line_comparison(
    results: Dict[str, pd.DataFrame],
    output_path: str
):
    """Generate cross-line comparison plots."""
    # Venn diagrams, heatmaps, etc.
```

**Integration:**
- Uses results from `phenotype_clustering.py`
- Integrates with `posh_viz.py` for visualization

**Tests:**
- `tests/unit/test_cross_line_analysis.py`
- Test with mock data for 3 lines
- Test hit identification
- Test visualization generation

---

## 4. INTEGRATION PLAN

### Phase 1: Foundation (Week 1)

**Priority:** CRITICAL

1. **Complete Cell Line Parameters**
   - Add/verify HepG2 and A549 parameters
   - Add tBHP compound definition
   - Run migration script
   - Test: `pytest tests/unit/test_simulation_params_db.py`

2. **Extend BiologicalVirtualMachine**
   - Add `simulate_cellrox_signal(compound, dose)`
   - Add `simulate_segmentation_quality(compound, dose)`
   - Test: `pytest tests/unit/test_biological_virtual_machine.py`

3. **Implement tBHP Dose Finder**
   - Create `src/cell_os/tbhp_dose_finder.py`
   - Implement `TBHPDoseFinder` class
   - Test: `pytest tests/unit/test_tbhp_dose_finder.py`

**Deliverable:** Can simulate tBHP dose finding for all 3 cell lines

---

### Phase 2: Campaign Infrastructure (Week 2)

**Priority:** CRITICAL

4. **Extend Campaign Database**
   - Add `stage_outputs` table to `campaign_db.py`
   - Implement save/get methods
   - Test: `pytest tests/unit/test_campaign_db.py`

5. **Implement Campaign Orchestrator**
   - Create `src/cell_os/multi_cell_line_campaign.py`
   - Implement `MultiCellLinePOSHCampaign` class
   - Implement stage runners for MCB, WCB, tBHP, LV
   - Test: `pytest tests/integration/test_multi_cell_line_campaign.py`

**Deliverable:** Can orchestrate MCB → WCB → tBHP → LV stages

---

### Phase 3: POSH Integration (Week 3)

**Priority:** HIGH

6. **Implement Multi-Condition POSH**
   - Modify `posh_complete_workflow.py`
   - Add `get_multi_condition_posh_workflow()`
   - Update screen designer for conditions
   - Test: `pytest tests/integration/test_multi_condition_posh.py`

7. **Integrate POSH into Campaign**
   - Add `_run_posh_screening()` to campaign orchestrator
   - Add `_run_analysis()` to campaign orchestrator
   - Test: End-to-end campaign test

**Deliverable:** Can run full campaign through POSH screening

---

### Phase 4: Analysis & Comparison (Week 4)

**Priority:** MEDIUM

8. **Implement Cross-Line Analysis**
   - Create `src/cell_os/cross_line_analysis.py`
   - Implement comparison functions
   - Implement visualization
   - Test: `pytest tests/unit/test_cross_line_analysis.py`

9. **Create End-to-End Demo**
   - Create `scripts/demo_multi_cell_line_posh.py`
   - Run full campaign for 3 lines
   - Generate comparison report
   - Save results to `data/campaign_results/`

**Deliverable:** Complete campaign with cross-line analysis

---

## 5. DATA FLOW DIAGRAM

```
Vendor Vials (U2OS, HepG2, A549)
    ↓
[MCB Generation] → MCB vials (10 per line)
    ↓
[WCB Generation] → WCB vials (30 per line)
    ↓
[tBHP Dose Finding] → optimal_dose_uM per line
    ↓                   (stored in CampaignDB)
[LV Titering] → optimal_volume_ul, titer per line
    ↓              (stored in CampaignDB)
[Whole Genome LV Transduction] → Transduced cells
    ↓
[Banking] → Banked screens (4× per line)
    ↓
[POSH Screening: Control] → Control results
[POSH Screening: tBHP] → Treatment results
    ↓
[Analysis] → Hits per line, per condition
    ↓
[Cross-Line Comparison] → Shared hits, line-specific hits
```

---

## 6. OPEN QUESTIONS & DESIGN CHOICES

### 6.1 tBHP Dose Optimization Strategy

**Question:** How to handle multi-objective optimization for tBHP dose?

**Options:**
1. **Scalarization:** Weighted sum of objectives
   - `score = w1×viability + w2×cellrox + w3×segmentation`
   - Simple but requires weight tuning
   
2. **Constraint Satisfaction:** Find dose meeting all constraints
   - `viability ≥ 0.7 AND cellrox ≥ 2.0 AND segmentation ≥ 0.8`
   - Clear criteria but may have no solution
   
3. **Pareto Frontier:** Return all non-dominated solutions
   - Let user choose from Pareto set
   - Most flexible but requires user input

**Recommendation:** Start with constraint satisfaction (Option 2), fall back to best partial match if no dose meets all criteria.

---

### 6.2 LV Titering: Per-Line or Shared Batch?

**Question:** Should each cell line get its own LV titration, or use one batch for all?

**Options:**
1. **Per-Line Titering:** More accurate, accounts for line-specific transduction efficiency
2. **Shared Batch:** Faster, assumes similar transduction across lines

**Recommendation:** Per-line titering (Option 1) for realism, but allow shared batch mode for speed.

---

### 6.3 POSH Condition Application

**Question:** When to apply tBHP in POSH workflow?

**Options:**
1. **During Growth:** Add tBHP to media, cells grow under stress
2. **Acute Treatment:** Add tBHP 24h before fixation
3. **Continuous:** tBHP present throughout

**Recommendation:** Acute treatment (Option 2) - add tBHP 24h before fixation for consistent stress window.

---

### 6.4 Cross-Line Hit Calling

**Question:** How to define "hit" consistently across lines with different baselines?

**Options:**
1. **Absolute Threshold:** Same phenotype threshold for all lines
2. **Relative Threshold:** Z-score within each line
3. **Differential:** Significant change from control within each line

**Recommendation:** Differential approach (Option 3) - call hits based on control vs treatment within each line, then compare hit lists.

---

### 6.5 Campaign Checkpointing Granularity

**Question:** At what level should campaign support resume?

**Options:**
1. **Stage-Level:** Resume at start of incomplete stage
2. **Cell-Line-Level:** Resume individual cell line within stage
3. **Operation-Level:** Resume at specific operation

**Recommendation:** Cell-line-level (Option 2) - allows parallelization and fine-grained resume.

---

## 7. ESTIMATED EFFORT

| Component | Complexity | Effort | Priority |
|-----------|-----------|--------|----------|
| Cell Line Parameters | Low | 2 hours | Critical |
| BiologicalVM Extensions | Medium | 4 hours | Critical |
| tBHP Dose Finder | Medium | 8 hours | Critical |
| Campaign DB Extension | Low | 2 hours | Critical |
| Campaign Orchestrator | High | 16 hours | Critical |
| Multi-Condition POSH | Medium | 8 hours | High |
| Cross-Line Analysis | Medium | 6 hours | Medium |
| Integration Tests | Medium | 8 hours | High |
| Documentation | Low | 4 hours | Medium |
| **TOTAL** | | **58 hours** | |

**Timeline:** ~2 weeks with focused development

---

## 8. RISK ASSESSMENT

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| tBHP parameters unknown | High | High | Use literature values, sensitivity analysis |
| Multi-condition POSH complexity | Medium | High | Start with 2 conditions, extend to N |
| Campaign state management bugs | Medium | Medium | Extensive testing, checkpointing |
| Cross-line comparison ambiguity | Low | Medium | Clear hit calling criteria |
| Integration test coverage | Medium | Low | Prioritize critical paths |

---

## 9. SUCCESS CRITERIA

Campaign implementation is complete when:

1. ✅ Can simulate MCB/WCB for U2OS, HepG2, A549
2. ✅ Can find optimal tBHP dose for each line
3. ✅ Can perform LV titering for each line
4. ✅ Can run POSH screens with control + tBHP conditions
5. ✅ Can analyze results per line and per condition
6. ✅ Can compare results across lines
7. ✅ Campaign can resume after interruption
8. ✅ All parameters stored and propagated correctly
9. ✅ End-to-end test passes for all 3 lines
10. ✅ Documentation complete

---

## 10. NEXT STEPS

**Immediate Actions:**

1. Review this audit with stakeholders
2. Confirm tBHP optimization criteria
3. Confirm LV titering strategy (per-line vs shared)
4. Confirm POSH condition application method
5. Begin Phase 1 implementation

**Do NOT execute any workflows until:**
- All gaps are filled
- Integration tests pass
- Parameters are validated
- Campaign orchestrator is tested

---

**End of Audit**
