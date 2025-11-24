from typing import List, Any, Union
import graphviz
from src.workflows import Workflow, Process

def render_workflow_graph(workflow_or_recipe: Union[Workflow, List[Any]], title: str = "Workflow Graph", detail_level: str = "process") -> graphviz.Digraph:
    """
    Generates a Graphviz Digraph for a Workflow or a simple recipe list.
    
    Args:
        workflow_or_recipe: Workflow object or list of UnitOps
        title: Graph title
        detail_level: "process" (high-level) or "unitop" (detailed)
    """
    dot = graphviz.Digraph(comment=title)
    dot.attr(rankdir='TB')
    dot.attr('node', shape='box', style='filled', fillcolor='white', fontname='Helvetica')
    
    # Check if input is a full Workflow object
    if isinstance(workflow_or_recipe, Workflow):
        workflow = workflow_or_recipe
        
        if detail_level == "process":
            # High-level view: Just show processes as nodes
            previous_node_id = None
            for p_idx, process in enumerate(workflow.processes):
                node_id = f"process_{p_idx}"
                
                # Simple label - just the process name
                label = process.name
                
                # Color based on process type
                fillcolor = '#e3f2fd'  # Default blue
                if 'construction' in process.name.lower() or 'library' in process.name.lower():
                    fillcolor = '#f3e5f5'  # Purple
                elif 'preparation' in process.name.lower() or 'cell' in process.name.lower():
                    fillcolor = '#fff3e0'  # Orange
                elif 'screening' in process.name.lower() or 'phenotyp' in process.name.lower():
                    fillcolor = '#fce4ec'  # Pink
                elif 'analysis' in process.name.lower() or 'data' in process.name.lower():
                    fillcolor = '#e8f5e9'  # Green
                
                dot.node(node_id, label=label, fillcolor=fillcolor, fontsize='12')
                
                if previous_node_id:
                    dot.edge(previous_node_id, node_id)
                previous_node_id = node_id
                
        else:  # detail_level == "unitop"
            # Detailed view: Show all UnitOps in subgraphs
            previous_node_id = None
            
            for p_idx, process in enumerate(workflow.processes):
                # Create a subgraph for the process
                with dot.subgraph(name=f"cluster_{p_idx}") as c:
                    c.attr(label=process.name)
                    c.attr(style='dashed')
                    c.attr(color='grey')
                    
                    for i, op in enumerate(process.ops):
                        node_id = f"p{p_idx}_op{i}"
                        _add_node(c, node_id, op)
                        
                        # Connect within process
                        if i > 0:
                            prev_in_proc = f"p{p_idx}_op{i-1}"
                            c.edge(prev_in_proc, node_id)
                            
                    # Connect processes
                    first_in_proc = f"p{p_idx}_op0"
                    if previous_node_id:
                        dot.edge(previous_node_id, first_in_proc)
                    
                    # Update previous node to be the last of this process
                    previous_node_id = f"p{p_idx}_op{len(process.ops)-1}"
                
    else:
        # Legacy list support
        recipe = workflow_or_recipe
        previous_node_id = None
        for i, op in enumerate(recipe):
            node_id = f"op_{i}"
            _add_node(dot, node_id, op)
            if previous_node_id:
                dot.edge(previous_node_id, node_id)
            previous_node_id = node_id
            
    return dot

def _add_node(graph, node_id, op):
    """Helper to add a styled node to a graph/subgraph."""
    # Get name and type with robust fallbacks
    op_name = getattr(op, 'name', None) or getattr(op, 'uo_id', 'Unknown Op')
    op_type = getattr(op, 'category', 'unknown')
    
    # Build a simple text label (not HTML) for better compatibility
    label_parts = [op_name]
    
    # Add type if different from name
    if op_type and op_type.lower() not in op_name.lower():
        label_parts.append(f"[{op_type}]")
    
    # Add sub-steps count if present
    if hasattr(op, 'sub_steps') and op.sub_steps:
        label_parts.append(f"({len(op.sub_steps)} steps)")
    
    # Join with newlines
    label = "\\n".join(label_parts)
    
    # Color coding based on category
    fillcolor = 'white'
    op_type_lower = op_type.lower() if op_type else ''
    
    if 'culture' in op_type_lower or 'cell_prep' in op_type_lower:
        fillcolor = '#fff3e0'  # Orange
    elif 'perturbation' in op_type_lower or 'transduce' in op_type_lower:
        fillcolor = '#fce4ec'  # Pink
    elif 'analysis' in op_type_lower or 'compute' in op_type_lower or 'sequencing' in op_type_lower:
        fillcolor = '#e8f5e9'  # Green
    elif 'banking' in op_type_lower or 'freeze' in op_type_lower or 'storage' in op_type_lower:
        fillcolor = '#e3f2fd'  # Blue
    elif 'cloning' in op_type_lower or 'molecular_biology' in op_type_lower:
        fillcolor = '#f3e5f5'  # Purple
        
    graph.node(node_id, label=label, fillcolor=fillcolor, fontsize='10')
