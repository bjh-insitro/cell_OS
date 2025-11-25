# Perturbation Acquisition Loop Design

## Overview

The **Perturbation Acquisition Loop** is the Phase 0 component of the autonomous POSH system. It operates at the gene/guide level, selecting which perturbations to include in a POSH screen.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Autonomous POSH System                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Phase -1: Imaging Dose Loop (COMPLETE)                     │
│  ┌────────────────────────────────────────────────────┐     │
│  │ Input:  Cell line, stressor                        │     │
│  │ Output: Optimal dose (e.g., 0.46 µM TBHP)         │     │
│  │ Status: ✓ Working, tested, committed              │     │
│  └────────────────────────────────────────────────────┘     │
│                           ↓                                   │
│  Phase 0: Perturbation Acquisition Loop (THIS LAYER)        │
│  ┌────────────────────────────────────────────────────┐     │
│  │ Input:  Candidate genes, guide library, constraints│     │
│  │ Output: Selected genes + guides for POSH screen    │     │
│  │ Status: ⏳ Skeleton only (no logic yet)            │     │
│  └────────────────────────────────────────────────────┘     │
│                           ↓                                   │
│  Phase 1: Morphology Analysis (FUTURE)                      │
│  ┌────────────────────────────────────────────────────┐     │
│  │ Input:  POSH images + barcodes                     │     │
│  │ Output: Morphological embeddings per gene          │     │
│  │ Status: ❌ Not started                             │     │
│  └────────────────────────────────────────────────────┘     │
│                           ↓                                   │
│  Phase 2: Hit Calling (FUTURE)                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ Input:  Morphological embeddings                   │     │
│  │ Output: Ranked hits, pathway enrichment            │     │
│  │ Status: ❌ Not started                             │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Data Structures (`perturbation_goal.py`)

**`PerturbationGoal`**
- Defines what to optimize for (e.g., "maximize_diversity", "target_pathway")
- Constraints: min/max guides per gene, plate capacity, budget
- Similar to `ImagingWindowGoal` but for perturbation selection

**`PerturbationPlan`**
- Represents one gene with its selected guides
- Includes expected phenotype score
- Similar to `ExperimentPlan` in imaging loop

**`PerturbationBatch`**
- Collection of perturbation plans
- Includes total cost and expected diversity
- Similar to `BatchPlan` in imaging loop

**`PerturbationPosterior`**
- Stores beliefs about gene -> phenotype relationships
- Will eventually hold morphological embeddings
- Similar to `ImagingWorldModel` but for perturbations

### 2. Acquisition Loop (`perturbation_loop.py`)

**`PerturbationAcquisitionLoop`**
- Main class for perturbation selection
- API: `propose()` and `run_one_cycle()`
- Similar structure to `ImagingDoseLoop`

**`PerturbationExecutorLike`** (Protocol)
- Interface for executing perturbation experiments
- Future implementations: simulated and real executors

## Workflow

```python
# Initialize
posterior = PerturbationPosterior()
executor = SimulatedPerturbationExecutor()  # Future
goal = PerturbationGoal(
    objective="maximize_diversity",
    max_perturbations=200,
    budget_usd=10000,
)

loop = PerturbationAcquisitionLoop(posterior, executor, goal)

# Run cycle
candidate_genes = ["TP53", "MDM2", "ATM", "BRCA1", ...]
batch = loop.run_one_cycle(candidate_genes)

# batch.plans contains selected genes + guides
# batch.total_cost_usd shows estimated cost
# batch.expected_diversity shows predicted phenotypic diversity
```

## Integration with Existing Systems

### With Imaging Loop
- Imaging loop provides optimal dose → used in POSH screen
- Perturbation loop provides gene/guide selection → used in POSH screen
- Together they define a complete POSH campaign

### With gRNA Design Solver
- Existing `src/cell_os/grna_design.py` can be integrated
- Perturbation loop will call gRNA solver to design guides
- Constraints: Hamming distance, location overlap, score optimization

### With Economic Engine
- Existing `src/cell_os/inventory.py` and `unit_ops.py` can be used
- Perturbation loop will calculate costs per gene
- Budget constraints enforced during acquisition

### With Plate Designer (Future)
- Perturbation loop outputs gene/guide list
- Plate designer converts to 384-well layout
- Handles controls, replicates, liquid handling constraints

## Future Implementation Plan

### Phase 0.1: Acquisition Logic (Next)
- Implement `propose()` with simple heuristics
- Rank genes by expected informativeness
- Select top N genes respecting constraints
- Integrate with gRNA design solver

### Phase 0.2: Cost Integration
- Calculate cost per perturbation
- Optimize for information gain per dollar
- Respect budget constraints

### Phase 0.3: Simulated Executor
- Create `SimulatedPerturbationExecutor`
- Simulate morphological diversity
- Enable closed-loop testing

### Phase 1: Morphology Integration
- Extract morphological features from POSH images
- Compute embeddings (PCA/UMAP)
- Update `PerturbationPosterior` with real data
- Enable learning from POSH results

### Phase 2: Hit Calling
- Phenotypic clustering
- Outlier detection
- Pathway enrichment analysis

## Design Principles

1. **Separation of Concerns**
   - Perturbation loop is independent of imaging loop
   - No changes to existing imaging code
   - Clean interfaces via Protocols

2. **Incremental Implementation**
   - Skeleton first (this phase)
   - Logic second (Phase 0.1)
   - Morphology third (Phase 1)

3. **Testability**
   - All components have clear APIs
   - Simulated executors for testing
   - No dependence on real lab equipment

4. **Economic Awareness**
   - Cost calculation integrated from start
   - Budget constraints enforced
   - Optimize for information per dollar

## Current Status

- ✅ Data structures defined
- ✅ Loop skeleton created
- ✅ Protocols defined
- ✅ Design document written
- ⏳ Tests stubbed (next)
- ❌ Acquisition logic (future)
- ❌ Morphology integration (future)

## Next Steps

1. Stub tests for perturbation loop
2. Verify imports and integration
3. Commit skeleton
4. Begin Phase 0.1: implement acquisition logic
