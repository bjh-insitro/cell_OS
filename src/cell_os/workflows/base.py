from dataclasses import dataclass
from typing import List

from cell_os.unit_ops import UnitOp, AssayRecipe


@dataclass
class Process:
    name: str
    ops: List[UnitOp]


@dataclass
class Workflow:
    name: str
    processes: List[Process]

    @property
    def all_ops(self) -> List[UnitOp]:
        ops: List[UnitOp] = []
        for process in self.processes:
            ops.extend(process.ops)
        return ops


def workflow_from_assay_recipe(recipe: AssayRecipe) -> Workflow:
    """
    Adapt an AssayRecipe (layered ops with counts) into a canonical Workflow.

    - Each recipe layer becomes a Process.
    - Each (UnitOp, count) entry is expanded into `count` UnitOp instances
      in that Process's ops list.
    - Bare UnitOp entries (no count) are preserved as a single op.
    """
    processes: List[Process] = []

    for layer_name, entries in recipe.layers.items():
        ops: List[UnitOp] = []

        for entry in entries:
            if isinstance(entry, tuple) and len(entry) == 2:
                op, count = entry
                try:
                    n = int(count)
                except (TypeError, ValueError):
                    n = 1
                n = max(1, n)
                for _ in range(n):
                    ops.append(op)
            else:
                ops.append(entry)

        processes.append(Process(name=layer_name, ops=ops))

    return Workflow(name=recipe.name, processes=processes)
