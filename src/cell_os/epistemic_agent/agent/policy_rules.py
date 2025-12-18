"""
Rule-based baseline policy (dumb but honest).

This is the "control" scientist that follows a fixed protocol.
No LLM, no Bayesian math - just honest epistemology:
1. First, measure baseline noise
2. Test if position matters
3. Find dose-response curves
4. Test if timing matters
5. Check generalization

This gives us:
- A working loop to debug interface
- A baseline to beat with smarter agents
- Proof that the API isn't leaky (if dumb policy discovers mid-dose, API is broken)
"""

import uuid
from typing import List, Optional
from ..schemas import WellSpec, Proposal


class RuleBasedPolicy:
    """Dumb but honest experimental scientist."""

    def __init__(self, budget: int = 384):
        self.budget_remaining = budget
        self.cycle = 0
        self.history = []

        # Simple state tracking
        self.baseline_measured = False
        self.edge_tested = False
        self.dose_responses = {}  # compound -> bool (tested?)
        self.time_tested = False

    def propose_next_experiment(
        self,
        capabilities: dict,
        previous_observation: Optional[dict] = None
    ) -> Proposal:
        """Propose next experiment based on cycle number.

        This is intentionally rigid to avoid "being clever."
        """
        self.cycle += 1

        if self.cycle == 1:
            return self._cycle1_baseline_replicates(capabilities)
        elif self.cycle == 2:
            return self._cycle2_edge_center_test(capabilities)
        elif self.cycle == 3:
            return self._cycle3_dose_ladder_coarse(capabilities)
        elif self.cycle == 4:
            return self._cycle4_dose_ladder_edge(capabilities)
        elif self.cycle == 5:
            return self._cycle5_time_probe(capabilities)
        else:
            # After cycle 5, just repeat dose ladders for other compounds
            return self._cycle_n_explore_compounds(capabilities)

    def _cycle1_baseline_replicates(self, cap: dict) -> Proposal:
        """Cycle 1: Measure baseline variability with DMSO controls."""
        design_id = f"cycle01_baseline_{uuid.uuid4().hex[:8]}"

        wells = []
        # 12 DMSO replicates at center, 12h
        for i in range(12):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='center'
            ))

        hypothesis = (
            "Measure baseline measurement variability. "
            "Expect CV ~2-5% if instrument is well-calibrated. "
            "This establishes noise floor before testing compounds."
        )

        return Proposal(
            design_id=design_id,
            hypothesis=hypothesis,
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _cycle2_edge_center_test(self, cap: dict) -> Proposal:
        """Cycle 2: Test if well position affects signal."""
        design_id = f"cycle02_edge_center_{uuid.uuid4().hex[:8]}"

        wells = []

        # 6 DMSO edge, 6 DMSO center
        for i in range(6):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='edge'
            ))
        for i in range(6):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='center'
            ))

        # 6 mild stressor edge, 6 mild stressor center
        # Use tBHQ at 10µM (mild oxidative stress)
        for i in range(6):
            wells.append(WellSpec(
                cell_line='A549',
                compound='tBHQ',
                dose_uM=10.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='edge'
            ))
        for i in range(6):
            wells.append(WellSpec(
                cell_line='A549',
                compound='tBHQ',
                dose_uM=10.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='center'
            ))

        hypothesis = (
            "Test if well position (edge vs center) affects measurements. "
            "If edge wells show systematic bias (e.g., evaporation, temperature), "
            "I need to either avoid them or correct for it."
        )

        return Proposal(
            design_id=design_id,
            hypothesis=hypothesis,
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _cycle3_dose_ladder_coarse(self, cap: dict) -> Proposal:
        """Cycle 3: Coarse dose-response for one compound."""
        design_id = f"cycle03_dose_ladder_{uuid.uuid4().hex[:8]}"

        wells = []

        # Test tunicamycin (strong ER stressor) at 4 doses, n=3 each
        # Doses: 0.01, 0.1, 1.0, 10.0 µM (geometric spacing)
        doses = [0.01, 0.1, 1.0, 10.0]

        for dose in doses:
            for rep in range(3):
                wells.append(WellSpec(
                    cell_line='A549',
                    compound='tunicamycin',
                    dose_uM=dose,
                    time_h=12.0,
                    assay='cell_painting',
                    position_tag='center'  # Use center to avoid edge bias
                ))

        hypothesis = (
            "Find dose-response curve for tunicamycin. "
            "Expect sigmoid shape with IC50 somewhere in 0.01-10 µM range. "
            "This will tell me what doses cause toxicity."
        )

        return Proposal(
            design_id=design_id,
            hypothesis=hypothesis,
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _cycle4_dose_ladder_edge(self, cap: dict) -> Proposal:
        """Cycle 4: Same dose ladder but on edge wells (test consistency)."""
        design_id = f"cycle04_edge_ladder_{uuid.uuid4().hex[:8]}"

        wells = []

        # Same as cycle 3 but on edge wells
        doses = [0.01, 0.1, 1.0, 10.0]

        for dose in doses:
            for rep in range(3):
                wells.append(WellSpec(
                    cell_line='A549',
                    compound='tunicamycin',
                    dose_uM=dose,
                    time_h=12.0,
                    assay='cell_painting',
                    position_tag='edge'
                ))

        hypothesis = (
            "Repeat dose-response on edge wells. "
            "If IC50 shifts or curve shape changes, edge bias is dose-dependent. "
            "If consistent, edge bias is just a constant offset."
        )

        return Proposal(
            design_id=design_id,
            hypothesis=hypothesis,
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _cycle5_time_probe(self, cap: dict) -> Proposal:
        """Cycle 5: Test if timing matters."""
        design_id = f"cycle05_time_probe_{uuid.uuid4().hex[:8]}"

        wells = []

        # Test mid-dose tunicamycin at 4 timepoints, n=2 each
        # Use 1.0 µM (likely around IC50 based on cycle 3)
        timepoints = [6.0, 12.0, 24.0, 48.0]

        for time in timepoints:
            for rep in range(2):
                wells.append(WellSpec(
                    cell_line='A549',
                    compound='tunicamycin',
                    dose_uM=1.0,
                    time_h=time,
                    assay='cell_painting',
                    position_tag='center'
                ))

        hypothesis = (
            "Test if response changes over time. "
            "Does toxicity increase progressively (cumulative)? "
            "Or is the effect determined early (commitment)?"
        )

        return Proposal(
            design_id=design_id,
            hypothesis=hypothesis,
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _cycle_n_explore_compounds(self, cap: dict) -> Proposal:
        """Cycles 6+: Test other compounds with coarse dose ladders."""
        design_id = f"cycle{self.cycle:02d}_explore_{uuid.uuid4().hex[:8]}"

        # Pick next untested compound
        tested = set(self.dose_responses.keys())
        available = set(cap['compounds']) - {'DMSO'} - tested

        if not available:
            # All compounds tested, just add more replicates
            compound = 'tBHQ'
        else:
            compound = sorted(available)[0]  # Deterministic selection

        self.dose_responses[compound] = True

        wells = []
        doses = [0.01, 0.1, 1.0, 10.0]

        for dose in doses:
            for rep in range(3):
                wells.append(WellSpec(
                    cell_line='A549',
                    compound=compound,
                    dose_uM=dose,
                    time_h=12.0,
                    assay='cell_painting',
                    position_tag='center'
                ))

        hypothesis = (
            f"Explore dose-response for {compound}. "
            "Building library of dose-response curves across compounds."
        )

        return Proposal(
            design_id=design_id,
            hypothesis=hypothesis,
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def update_from_observation(self, observation: dict):
        """Update internal state based on observation.

        For rule-based policy, this is just bookkeeping.
        Smarter agents would update beliefs here.
        """
        self.budget_remaining = observation.budget_remaining
        self.history.append(observation)

        # Simple state updates
        if self.cycle == 1:
            self.baseline_measured = True
        elif self.cycle == 2:
            self.edge_tested = True
        elif self.cycle == 5:
            self.time_tested = True
