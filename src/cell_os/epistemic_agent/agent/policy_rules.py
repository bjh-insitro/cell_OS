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
        self.last_decision = None  # v0.5.0: Canonical Decision object (kills side-channel)
        self.cycle = 0

    def propose_next_experiment(
        self,
        capabilities: dict,
        previous_observation: Optional[dict] = None
    ) -> Proposal:
        """Propose next experiment using chooser + beliefs.

        v0.4.2: Enforces pay-for-calibration constraints.
        v0.5.0: Returns Decision object with full provenance (kills side-channel pattern).
        """
        self.cycle += 1

        # Choose template based on current beliefs
        # v0.5.0: chooser.choose_next() now returns Decision (not tuple)
        decision = self.chooser.choose_next(
            beliefs=self.beliefs,
            budget_remaining_wells=self.budget_remaining,
            cycle=self.cycle
        )

        # Store decision for provenance (replaces side-channel last_decision_event)
        self.last_decision = decision

        # Extract template and kwargs from decision
        template_name = decision.chosen_template
        template_kwargs = dict(decision.chosen_kwargs)

        # Handle abort
        if template_name == "abort" or decision.kind == "abort":
            reason = template_kwargs.get("reason", "Unknown")
            raise RuntimeError(f"ABORT EXPERIMENT: {reason}")

        # Map template to proposal
        if template_name == "baseline_replicates":
            return self._template_baseline_replicates(capabilities, **template_kwargs)
        elif template_name == "edge_center_test":
            return self._template_edge_center_test(capabilities, **template_kwargs)
        elif template_name == "dose_ladder_coarse":
            return self._template_dose_ladder_coarse(capabilities, **template_kwargs)
        # v0.5.0: Assay ladder templates
        elif template_name == "calibrate_ldh_baseline":
            return self._template_calibrate_ldh_baseline(capabilities, **template_kwargs)
        elif template_name == "calibrate_cell_paint_baseline":
            return self._template_calibrate_cell_paint_baseline(capabilities, **template_kwargs)
        elif template_name == "calibrate_scrna_baseline":
            return self._template_calibrate_scrna_baseline(capabilities, **template_kwargs)
        elif template_name == "cell_paint_screen":
            return self._template_cell_paint_screen(capabilities, **template_kwargs)
        elif template_name == "scrna_upgrade_probe":
            return self._template_scrna_upgrade_probe(capabilities, **template_kwargs)
        elif template_name == "abort_insufficient_assay_gate_budget":
            assay = template_kwargs.get("assay", "unknown")
            block_reason = template_kwargs.get("block_reason", "Unknown")
            calib_plan = template_kwargs.get("calibration_plan", {})
            reason = template_kwargs.get("reason", f"Cannot afford {assay} gate calibration")
            raise RuntimeError(f"ABORT EXPERIMENT: {reason}. Calibration plan: {calib_plan}")
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

    def _template_calibrate_ldh_baseline(
        self,
        cap: dict,
        n_reps: int = 12,
        assay: str = "ldh",
        reason: str = "Calibrate LDH assay gate"
    ) -> Proposal:
        """Template: DMSO replicates for LDH assay calibration.

        v0.5.0: LDH proxy using noisy_morphology until real LDH assay added.
        """
        design_id = f"ldh_calib_{uuid.uuid4().hex[:8]}"

        wells = []
        for i in range(n_reps):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='ldh',  # Declare LDH assay intent (proxy: noisy_morphology)
                position_tag='center'
            ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. LDH gate calibration (proxy: noisy_morphology).",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_calibrate_cell_paint_baseline(
        self,
        cap: dict,
        n_reps: int = 12,
        assay: str = "cell_paint",
        reason: str = "Calibrate Cell Painting assay gate"
    ) -> Proposal:
        """Template: DMSO replicates for Cell Painting assay calibration.

        v0.5.0: Cell Painting uses noisy_morphology (existing signal).
        """
        design_id = f"cp_calib_{uuid.uuid4().hex[:8]}"

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
            hypothesis=f"{reason}. Cell Painting gate calibration (morphology features).",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_calibrate_scrna_baseline(
        self,
        cap: dict,
        n_reps: int = 6,  # Smaller, expensive
        assay: str = "scrna",
        reason: str = "Calibrate scRNA assay gate"
    ) -> Proposal:
        """Template: DMSO replicates for scRNA assay calibration (placeholder).

        v0.5.0: scRNA placeholder using noisy_morphology proxy. Small n_reps (expensive).
        """
        design_id = f"scrna_calib_{uuid.uuid4().hex[:8]}"

        wells = []
        for i in range(n_reps):
            wells.append(WellSpec(
                cell_line='A549',
                compound='DMSO',
                dose_uM=0.0,
                time_h=12.0,
                assay='scrna',  # Declare scRNA intent (proxy: noisy_morphology)
                position_tag='center'
            ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. scRNA gate calibration (placeholder: proxy morphology).",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_cell_paint_screen(
        self,
        cap: dict,
        reason: str = "Screen compounds with Cell Painting"
    ) -> Proposal:
        """Template: Small Cell Painting screen across diverse compounds."""
        design_id = f"cp_screen_{uuid.uuid4().hex[:8]}"

        # Diverse compound panel
        compounds = ['Staurosporine', 'Paclitaxel', 'Doxorubicin', 'DMSO']
        wells = []

        for compound in compounds:
            dose = 1.0 if compound != 'DMSO' else 0.0
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
            hypothesis=f"{reason}. Screen {len(compounds)} compounds with Cell Painting morphology.",
            wells=wells,
            budget_limit=self.budget_remaining
        )

    def _template_scrna_upgrade_probe(
        self,
        cap: dict,
        novelty_score: float = 0.0,
        ldh_viable: bool = True,
        reason: str = "Upgrade to scRNA for mechanistic insight"
    ) -> Proposal:
        """Template: scRNA probe on selected conditions (upgrade from CP).

        v0.5.0: Placeholder implementation. Real version would select conditions
        based on CP novelty clusters.
        """
        design_id = f"scrna_probe_{uuid.uuid4().hex[:8]}"

        # Placeholder: run scRNA on most interesting compound (proxy: use last non-DMSO)
        compound = 'Staurosporine'
        wells = []

        for rep in range(3):  # Small n for expensive assay
            wells.append(WellSpec(
                cell_line='A549',
                compound=compound,
                dose_uM=1.0,
                time_h=12.0,
                assay='scrna',
                position_tag='center'
            ))

        return Proposal(
            design_id=design_id,
            hypothesis=f"{reason}. scRNA probe (novelty={novelty_score:.3f}, ldh_viable={ldh_viable}).",
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
