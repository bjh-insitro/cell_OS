"""
Experimental World: Wraps the simulator without exposing god mode.

The world executes experiments and returns only what a real experimentalist would see:
- Summary statistics per condition
- QC flags (but agent must interpret)
- No internal parameters, no noise terms, no "true" values
"""

import sys
import uuid
import hashlib
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
from dataclasses import dataclass

# Import standalone simulator components
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
import standalone_cell_thalamus as sim

from .schemas import WellSpec, Proposal, Observation, ConditionSummary


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
        self.history: List[Observation] = []

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

    def run_experiment(self, proposal: Proposal) -> Observation:
        """Execute proposed experiment and return observations.

        Args:
            proposal: Agent's experiment proposal

        Returns:
            Observation with summary statistics (no raw wells by default)

        Raises:
            ValueError: If proposal exceeds budget or has invalid parameters
        """
        # Validate budget
        wells_requested = len(proposal.wells)
        if wells_requested > self.budget_remaining:
            raise ValueError(
                f"Insufficient budget: requested {wells_requested}, "
                f"remaining {self.budget_remaining}"
            )

        # Convert WellSpec list to WellAssignment list
        well_assignments = self._convert_proposal_to_assignments(proposal)

        # Run simulation (using standalone simulator)
        results = self._simulate_wells(well_assignments, proposal.design_id)

        # Aggregate results into summary statistics
        observation = self._aggregate_results(
            results,
            proposal.design_id,
            wells_requested
        )

        # Update budget
        self.budget_remaining -= wells_requested
        self.history.append(observation)

        return observation

    def _convert_proposal_to_assignments(
        self,
        proposal: Proposal
    ) -> List[sim.WellAssignment]:
        """Convert agent's WellSpec to simulator's WellAssignment.

        This is where we map position_tag to actual well positions
        without exposing the mapping to the agent.
        """
        assignments = []

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

        return assignments

    def _simulate_wells(
        self,
        assignments: List[sim.WellAssignment],
        design_id: str
    ) -> List[Dict[str, Any]]:
        """Run simulation for list of wells.

        Uses standalone simulator's simulate_well function.
        """
        results = []
        for well in assignments:
            result = sim.simulate_well(well, design_id)
            if result is not None:
                results.append(result)
        return results

    def _aggregate_results(
        self,
        results: List[Dict[str, Any]],
        design_id: str,
        wells_requested: int
    ) -> Observation:
        """Aggregate raw results into summary statistics.

        Agent only sees summaries, not raw well values.
        This prevents "god mode" leakage.
        """
        # Group by condition
        conditions = defaultdict(list)

        for res in results:
            # Determine position_tag from well_id
            well_id = res['well_id']
            if well_id in self.EDGE_WELLS:
                position_tag = 'edge'
            else:
                position_tag = 'center'

            # Create condition key
            key = (
                res['cell_line'],
                res['compound'],
                res['dose_uM'],
                res['timepoint_h'],
                'cell_painting',  # For now, single assay
                position_tag
            )

            # Extract response from measured signal (not "true" viability)
            # Agent should see noisy measurements like a real experimentalist
            # Use morphology mean (has biological + technical noise)
            morph = res['morphology']
            response = np.mean([morph['er'], morph['mito'], morph['nucleus'],
                                morph['actin'], morph['rna']])

            # Note: LDH signal is zero for DMSO (healthy cells), not useful for baseline noise

            conditions[key].append({
                'response': response,
                'well_id': well_id,
                'failed': False,  # TODO: detect failures
            })

        # Compute summary statistics per condition
        summaries = []
        for key, values in conditions.items():
            cell_line, compound, dose, time, assay, pos = key

            # Extract responses
            responses = [v['response'] for v in values]
            n = len(responses)

            if n == 0:
                continue

            mean_val = np.mean(responses)
            std_val = np.std(responses, ddof=1) if n > 1 else 0.0
            sem_val = std_val / np.sqrt(n) if n > 0 else 0.0
            cv_val = std_val / mean_val if mean_val > 0 else 0.0
            min_val = np.min(responses)
            max_val = np.max(responses)

            # Outlier detection (simple Z-score > 3)
            n_outliers = 0
            if n > 2:
                z_scores = np.abs((responses - mean_val) / std_val) if std_val > 0 else np.zeros(n)
                n_outliers = int(np.sum(z_scores > 3))

            summary = ConditionSummary(
                cell_line=cell_line,
                compound=compound,
                dose_uM=dose,
                time_h=time,
                assay=assay,
                position_tag=pos,
                n_wells=n,
                mean=mean_val,
                std=std_val,
                sem=sem_val,
                cv=cv_val,
                min_val=min_val,
                max_val=max_val,
                n_failed=0,  # TODO: track actual failures
                n_outliers=n_outliers,
            )
            summaries.append(summary)

        # Generate QC flags (coarse, agent must interpret)
        qc_flags = self._generate_qc_flags(summaries)

        observation = Observation(
            design_id=design_id,
            conditions=summaries,
            wells_spent=wells_requested,
            budget_remaining=self.budget_remaining - wells_requested,
            qc_flags=qc_flags,
        )

        return observation

    def _generate_qc_flags(self, summaries: List[ConditionSummary]) -> List[str]:
        """Generate coarse QC flags without exposing internals.

        Agent must interpret these.
        """
        flags = []

        # Check for edge bias (if both edge and center present)
        edge_means = [s.mean for s in summaries if s.position_tag == 'edge']
        center_means = [s.mean for s in summaries if s.position_tag == 'center']

        if edge_means and center_means:
            edge_avg = np.mean(edge_means)
            center_avg = np.mean(center_means)
            diff_pct = abs(edge_avg - center_avg) / center_avg if center_avg > 0 else 0

            if diff_pct > 0.1:  # >10% difference
                direction = "lower" if edge_avg < center_avg else "higher"
                flags.append(
                    f"Edge wells show {diff_pct:.1%} {direction} signal than center"
                )

        # Check for high variance
        high_cv_conditions = [s for s in summaries if s.cv > 0.15]
        if high_cv_conditions:
            flags.append(
                f"{len(high_cv_conditions)}/{len(summaries)} conditions have CV >15%"
            )

        # Check for outliers
        total_outliers = sum(s.n_outliers for s in summaries)
        if total_outliers > 0:
            flags.append(f"{total_outliers} wells flagged as outliers (Z>3)")

        return flags
