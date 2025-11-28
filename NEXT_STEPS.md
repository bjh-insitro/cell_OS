# Next Steps for cell_OS

## Current Status (as of 2025-11-28)

The system now has a robust **Execution Engine** with:
- **Inventory Management**: Persistent tracking of reagents and consumables.
- **Campaign Management**: Scheduling of long-term maintenance and screening campaigns.
- **Job Queue**: Priority-based scheduling of execution jobs.
- **HAL (Hardware Abstraction Layer)**: Interface for plugging in real robots.
- **Dashboard**: Comprehensive UI for monitoring and control.

## Recommended Next Steps

### 1. Unify Optimization and Execution
Currently, `scripts/run_loop.py` (the optimization loop) uses a legacy `SimulationEngine`. It should be updated to use the new `WorkflowExecutor` and `JobQueue`.
- **Goal**: Allow the AI scientist to run experiments using the same infrastructure as manual protocols.
- **Action**: Refactor `run_loop.py` to convert proposals into `Workflow` objects and submit them to `JobQueue`.

### 2. Implement Real Hardware Support
The `HardwareInterface` is currently backed by `VirtualMachine`.
- **Goal**: Enable physical automation.
- **Action**: Create `OpentronsInterface` or `HamiltonInterface` implementing `HardwareInterface`.

### 3. Advanced Scheduling
The `CampaignManager` generates simple schedules.
- **Goal**: Optimize lab throughput.
- **Action**: Implement conflict detection (e.g., two jobs needing the robot at the same time) and smart rescheduling.

### 4. LIMS Integration
- **Goal**: seamless data tracking.
- **Action**: Connect `InventoryManager` to barcode scanners or external LIMS APIs.

### 5. User Management
- **Goal**: Multi-user support.
- **Action**: Add user authentication and role-based access control to the dashboard.
