# src/core/process.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from src.core.world_model import Artifact, ExecutionRecord, UnitOp
from src.core.store import ArtifactStore


@dataclass
class ProcessResult:
    outputs: List[Artifact]
    records: List[ExecutionRecord]
    total_cost_usd: float


class Process:
    """
    A logical grouping of UnitOps that transforms input Artifacts into output Artifacts.

    For now this is a simple linear chain:
    - Step 0 consumes the input_ids from the store.
    - Each subsequent UnitOp consumes the outputs of the previous step.

    Optionally enforces expected input kinds for the initial artifacts.
    """

    def __init__(
        self,
        name: str,
        steps: List[UnitOp],
        expected_input_kinds: Optional[List[str]] = None,
    ) -> None:
        self.name = name
        self.steps = steps
        self.expected_input_kinds = expected_input_kinds

    def _validate_initial_inputs(
        self,
        artifacts: List[Artifact],
    ) -> None:
        """
        Validate that initial artifacts match expected_input_kinds if provided.

        Rules:
          - If expected_input_kinds is None:
              If the first UnitOp declares input_kinds, reuse those as expectations.
          - If expected_input_kinds has length 1:
              All inputs must be of that kind.
          - If lengths match:
              Check pairwise.
        """
        if not artifacts:
            raise ValueError("Process requires at least one starting Artifact")

        # Resolve effective expectations
        kinds = self.expected_input_kinds
        if kinds is None and self.steps:
            kinds = self.steps[0].input_kinds

        if not kinds:
            # No type expectations, nothing to validate
            return

        if len(kinds) == 1:
            expected = kinds[0]
            for i, art in enumerate(artifacts):
                if art.kind != expected:
                    raise ValueError(
                        f"Process '{self.name}' expected initial kind '{expected}' "
                        f"for all inputs, got '{art.kind}' at position {i}"
                    )
        else:
            if len(artifacts) != len(kinds):
                raise ValueError(
                    f"Process '{self.name}' expected {len(kinds)} inputs, "
                    f"got {len(artifacts)}"
                )
            for i, (art, expected) in enumerate(zip(artifacts, kinds)):
                if art.kind != expected:
                    raise ValueError(
                        f"Process '{self.name}' expected initial kind '{expected}' "
                        f"at position {i}, got '{art.kind}'"
                    )

    def run(
        self,
        store: ArtifactStore,
        input_ids: List[str],
        cost_engine: Optional["CostEngine"] = None,
        **op_params: Dict[str, Any],
    ) -> ProcessResult:
        """
        Run the process starting from the input artifacts in the store.

        Parameters
        ----------
        store:
            ArtifactStore containing initial artifacts.
        input_ids:
            List of artifact ids to use as inputs for the first step.
        cost_engine:
            Optional CostEngine to compute real costs.
        op_params:
            Mapping from UnitOp.name to a dict of parameters.
            Example:
                {
                    "op_passage": {"target_vessel": "plate_6well_02", "split_ratio": 4.0},
                    "op_feed": {"media": "DMEM+10%FBS+PenStrep"},
                }

        Returns
        -------
        ProcessResult
            outputs: final Artifacts from the last step
            records: list of ExecutionRecords in execution order
            total_cost_usd: sum of cost_usd across all ExecutionRecords
        """
        if not input_ids:
            raise ValueError("Process.run requires at least one input_id")

        # Resolve initial artifacts
        current_artifacts: List[Artifact] = [
            store.get(aid) for aid in input_ids
        ]

        # Validate initial types at the process boundary
        self._validate_initial_inputs(current_artifacts)

        records: List[ExecutionRecord] = []

        for step in self.steps:
            params_for_step = op_params.get(step.name, {})
            if params_for_step is None:
                params_for_step = {}

            # Run the UnitOp
            new_artifacts, record = step(*current_artifacts, **params_for_step)
            
            # Compute real cost if engine provided
            if cost_engine:
                real_cost = cost_engine.compute_cost(
                    step, 
                    current_artifacts, 
                    new_artifacts, 
                    params_for_step
                )
                record.cost_usd = real_cost

            # Register new artifacts in the store
            for art in new_artifacts:
                store.add(art)

            # Update execution history
            records.append(record)
            current_artifacts = new_artifacts

        total_cost = sum(rec.cost_usd for rec in records)

        return ProcessResult(
            outputs=current_artifacts,
            records=records,
            total_cost_usd=total_cost,
        )
