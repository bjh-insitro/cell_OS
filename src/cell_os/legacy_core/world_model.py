import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Optional, Sequence
from abc import ABC, abstractmethod

# 1. Core Data Structures

@dataclass
class Artifact:
    id: str
    kind: str  # e.g. "CellPopulation", "Plate", "ReagentAliquot", "ImageSet"
    state: Dict[str, Any]
    lineage: List[str] = field(default_factory=list)


@dataclass
class ExecutionRecord:
    unit_op_name: str
    inputs: List[str]      # input artifact ids
    outputs: List[str]     # output artifact ids
    params: Dict[str, Any]
    time_start: Optional[float] = None
    time_end: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    cost_usd: float = 0.0


class UnitOp(ABC):
    """
    Base class for all Unit Operations.

    Each UnitOp can optionally declare:
      - input_kinds: kinds of Artifacts it expects
      - base_cost_usd: nominal cost per execution (can be overridden)
    """

    name: str
    input_kinds: Optional[List[str]]
    base_cost_usd: float

    def __init__(
        self,
        name: str,
        input_kinds: Optional[List[str]] = None,
        base_cost_usd: float = 0.0,
    ):
        self.name = name
        # Example: ["CellPopulation"] for single input
        #          ["CellPopulation", "VirusStock"] for two inputs
        self.input_kinds = input_kinds
        self.base_cost_usd = base_cost_usd

    def __call__(self, *artifacts: Artifact, **params: Any) -> Tuple[List[Artifact], ExecutionRecord]:
        return self.run(*artifacts, **params)

    def validate_inputs(self, artifacts: Sequence[Artifact]) -> None:
        """
        Check that the provided Artifacts match the declared input_kinds, if any.

        Rules:
          - If input_kinds is None: no checking.
          - If len(input_kinds) == 1: all inputs must be of that kind.
          - If len(input_kinds) == len(artifacts): pairwise match.
        """
        if self.input_kinds is None:
            return

        if len(self.input_kinds) == 1:
            expected = self.input_kinds[0]
            for i, art in enumerate(artifacts):
                if art.kind != expected:
                    raise ValueError(
                        f"{self.name} expects input kind '{expected}' "
                        f"for all inputs, got '{art.kind}' at position {i}"
                    )
        else:
            if len(artifacts) != len(self.input_kinds):
                raise ValueError(
                    f"{self.name} expects {len(self.input_kinds)} inputs, "
                    f"got {len(artifacts)}"
                )
            for i, (art, expected) in enumerate(zip(artifacts, self.input_kinds)):
                if art.kind != expected:
                    raise ValueError(
                        f"{self.name} expects input kind '{expected}' "
                        f"at position {i}, got '{art.kind}'"
                    )

    @abstractmethod
    def run(
        self,
        *artifacts: Artifact,
        **params: Any,
    ) -> Tuple[List[Artifact], ExecutionRecord]:
        """
        Implementations must:
          1. Validate input artifact kinds.
          2. Create new artifact(s) (no in place mutation).
          3. Populate an ExecutionRecord linking input ids to output ids.
        """
        raise NotImplementedError


# 2. Concrete UnitOps

class PassageOp(UnitOp):
    def __init__(self):
        super().__init__(
            "op_passage",
            input_kinds=["CellPopulation"],
            base_cost_usd=2.50,  # nominal, adjust later
        )

    def run(
        self,
        *artifacts: Artifact,
        **params: Any,
    ) -> Tuple[List[Artifact], ExecutionRecord]:
        # Validate inputs
        if len(artifacts) != 1:
            raise ValueError(f"PassageOp expects exactly 1 input artifact, got {len(artifacts)}")

        self.validate_inputs(artifacts)
        input_artifact = artifacts[0]

        # Extract params with defaults
        target_vessel = params.get("target_vessel")
        if not target_vessel:
            raise ValueError("PassageOp requires 'target_vessel' parameter")

        split_ratio = params.get("split_ratio")
        if split_ratio is None:
            raise ValueError("PassageOp requires 'split_ratio' parameter")
        if split_ratio <= 0:
            raise ValueError("PassageOp requires 'split_ratio' > 0")

        dissociation_method = params.get("dissociation_method", "trypsin")

        # Record start time
        t_start = time.time()

        # Create new state (no in place mutation)
        old_state = input_artifact.state
        new_state = old_state.copy()

        # Update state
        new_state["vessel_id"] = target_vessel
        # Keep cell_count as float for consistency
        old_count = float(old_state.get("cell_count", 0))
        new_state["cell_count"] = old_count / split_ratio
        new_state["passage_number"] = old_state.get("passage_number", 0) + 1
        new_state["time_since_last_feed_h"] = 0.0
        # Inject dissociation method into state for traceability
        new_state["last_passage_dissociation_method"] = dissociation_method

        # Create new Artifact
        new_id = str(uuid.uuid4())
        new_lineage = input_artifact.lineage + [input_artifact.id]

        new_artifact = Artifact(
            id=new_id,
            kind="CellPopulation",
            state=new_state,
            lineage=new_lineage,
        )

        # Record end time
        t_end = time.time()

        # Create ExecutionRecord
        record = ExecutionRecord(
            unit_op_name=self.name,
            inputs=[input_artifact.id],
            outputs=[new_artifact.id],
            params=params,
            time_start=t_start,
            time_end=t_end,
            cost_usd=self.base_cost_usd,
        )

        return [new_artifact], record


class FeedOp(UnitOp):
    def __init__(self):
        super().__init__(
            "op_feed",
            input_kinds=["CellPopulation"],
            base_cost_usd=0.75,  # nominal, adjust later
        )

    def run(
        self,
        *artifacts: Artifact,
        **params: Any,
    ) -> Tuple[List[Artifact], ExecutionRecord]:
        if len(artifacts) != 1:
            raise ValueError(f"FeedOp expects exactly 1 input artifact, got {len(artifacts)}")

        self.validate_inputs(artifacts)
        input_artifact = artifacts[0]

        media = params.get("media")
        if not media:
            raise ValueError("FeedOp requires 'media' parameter")

        t_start = time.time()

        old_state = input_artifact.state
        new_state = old_state.copy()
        new_state["media"] = media
        new_state["time_since_last_feed_h"] = 0.0

        new_id = str(uuid.uuid4())
        new_lineage = input_artifact.lineage + [input_artifact.id]

        new_artifact = Artifact(
            id=new_id,
            kind="CellPopulation",
            state=new_state,
            lineage=new_lineage,
        )

        t_end = time.time()

        record = ExecutionRecord(
            unit_op_name=self.name,
            inputs=[input_artifact.id],
            outputs=[new_artifact.id],
            params=params,
            time_start=t_start,
            time_end=t_end,
            cost_usd=self.base_cost_usd,
        )

        return [new_artifact], record


class WorldModel:
    """
    Container for the static knowledge of the world.
    """
    def __init__(
        self, 
        config: Dict[str, Any], 
        inventory: Optional[Any] = None, 
        vessel_library: Optional[Any] = None
    ):
        self.config = config
        self.inventory = inventory
        self.vessel_library = vessel_library
        
        # Extract key constraints
        self.allowed_cell_lines = config.get("cell_lines", [])
        self.allowed_compounds = config.get("compounds", [])
        self.dose_grid = config.get("dose_grid", [])

    @classmethod
    def from_config(
        cls, 
        config: Dict[str, Any], 
        inventory: Optional[Any] = None, 
        vessel_library: Optional[Any] = None
    ) -> "WorldModel":
        return cls(config, inventory, vessel_library)


# 3. Chained Usage Example

if __name__ == "__main__":
    # Construct starting Artifact
    start_artifact = Artifact(
        id="art_001",
        kind="CellPopulation",
        state={
            "cell_line": "HepG2",
            "media": "DMEM+10%FBS",
            "vessel_id": "plate_6well_01",
            "cell_count": 1_000_000,
            "passage_number": 5,
            "time_since_last_feed_h": 24.0,
        },
        lineage=[],
    )

    # Initialize Ops
    passage_op = PassageOp()
    feed_op = FeedOp()

    print("--- START ---")
    print(f"Artifact ID: {start_artifact.id}")
    print(f"State: {start_artifact.state}")
    print()

    # Step 1: Passage
    passaged_artifacts, rec_passage = passage_op(
        start_artifact,
        target_vessel="plate_6well_02",
        split_ratio=4.0,
        dissociation_method="trypsin",
    )
    passaged_artifact = passaged_artifacts[0]

    print("--- AFTER PASSAGE ---")
    print(f"Artifact ID: {passaged_artifact.id}")
    print(f"State: {passaged_artifact.state}")
    print(f"Lineage: {passaged_artifact.lineage}")
    print()

    # Step 2: Feed
    fed_artifacts, rec_feed = feed_op(
        passaged_artifact,
        media="DMEM+10%FBS+PenStrep",
    )
    fed_artifact = fed_artifacts[0]

    print("--- AFTER FEED ---")
    print(f"Artifact ID: {fed_artifact.id}")
    print(f"State: {fed_artifact.state}")
    print(f"Lineage: {fed_artifact.lineage}")
    print()

    print("--- EXECUTION RECORDS ---")
    print(rec_passage)
    print(rec_feed)
