# cell_OS Ontology

This document defines the semantic framework (ontology) for `cell_OS`. It establishes the vocabulary used to describe biological work, from high-level campaigns down to atomic liquid handling events.

## Hierarchy of Work

The system organizes work into four hierarchical levels:

1.  **Campaign** (Goal)
2.  **Workflow** (End-to-End Chain)
3.  **Process** (Functional Module)
4.  **Unit Operation** (Atomic/Composite Action)

---

### 1. Campaign
*   **Definition**: A high-level scientific objective.
*   **Semantics**: "Find X", "Optimize Y", "Characterize Z".
*   **Example**: `SelectivityCampaign(target="HepG2", counter_target="U2OS")`
*   **Output**: Knowledge (bits), Hypothesis, or Decision.

### 2. Workflow
*   **Definition**: An end-to-end sequence of processes that transforms a starting material (or idea) into a dataset.
*   **Semantics**: A directed graph of **Processes**.
*   **Example**: `Zombie_POSH_Screening_Workflow`
*   **Connectivity**:
    *   Input: `Target Gene List`
    *   Output: `Dose-Response Data` / `Phenotypic Profile`

### 3. Process (The "Recipe")
*   **Definition**: A logical grouping of Unit Operations that achieves a distinct biological state change. Often corresponds to a "Protocol" or "Recipe" in the codebase.
*   **Semantics**: A sequence of **Unit Operations**.
*   **Key Attributes**:
    *   **Inputs**: Physical artifacts (e.g., "Frozen Vial", "Plasmid DNA").
    *   **Outputs**: Physical artifacts (e.g., "Transduced Cells", "Sequencing Library").
*   **Examples**:
    *   `Process_Lentivirus_Production`: Plasmid → Viral Supernatant
    *   `Process_Cell_Painting`: Fixed Cells → Stained Cells
    *   `Process_Sequencing`: Library → FASTQ Files

### 4. Unit Operation (UnitOp)
*   **Definition**: The smallest schedulable unit of work. Can be **Atomic** (single machine action) or **Composite** (a tight loop of atomic actions).
*   **Semantics**: `Action(Subject, Parameters)`
*   **Types**:
    *   **Atomic**: `op_aspirate`, `op_dispense`, `op_incubate`, `op_centrifuge`.
    *   **Composite**: `op_passage` (Asp -> Disp -> Incubate -> Centrifuge -> Resuspend).
    *   **Parametric**: A function that generates a UnitOp based on parameters (e.g., `op_cell_painting(panel="neuropaint")`).

---

## Connectivity & Semantics

How do we connect these components? We use a **Resource-Flow Model**.

### The "Artifact"
An **Artifact** is any physical or digital object that flows between Operations.

*   **Physical**: `Vessel` (Plate, Tube), `Reagent` (Buffer, Enzyme), `BiologicalMaterial` (Cell Line, Virus).
*   **Digital**: `SequenceData`, `ImageSet`, `AnalysisResult`.

### The "Parametric Op" Contract
A `ParametricOp` in `src/unit_ops.py` is a factory function. To formalize connectivity, we define its **Signature**:

```python
def op_example(input_artifact: Artifact, params: Dict) -> OutputArtifact:
    ...
```

*Current Implementation*: The `vessel_id` string acts as the handle for the `InputArtifact`. The return value `UnitOp` represents the transformation cost, but implicitly modifies the state of the `vessel_id`.

---

## Case Study: POSH Workflow

Here is how the **Zombie POSH** workflow maps to this ontology.

### Workflow: `Zombie_POSH_Screening`

#### Phase 1: Upstream (Genetic Supply)
*   **Process 1.1: Library Design** (In Silico)
    *   Input: `Gene List`
    *   Op: `op_design_guides`
    *   Output: `Oligo Pool Design`
*   **Process 1.2: Vector Construction** (Cloning)
    *   Input: `Oligo Pool`, `Backbone Plasmid`
    *   Op: `op_golden_gate_assembly`
    *   Output: `Plasmid Library`
*   **Process 1.3: Virus Production** (Cell Culture)
    *   Input: `Plasmid Library`, `Packaging Mix`, `HEK293T`
    *   Op: `op_transfect`, `op_harvest_virus`
    *   Output: `Lentiviral Supernatant`

#### Phase 2: Screening (Cell Prep & Phenotyping)
*   **Process 2.1: Transduction**
    *   Input: `Target Cells` (e.g., HeLa), `Lentiviral Supernatant`
    *   Op: `op_transduce(method="spinoculation")`
    *   Output: `Transduced Pool`
*   **Process 2.2: Selection & Expansion**
    *   Input: `Transduced Pool`
    *   Op: `op_feed(antibiotic="puromycin")`, `op_passage`
    *   Output: `Selected Pool`
*   **Process 2.3: Phenotyping (Zombie Mode)**
    *   Input: `Selected Pool`
    *   Op: `op_fix_cells`
    *   Op: `op_decross_linking`
    *   Op: `op_t7_ivt`
    *   Op: `op_cell_painting(panel="posh_5channel")`
    *   Output: `Phenotyped Plate`

#### Phase 3: Readout (Imaging & Sequencing)
*   **Process 3.1: Imaging**
    *   Input: `Phenotyped Plate`
    *   Op: `op_imaging`
    *   Output: `Raw Images`
*   **Process 3.2: In Situ Sequencing (ISS)**
    *   Input: `Phenotyped Plate`
    *   Op: `op_sbs_cycle` (Loop x13)
    *   Output: `Sequencing Images`

#### Phase 4: Analysis (Compute)
*   **Process 4.1: Image Processing**
    *   Input: `Raw Images`, `Sequencing Images`
    *   Op: `op_compute_analysis`
    *   Output: `Single Cell Profiles`

---

## Implementation Strategy

To enforce this ontology in code, we should:

1.  **Formalize Artifacts**: Create a class `Artifact` (or `Resource`) that tracks state (e.g., `volume`, `concentration`, `history`).
2.  **Typed Signatures**: Annotate `ParametricOps` to specify required input Artifact types.
3.  **Workflow Builder**: A higher-level class that chains Processes together, validating that `Output(Process A)` matches `Input(Process B)`.

For now, `AssayRecipe` serves as a **linear Workflow definition**, but it lacks explicit artifact tracking between steps.
