# iPSC Protocol & Cost Refinement Report
**Date:** November 30, 2025
**Focus:** Accuracy of iPSC Thawing/Coating Protocols and Cost Accounting

## 1. Cost & Inventory Corrections
We conducted a thorough audit and update of the `cell_os_inventory.db` to reflect accurate vendor pricing and ensure the simulation uses the correct item IDs.

*   **T75 Flasks**: Updated price to **$4.24/unit** (Case of 100 for $424.22). Added `flask_t75` alias.
*   **Serological Pipettes (10mL)**: Updated price to **$1.06/unit** ($212 for 200). Added `pipette_10ml` alias.
*   **Pipette Tips (1000µL)**: Updated price to **$0.143/tip** ($110 for 768). Added `tip_1000ul_lr` alias.
*   **Accutase**: Updated price to **$0.62/mL** ($62 for 100mL bottle).
*   **CryoStor CS10**: Verified price at **$4.00/mL** ($400 for 100mL bottle).
*   **Vitronectin**: Verified price at **$90.00/mL** ($900 for 10mL stock).
*   **PBS**: Verified price at **$0.036/mL**.
*   **mTeSR Plus Kit**: Verified price at **$0.814/mL**.

**Fix:** Added `ttl=60` to the `load_data` cache in `dashboard_app/utils.py` to ensure price updates from the database are immediately reflected in the dashboard without requiring a full server restart.

## 2. Protocol Refinements

### A. Vitronectin Coating (Day -1)
The coating process was overhauled to reflect the actual manual preparation steps:
*   **Dilution Logic**: Implemented a realistic workflow where Vitronectin is diluted 50x in PBS within a 50mL conical tube before being transferred to the flask.
*   **Step Sequence**:
    1.  Dispense PBS into 50mL Tube.
    2.  Dispense Vitronectin Stock into 50mL Tube.
    3.  Mix solution (Aspirate/Dispense cycle).
    4.  Transfer Coating Solution to T75 Flask.
    5.  Incubate (24 hours).
*   **Costing**: Accurately tracks the cost of the 50mL tube, PBS volume, Vitronectin stock volume, and pipettes used for mixing and transfer.

### B. iPSC Thawing (Day 0)
The thawing protocol was completely rewritten to match the detailed standard operating procedure (SOP), replacing the generic "Thaw -> Seed" logic.
*   **New Step Sequence**:
    1.  **Thaw Vial**: Incubate 2 min at 37°C.
    2.  **Prepare Wash Tube**: Add 5mL media to a 15mL conical tube.
    3.  **Transfer Cells**: Transfer vial contents to the 15mL tube.
    4.  **Wash Vial**: Rinse cryovial with 0.5mL media and add to the 15mL tube.
    5.  **Centrifuge**: Spin down the 15mL tube (5 min @ 1200 rpm).
    6.  **Aspirate Supernatant**: Remove DMSO-laden media.
    7.  **Resuspend**: Resuspend pellet in 1.1mL fresh media.
    8.  **Sample**: Take 100µL sample for NC-202 cell count.
    9.  **Aspirate Coating**: Remove coating solution from the destination T75 flask (moved from Coating op).
    10. **Add Growth Media**: Add 15mL mTeSR Plus to the flask.
    11. **Seed Cells**: Transfer the cell suspension to the flask.
    12. **Incubate**: Begin culture.
*   **Improvements**:
    *   **Vessel Awareness**: Added `tube_15ml` and `cryovial` to `VesselLibrary` to prevent "Generic Vessel" labels.
    *   **Volume Accuracy**: Updated media volume to 15mL (standard for T75).
    *   **Cost Accuracy**: Includes costs for the 15mL tube, multiple pipette sizes (2mL, 5mL, 10mL), and exact media volumes used for washing and resuspension.

## 3. Dashboard & UI Enhancements

*   **Daily Usage Matrix**: Added a new pivot table in the "POSH Campaign Sim" tab to visualize costs per item broken down by day.
*   **Detailed Cost Breakdown**: Added "Coating" as a separate category in the Daily Cost stacked bar chart to visualize Day -1 expenses.
*   **Parameterized Unit Ops Display**:
    *   **Atomic Sub-Steps**: Operations can now be expanded to view every single atomic step (dispense, aspirate, incubate, centrifuge) with individual costs and times.
    *   **Labor Load**: Added a "Labor" column showing estimated human attention time (excluding incubation periods).
*   **Bug Fixes**:
    *   Fixed `TypeError` in `op_incubate` by adding a `name` parameter.
    *   Fixed `NameError` in `op_thaw` by removing legacy code.
    *   Fixed "Generic Vessel" display issues by updating `VesselLibrary` fallbacks.

## 4. Summary of Impact
The simulation now produces highly realistic cost estimates and material bills of materials (BOMs) for iPSC campaigns. The workflow steps mirror the physical actions performed in the lab, allowing for accurate labor and bottleneck analysis.
