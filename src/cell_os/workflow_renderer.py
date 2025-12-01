"""
Lightweight workflow rendering utilities.

Provides a stable import target for smoke tests and CLI helpers that want to
visualize workflows without depending on the older Streamlit dashboard code.
"""
from __future__ import annotations

from typing import Iterable, Optional

try:
    from graphviz import Digraph
except ImportError:  # pragma: no cover
    Digraph = None  # type: ignore


def render_workflow_graph(workflow, filename: Optional[str] = None):
    """
    Render a Workflow object to a Graphviz Digraph.

    Parameters
    ----------
    workflow : cell_os.workflows.Workflow
        Workflow instance with `.processes` and `.ops`.
    filename : str, optional
        If provided, renders the graph to the given base filename (Graphviz
        chooses the extension, defaulting to .gv/.pdf/png depending on config).

    Returns
    -------
    Digraph or list[str]
        Returns the Digraph when graphviz is available, otherwise a list of
        human-readable lines representing the structure.
    """
    if Digraph is None:
        return _render_textual(workflow)

    graph = Digraph(comment=workflow.name)
    graph.attr(rankdir="LR")

    for proc_idx, process in enumerate(workflow.processes):
        proc_id = f"proc_{proc_idx}"
        graph.node(proc_id, process.name, shape="box", style="filled", fillcolor="#e8f5ff")

        for op_idx, op in enumerate(process.ops):
            op_id = f"{proc_id}_{op_idx}"
            op_label = getattr(op, "name", f"Op {op_idx}")
            graph.node(op_id, op_label, shape="ellipse")
            graph.edge(proc_id, op_id)

    if filename:
        graph.render(filename, cleanup=True)
    return graph


def _render_textual(workflow) -> Iterable[str]:
    """Fallback textual representation when graphviz isn't installed."""
    lines = [f"Workflow: {workflow.name}"]
    for proc_idx, process in enumerate(workflow.processes):
        lines.append(f"  [{proc_idx}] {process.name} ({len(process.ops)} ops)")
        for op_idx, op in enumerate(process.ops):
            op_name = getattr(op, "name", f"Op {op_idx}")
            lines.append(f"    - {op_name}")
    return lines

