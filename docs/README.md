# cell_OS Documentation Index

**Last updated:** December 20, 2025

Welcome! This directory hosts all written artifacts for the cell_OS platform. Use this index to navigate the documentation and understand how we organize active docs, design principles, results, and archives.

---

## 🚀 Quick Start

**New to cell_OS?**
1. Read the root [README](../README.md) for project overview
2. Read [CONTEXT.md](CONTEXT.md) for system architecture and current state
3. Check [QUICKSTART.md](QUICKSTART.md) for getting started
4. Explore [STATUS.md](STATUS.md) for current priorities

**Want to understand a specific phase?**
- See `milestones/` for completed phase summaries
- Phase 6A (epistemic control) details are in [CONTEXT.md](CONTEXT.md#phase-6a-epistemic-control-december-2025)

---

## 📚 Documentation Structure

### Core System Documentation

#### [CONTEXT.md](CONTEXT.md) ⭐ **Start Here**
Complete system overview including:
- What cell_OS is (world model for cell biology experiments)
- Architecture overview (frontend, API, simulation, database)
- Phase 0-6A milestones and achievements
- File layout and key concepts
- Phase 5B realism layer (RunContext, plating artifacts, pipeline drift)
- Phase 6A epistemic control (signature learning, calibrated confidence, semantic honesty)

#### [BIOLOGY_SIMULATION_EVOLUTION.md](BIOLOGY_SIMULATION_EVOLUTION.md)
Complete history of the biological simulation development from initial concepts through Phase 5B.

#### [DEVELOPER_REFERENCE.md](DEVELOPER_REFERENCE.md)
Local development setup, testing, and contribution guidelines.

#### [QUICKSTART.md](QUICKSTART.md)
Get the system running in 5 minutes.

#### [STATUS.md](STATUS.md)
Current program status and immediate next steps.

---

### Active Categories

#### **Milestones (`milestones/`)**
Completed phase work and major achievements (13 documents):
- `PHASE0_FOUNDER_FIXED_SCAFFOLD_COMPLETE.md` - Phase 0: Fixed scaffold design
- `PHASE1_AGENT_SUMMARY.md` - Phase 1: Epistemic agent implementation
- `PHASE2_COMPLETION.md` - Phase 2: Completion summary
- `phase2_chart_gating_results.md` - Phase 2: Chart gating results
- `PHASE3_COMPLETE.md` - Phase 3: Completion
- `PHASE_4_COMPLETION_SUMMARY.md` - Phase 4: Completion summary
- `PHASE_5_EPISTEMIC_CONTROL.md` - Phase 5: Epistemic control system
- `PHASE_5_HETEROGENEITY.md` - Phase 5: Population heterogeneity
- `PHASE_5_HETEROGENEITY_IMPACT.md` - Phase 5: Heterogeneity impact analysis
- `PHASE_5B_REALISM_LAYER.md` - Phase 5B: Realism layer (RunContext, plating, pipeline drift)
- `PHASE_6A_BEAM_SEARCH.md` - Phase 6A: Beam search design
- `PHASE_6A1_STATUS.md` - Phase 6A: Status update
- `PHASE_6A_EPISTEMIC_CONTROL_SESSION.md` - Phase 6A: Dec 20 implementation session

#### **Designs (`designs/`)**
Design philosophy, principles, and roadmaps (15 documents):
- `CELL_THALAMUS_DESIGN.md` - Core simulation design
- `DESIGN_PRINCIPLES.md` ⭐ - Core design principles
- `EPISTEMIC_HONESTY_PHILOSOPHY.md` ⭐ - Epistemic integrity design philosophy
- `EPISTEMIC_CHARTER.md` - Epistemic governance principles
- `EPISTEMIC_AGENT_EXPLORATION.md` - Agent design exploration
- `BIO_VM_FOR_EPISTEMIC_CONTROL.md` - BiologicalVM for epistemic control
- `PHASE_6_REALISM_ROADMAP.md` - Future realism improvements (volume, evaporation, plate fields, waste/pH)
- `REALISM_PRIORITY_ORDER.md` - Realism priorities
- `SIMULATOR_REALISM_GAP.md` - Experimentalist perspective on realism gaps
- `SCAFFOLD_VERSIONING_AND_GEOMETRY.md` - Scaffold design principles
- `SHAPE_LEARNING_DESIGN.md` - Shape learning system design
- `perturbation_loop.md` - Perturbation workflow design
- Plus READMEs and other design documents

#### **Results (`results/`)**
Experimental results, validation reports, and test outcomes:
- `CALIBRATION_RESULTS.md` - Calibrator training metrics (ECE = 0.0626)
- `SIGNATURE_LEARNING_RESULTS.md` - Mechanism signature validation (cosplay detector ratio = ∞)
- `BEAM_COMMIT_TEST_RESULTS.md` - Beam search integration test results
- `MECHANISM_RECOVERY_REPORT.md` - Phase 0 mechanism recovery validation
- `PHASE0_VIABILITY_TABLE.md` - Viability simulation validation
- `PREDICTIVE_MODELING_RESULTS.md` - Predictive model performance

#### **Architecture (`architecture/`)**
System design, implementation plans, and technical details (20 documents):
- `CALIBRATION_ARCHITECTURE.md` ⭐ - Three-layer calibration design (inference, reality, decision)
- `CALIBRATION_PROGRESS.md` - Implementation progress tracking
- `BEAM_SEARCH_CALIBRATION_INTEGRATION.md` - Integration recipe for COMMIT gating
- `BEAM_SEARCH_INTEGRATION_PLAN.md` - Detailed integration plan
- `HARDWARE_ARCHITECTURE.md` - Hardware abstraction layer design
- `WORKCELL_ARCHITECTURE.md` - Workcell system architecture
- `PHASE1_ARCHITECTURE.md` - Phase 1 architecture details
- `LATENT_TO_READOUT_MAP.md` - Morphology readout mapping
- `MORPHOLOGY_READOUT_MODEL.md` - Morphology readout system
- `DEATH_ACCOUNTING_FIX.md` - Death attribution system
- `INTERCONNECTIVITY_AUDIT.md` - System interconnection analysis
- `THREE_EDGE_CASES_FIXED.md` - Edge case resolutions
- `ARCHITECTURE.md`, `DATA_MODEL.md`, `ONTOLOGY.md`, `PROJECT_STRUCTURE.md`, `SYSTEM_GLUE.md`
- Plus other architecture documents

#### **Guides (`guides/`)**
User guides and operational documentation (18 documents):
- `STANDALONE_USAGE.md` - Running standalone simulations
- `CODE_REVIEW_GUIDE.md` - Code review standards
- `AUTONOMOUS_EXECUTOR.md` - Autonomous execution system
- `INVENTORY_GUIDE.md` - Inventory management guide
- See `guides/README.md` for full index

#### **Testing (`testing/`)**
Test strategy, hardening, and validation (6 documents):
- `HARDENING_COMPLETE.md` - System hardening summary
- `RNG_HARDENING_SUMMARY.md` - RNG determinism validation
- `STANDALONE_HARDENING_COMPLETE.md` - Standalone execution hardening
- `TESTING_STREAMLIT.md` - Streamlit testing guide
- `WHY_TESTS_MISS_ERRORS.md` - Test coverage analysis
- `REFUSAL_AND_RETRY_THEOLOGY.md` - Refusal and retry handling

#### **Deployment (`deployment/`)**
Production deployment guides and infrastructure (4 documents):
- `JUPYTERHUB_DEPLOYMENT.md` - 72-core JupyterHub setup (50-100× speedup)
- `JUPYTERHUB_QUICKSTART.md` - Quick start guide for JupyterHub
- `AWS_LAMBDA_SETUP.md` - AWS Lambda configuration
- `IAM_ROLE_REQUEST.md` - IAM role setup for AWS

---

### Reference Documentation

#### **System (`system/`)**
Lab world model and acquisition system references.

#### **Protocols (`protocols/`)**
Wet-lab SOPs and experimental protocols.

#### **Configuration Examples (`config_examples/`)**
Sample configuration files for various use cases.

#### **Notebooks (`notebooks/`)**
Jupyter notebooks for analysis and exploration.

---

### Historical Documentation

#### **Archive (`archive/`)**
All completed or historical documentation (58 documents):

- **`archive/sessions/`** - Historical work sessions with date prefixes:
  - `2025-12-20-semantic-fixes.md` - Semantic honesty enforcement
  - `2025-01-20-semantic-fixes.md`, `2025-01-20-semantic-review.md` - Additional semantic fixes
  - `decision-provenance-patch.md` - Decision provenance fixes
  - `scalar-assay-run-context-fix.md` - Scalar assay context integration
  - `final-sharp-edges-fixed.md` - Sharp edges resolution
  - Plus migration, database, and refactoring sessions

- **`archive/migrations/`** - Legacy migration packets referenced by `MIGRATION_HISTORY.md`

- **`archive/refactorings/`** - Completed refactor logs and summaries

- **`archive/status/`** - Prior status and progress reports

- **`archive/audits/`** - Historical audit reports:
  - `BIO_VM_AUDIT.md` - BiologicalVM audit
  - `MULTI_CELL_LINE_POSH_AUDIT.md` - Multi-cell line audit

- **`archive/improvements/`** - Historical improvement proposals:
  - `BIO_VM_IMPROVEMENTS.md`, `DATABASE_OPPORTUNITIES.md`, `SIMULATION_IMPROVEMENTS.md`
  - `QUICK_WINS.md`, `POSH_DASHBOARD_ENHANCEMENTS.md`
  - `IPSC_PROTOCOL_AND_COST_FIXES.md`, `IPSC_PROTOCOL_FIXES.md`
  - `PHASE3_WASHOUT_COSTS.md`

- **`archive/README.md`** - Archive navigation guide

---

### Meta Documentation

#### **Meta (`meta/`)**
Documentation about documentation, cleanup logs, maintenance:
- `CLEANUP_SUMMARY.md` - Documentation cleanup history
- `DATA_PRINTING.md` - Data printing standards
- `DEPLOYMENT_SPLIT.md` - Deployment documentation organization

#### **Refactor Plans (`refactor_plans/`)**
Active technical refactoring plans (e.g., `BOM_TRACKING_REFACTOR.md`).

---

## 🎯 Common Documentation Pathways

### "I want to understand what cell_OS does"
→ [CONTEXT.md](CONTEXT.md) - Complete system overview

### "I want to run the system"
→ [QUICKSTART.md](QUICKSTART.md) - Get started in 5 minutes

### "I want to understand the epistemic control work"
→ [CONTEXT.md#phase-6a](CONTEXT.md#phase-6a-epistemic-control-december-2025) - Phase 6A summary
→ [designs/EPISTEMIC_HONESTY_PHILOSOPHY.md](designs/EPISTEMIC_HONESTY_PHILOSOPHY.md) - Design philosophy
→ [architecture/CALIBRATION_ARCHITECTURE.md](architecture/CALIBRATION_ARCHITECTURE.md) - Three-layer architecture
→ [results/CALIBRATION_RESULTS.md](results/CALIBRATION_RESULTS.md) - Training metrics

### "I want to understand the biological simulation"
→ [BIOLOGY_SIMULATION_EVOLUTION.md](BIOLOGY_SIMULATION_EVOLUTION.md) - Complete history
→ [designs/CELL_THALAMUS_DESIGN.md](designs/CELL_THALAMUS_DESIGN.md) - Core design
→ [CONTEXT.md#phase-5b](CONTEXT.md#phase-5--5b-population-heterogeneity-and-realism-layer) - Realism layer

### "I want to see validation results"
→ [results/](results/) - All test results and validation reports

### "I want to deploy to production"
→ [deployment/JUPYTERHUB_DEPLOYMENT.md](deployment/JUPYTERHUB_DEPLOYMENT.md) - 72-core setup

---

## 📝 Contributing Documentation

### Adding New Documentation
1. Place active documentation in the appropriate category directory:
   - `milestones/` - Completed phase work
   - `designs/` - Design philosophy and roadmaps
   - `results/` - Validation and test results
   - `architecture/` - System design and implementation
   - `guides/` - User guides
   - `testing/` - Test strategy and validation

2. Update this index when adding major documentation

### Archiving Documentation
When a document becomes historical:
1. Move to appropriate `archive/` subdirectory
2. Add `YYYY-MM-DD-` prefix to filename
3. Update archive index and relevant category indexes

### Documentation Standards
- Use clear, descriptive filenames
- Include "Last updated" dates in major documents
- Link related documents for navigation
- Use consistent markdown formatting

---

## 🔍 Finding Documentation

**Can't find what you're looking for?**
1. Check this index for category organization
2. Search `archive/` for historical artifacts
3. Check `MIGRATION_HISTORY.md` for implementation summaries
4. Look in category subdirectories (`architecture/`, `guides/`, etc.)

**For specific topics:**
- Simulation biology: `BIOLOGY_SIMULATION_EVOLUTION.md`
- System state: `CONTEXT.md`, `STATUS.md`
- Development: `DEVELOPER_REFERENCE.md`
- Historical sessions: `archive/sessions/`

---

## 📊 Documentation Statistics

**Last reorganization:** December 20, 2025

**Organization summary:**
- **docs/ root**: 10 core reference documents (CONTEXT, STATUS, QUICKSTART, etc.)
- **docs/milestones/**: 13 phase completion documents (Phase 0 → 6A)
- **docs/designs/**: 15 design philosophy and roadmap documents
- **docs/results/**: 6 validation and test result documents
- **docs/architecture/**: 20 system design and implementation documents
- **docs/testing/**: 6 test strategy and hardening documents
- **docs/deployment/**: 4 production deployment guides
- **docs/guides/**: 18 user and operational guides
- **docs/archive/**: 58 historical documents (sessions, audits, improvements)

**Total documentation files:** 150+ markdown documents organized by category

**Recent work (December 20, 2025):**
- Organized 55+ markdown files from root and docs/ directories
- Updated CONTEXT.md with comprehensive Phase 6A section
- Completed documentation index with navigation pathways
- Archived historical sessions, audits, and improvement proposals
- Created new archive subdirectories (audits/, improvements/)
