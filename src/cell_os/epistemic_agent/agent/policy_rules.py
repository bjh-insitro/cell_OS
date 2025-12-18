"""
Evidence-driven policy using BeliefState + TemplateChooser.

v0.4.2: Pay-for-calibration regime with gate lock invariant.
- Uses BeliefState to track what we know (with receipts)
- Uses TemplateChooser to decide what to test next
- Hard constraint: no biology until noise gate earned
"""

import uuid
from typing import Optional
from ..schemas import WellSpec, Proposal
from ..beliefs import BeliefState
from ..acquisition import TemplateChooser


class RuleBasedPolicy:
    """Evidence-driven policy with accountability."""

    def __init__(self, budget: int = 384):
        self.budget = budget
        self.budget_remaining = budget
        self.beliefs = BeliefState()
        self.chooser = TemplateChooser()
        self.last_diagnostics = None
        self.cycle = 0

    def propose_next_experiment(
        self,
        capabilities: dict,
        previous_observation: Optional[dict] = None
    ) -> Proposal:
        """Propose next experiment using chooser + beliefs.

        v0.4.2: Enforces pay-for-calibration constraints.
        """
        self.cycle += 1

        # Choose template based on current beliefs
        template_name, template_kwargs = self.chooser.choose_next(
            beliefs=self.beliefs,
            budget_remaining_wells=self.budget_remaining
        )

        # Handle abort
        if template_name == "abort":
            reason = template_kwargs.get("reason", "Unknown")
            raise RuntimeError(f"ABORT EXPERIMENT: {reason}")

        # Map template to proposal
        if template_name == "baseline_replicates":
            return self._template_baseline_replicates(capabilities, **template_kwargs)
        elif template_name == "edge_center_test":
            return self._template_edge_center_test(capabilities, **template_kwargs)
        elif template_name == "dose_ladder_coarse":
            return self._template_dose_ladder_coarse(capabilities, **template_kwargs)
        else:
            # Fallback
            return self._template_baseline_replicates(capabilities, n_reps=12, reason="Fallback")

    def _template_baseline_replicates(
        self,
        cap: dict,
        n_reps: int = 12,
        reason: str = "Measure baseline noise"
    ) -> Proposal:
        """Template: DMSO replicates at center position."""
        design_id = f"baseline_{uuid.uuid4().hex[:8]}"

        wells = []
        for i in range(n_reps):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='cell_painting',
                position_tag='center'
            ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. Calibration: measure instrument noise to establish confidence intervals.",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_edge_center_test(
        self,
        cap: dict,
        reason: str = "Test edge effects"
    ) -> Proposal:
        """Template: Compare edge vs center wells."""
        design_id = f"edge_test_{uuid.uuid4().hex[:8]}"

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

        # 6 tBHQ edge, 6 tBHQ center (for robustness)
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

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. Test if well position (edge vs center) introduces systematic bias.",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_dose_ladder_coarse(
        self,
        cap: dict,
        reason: str = "Explore dose-response"
    ) -> Proposal:
        """Template: Coarse dose ladder for compound."""
        design_id = f"dose_ladder_{uuid.uuid4().hex[:8]}"

        # Pick untested compound
        tested = self.beliefs.tested_compounds - {'DMSO'}
        available = set(cap.get('compounds', [])) - {'DMSO'} - tested

        if available:
            compound = sorted(available)[0]
        else:
            compound = 'tBHQ'  # fallback

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

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. Map dose-response for {compound} across 4 log-spaced doses.",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def update_from_observation(self, observation: dict):
        """Update beliefs from observation.

        v0.4.2: Updates BeliefState with evidence tracking.
        """
        self.budget_remaining = observation.budget_remaining

        # Update beliefs (returns events + diagnostics)
        events, diagnostics = self.beliefs.update(observation, cycle=self.cycle)

        # Store diagnostics for logging
        self.last_diagnostics = diagnostics
