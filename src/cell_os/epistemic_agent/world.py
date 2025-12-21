"""
Experimental World: Wraps the simulator without exposing god mode.

The world executes experiments and returns only what a real experimentalist would see:
- Raw well-level results (no aggregation)
- Physical locations (concrete, not abstract)
- No internal parameters, no noise terms, no "true" values

Aggregation happens in a separate layer (observation_aggregator.py).
"""

import sys
import uuid
import hashlib
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass

# Import standalone simulator components
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
import standalone_cell_thalamus as sim

# Import canonical types from core
from ..core.observation import RawWellResult
from ..core.experiment import SpatialLocation, Treatment
from ..core.assay import AssayType

# Import legacy schemas for backward compatibility (temporarily)
from .schemas import WellSpec, Proposal


class ExperimentalWorld:
    """Interface for agent to query the biological world."""

    def __init__(self, budget_wells: int = 384, seed: int = 0):
        """Initialize experimental system.

        Args:
            budget_wells: Total well budget for the campaign
            seed: Random seed for deterministic runs
        """
        self.budget_total = budget_wells
        self.budget_remaining = budget_wells
        self.seed = seed
        self.history: List[Tuple[RawWellResult, ...]] = []  # Track raw results

        # Plate geometry (96-well)
        self.ROWS = [chr(65 + i) for i in range(8)]  # A-H
        self.COLS = [f"{i:02d}" for i in range(1, 13)]  # 01-12

        # Edge wells (for position_tag mapping)
        self.EDGE_WELLS = set()
        for row in ['A', 'H']:  # Top/bottom rows
            for col in self.COLS:
                self.EDGE_WELLS.add(f"{row}{col}")
        for col in ['01', '12']:  # Left/right columns
            for row in self.ROWS:
                self.EDGE_WELLS.add(f"{row}{col}")

        # Center wells (non-edge)
        all_wells = {f"{r}{c}" for r in self.ROWS for c in self.COLS}
        self.CENTER_WELLS = list(all_wells - self.EDGE_WELLS)
        self.EDGE_WELLS = list(self.EDGE_WELLS)

    def get_capabilities(self) -> Dict[str, Any]:
        """Return what instruments/compounds/cell lines are available.

        This is what the agent "knows" at t=0.
        """
        return {
            'cell_lines': ['A549', 'HepG2'],
            'compounds': [
                'DMSO',  # Vehicle control
                'tBHQ', 'H2O2',  # Oxidative stress
                'tunicamycin', 'thapsigargin',  # ER stress
                'CCCP', 'oligomycin',  # Mitochondrial
                'etoposide',  # DNA damage
                'MG132',  # Proteasome
                'nocodazole', 'paclitaxel',  # Microtubule
            ],
            'assays': ['cell_painting', 'ldh_cytotoxicity'],
            'dose_range_uM': (0.0, 1000.0),  # Valid dose range
            'time_range_h': (0.0, 72.0),     # Valid timepoint range
            'position_tags': ['edge', 'center', 'any'],
            'plate_format': '96-well',
            'budget_total': self.budget_total,
            'budget_remaining': self.budget_remaining,
        }

    def run_experiment(self, proposal: Proposal) -> Tuple[RawWellResult, ...]:
        """Execute proposed experiment and return raw well results.

        The world executes any physically valid proposal. It does NOT:
        - Aggregate or summarize results
        - Validate scientific quality (confounding, power, etc.)
        - Compute statistics or interpret data

        That's the aggregation layer's and agent's job.

        Args:
            proposal: Agent's experiment proposal

        Returns:
            Tuple of RawWellResult (raw per-well measurements, no aggregation)

        Raises:
            ValueError: If proposal exceeds budget (physical constraint)
        """
        # Validate budget (this IS a physical constraint)
        wells_requested = len(proposal.wells)
        if wells_requested > self.budget_remaining:
            raise ValueError(
                f"Insufficient budget: requested {wells_requested}, "
                f"remaining {self.budget_remaining}"
            )

        # Convert and execute
        well_assignments, positions = self._convert_proposal_to_assignments_with_positions(proposal)
        raw_results = self._simulate_wells(well_assignments, positions, proposal.design_id)

        # Update budget
        self.budget_remaining -= wells_requested
        self.history.append(raw_results)

        return raw_results

    def _convert_proposal_to_assignments(
        self,
        proposal: Proposal
    ) -> List[sim.WellAssignment]:
        """Convert agent's WellSpec to simulator's WellAssignment.

        This is where we map position_tag to actual well positions
        without exposing the mapping to the agent.
        """
        assignments, _ = self._convert_proposal_to_assignments_with_positions(proposal)
        return assignments

    def _convert_proposal_to_assignments_with_positions(
        self,
        proposal: Proposal
    ) -> tuple[List[sim.WellAssignment], List[str]]:
        """Convert agent's WellSpec to simulator's WellAssignment, returning both assignments and positions.

        Returns:
            (assignments, positions): List of WellAssignment and list of well_pos strings
        """
        assignments = []
        positions = []

        # Allocate wells based on position_tag
        edge_iter = iter(self.EDGE_WELLS)
        center_iter = iter(self.CENTER_WELLS)
        any_wells = self.CENTER_WELLS + self.EDGE_WELLS
        any_iter = iter(any_wells)

        for i, spec in enumerate(proposal.wells):
            # Select well position based on position_tag
            if spec.position_tag == 'edge':
                well_id = next(edge_iter, f"E{i+1:02d}")
            elif spec.position_tag == 'center':
                well_id = next(center_iter, f"C{i+1:02d}")
            else:  # 'any'
                well_id = next(any_iter, f"A{i+1:02d}")

            # Create WellAssignment (simulator's format)
            assignment = sim.WellAssignment(
                well_id=well_id,
                cell_line=spec.cell_line,
                compound=spec.compound,
                dose_uM=spec.dose_uM,
                timepoint_h=spec.time_h,
                plate_id=f"Plate_{proposal.design_id[:8]}",
                day=1,  # Single day for now
                operator="Agent",
                is_sentinel=False
            )
            assignments.append(assignment)
            positions.append(well_id)

        return assignments, positions

    def _simulate_wells(
        self,
        assignments: List[sim.WellAssignment],
        positions: List[str],
        design_id: str
    ) -> Tuple[RawWellResult, ...]:
        """Run simulation for list of wells.

        Uses standalone simulator's simulate_well function and converts
        to canonical RawWellResult objects.

        Args:
            assignments: Simulator's WellAssignment objects
            positions: Corresponding well positions (same order)
            design_id: Design identifier

        Returns:
            Tuple of RawWellResult (canonical format)
        """
        results = []
        for well_assignment, well_pos in zip(assignments, positions):
            # Run simulator
            sim_result = sim.simulate_well(well_assignment, design_id)
            if sim_result is None:
                continue

            # Convert to canonical RawWellResult
            location = SpatialLocation(
                plate_id=sim_result.get('plate_id', f"Plate_{design_id[:8]}"),
                well_id=sim_result['well_id']
            )

            treatment = Treatment(
                compound=sim_result['compound'],
                dose_uM=sim_result['dose_uM']
            )

            # Map assay string to AssayType enum
            # For now, epistemic agent only uses cell_painting
            assay = AssayType.CELL_PAINTING

            # Extract readouts (morphology channels)
            morph = sim_result['morphology']
            readouts = {
                'morphology': {
                    'er': morph['er'],
                    'mito': morph['mito'],
                    'nucleus': morph['nucleus'],
                    'actin': morph['actin'],
                    'rna': morph['rna'],
                }
            }

            # Extract LDH if present
            if 'ldh' in sim_result:
                readouts['ldh'] = sim_result['ldh']

            # QC metadata (optional)
            qc = {}
            if 'failed' in sim_result:
                qc['failed'] = sim_result['failed']
            if 'failure_type' in sim_result:
                qc['failure_type'] = sim_result['failure_type']

            raw_result = RawWellResult(
                location=location,
                cell_line=sim_result['cell_line'],
                treatment=treatment,
                assay=assay,
                observation_time_h=sim_result['timepoint_h'],
                readouts=readouts,
                qc=qc
            )

            results.append(raw_result)

        return tuple(results)

    # =============================================================================
    # AGGREGATION REMOVED: World is now a pure executor
    # =============================================================================
    # The _aggregate_results and _generate_qc_flags methods have been removed.
    # Aggregation now happens in observation_aggregator.py (separate layer).
    #
    # World's job:
    #   - Execute experiments (simulate wells)
    #   - Return raw RawWellResult objects
    #   - Track budget
    #
    # Not world's job:
    #   - Compute statistics (mean, std, sem, cv)
    #   - Group by conditions
    #   - Generate QC flags
    #   - Interpret results
    # ============================================================================
