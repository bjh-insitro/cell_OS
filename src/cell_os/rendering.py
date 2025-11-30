"""
Workflow Rendering Module.

Consolidates visualization logic for Workflows using Graphviz and Plotly.
"""

from typing import List, Any, Union, Optional, Dict
import graphviz
import plotly.graph_objects as go
import networkx as nx
from abc import ABC, abstractmethod

from cell_os.workflows import Workflow, Process

# Shared Color Scheme
COLOR_SCHEME = {
    'construction': '#f3e5f5',  # Purple
    'library': '#f3e5f5',       # Purple
    'cloning': '#f3e5f5',       # Purple
    'molecular': '#f3e5f5',     # Purple
    
    'preparation': '#fff3e0',   # Orange
    'cell': '#fff3e0',          # Orange
    'culture': '#fff3e0',       # Orange
    
    'screening': '#fce4ec',     # Pink
    'phenotyp': '#fce4ec',      # Pink
    'perturbation': '#fce4ec',  # Pink
    'transduce': '#fce4ec',     # Pink
    
    'analysis': '#e8f5e9',      # Green
    'data': '#e8f5e9',          # Green
    'compute': '#e8f5e9',       # Green
    'sequencing': '#e8f5e9',    # Green
    
    'banking': '#e3f2fd',       # Blue
    'freeze': '#e3f2fd',        # Blue
    'storage': '#e3f2fd',       # Blue
    'default': '#e3f2fd'        # Blue
}

def get_color_for_name(name: str) -> str:
    """Determine color based on keyword matching."""
    name_lower = name.lower()
    for key, color in COLOR_SCHEME.items():
        if key in name_lower:
            return color
    return COLOR_SCHEME['default']


class WorkflowRenderer(ABC):
    """Abstract base class for workflow renderers."""
    
    @abstractmethod
    def render(self, workflow: Workflow, detail_level: str = "process") -> Any:
        """Render the workflow."""
        pass


class GraphvizRenderer(WorkflowRenderer):
    """Renders workflow as a static Graphviz Digraph."""
    
    def render(self, workflow_or_recipe: Union[Workflow, List[Any]], title: str = "Workflow Graph", detail_level: str = "process") -> graphviz.Digraph:
        dot = graphviz.Digraph(comment=title)
        dot.attr(rankdir='TB')
        dot.attr('node', shape='box', style='filled', fillcolor='white', fontname='Helvetica')
        
        if isinstance(workflow_or_recipe, Workflow):
            workflow = workflow_or_recipe
            
            if detail_level == "process":
                self._render_process_level(dot, workflow)
            else:
                self._render_unitop_level(dot, workflow)
        else:
            # Legacy list support
            self._render_legacy_list(dot, workflow_or_recipe)
            
        return dot

    def _render_process_level(self, dot: graphviz.Digraph, workflow: Workflow):
        previous_node_id = None
        for p_idx, process in enumerate(workflow.processes):
            node_id = f"process_{p_idx}"
            label = process.name
            fillcolor = get_color_for_name(process.name)
            
            dot.node(node_id, label=label, fillcolor=fillcolor, fontsize='12')
            
            if previous_node_id:
                dot.edge(previous_node_id, node_id)
            previous_node_id = node_id

    def _render_unitop_level(self, dot: graphviz.Digraph, workflow: Workflow):
        previous_node_id = None
        for p_idx, process in enumerate(workflow.processes):
            with dot.subgraph(name=f"cluster_{p_idx}") as c:
                c.attr(label=process.name)
                c.attr(style='dashed')
                c.attr(color='grey')
                
                for i, op in enumerate(process.ops):
                    node_id = f"p{p_idx}_op{i}"
                    self._add_node(c, node_id, op)
                    
                    if i > 0:
                        prev_in_proc = f"p{p_idx}_op{i-1}"
                        c.edge(prev_in_proc, node_id)
                        
                first_in_proc = f"p{p_idx}_op0"
                if previous_node_id:
                    dot.edge(previous_node_id, first_in_proc)
                
                previous_node_id = f"p{p_idx}_op{len(process.ops)-1}"

    def _render_legacy_list(self, dot: graphviz.Digraph, recipe: List[Any]):
        previous_node_id = None
        for i, op in enumerate(recipe):
            node_id = f"op_{i}"
            self._add_node(dot, node_id, op)
            if previous_node_id:
                dot.edge(previous_node_id, node_id)
            previous_node_id = node_id

    def _add_node(self, graph, node_id, op):
        op_name = getattr(op, 'name', None) or getattr(op, 'uo_id', 'Unknown Op')
        op_type = getattr(op, 'category', 'unknown')
        
        label_parts = [op_name]
        if op_type and op_type.lower() not in op_name.lower():
            label_parts.append(f"[{op_type}]")
        
        if hasattr(op, 'sub_steps') and op.sub_steps:
            label_parts.append(f"({len(op.sub_steps)} steps)")
        
        label = "\\n".join(label_parts)
        fillcolor = get_color_for_name(op_type if op_type else op_name)
            
        graph.node(node_id, label=label, fillcolor=fillcolor, fontsize='10')


class PlotlyRenderer(WorkflowRenderer):
    """Renders workflow as an interactive Plotly figure."""
    
    def render(self, workflow: Workflow, detail_level: str = "process") -> Optional[go.Figure]:
        if detail_level != "process":
            return None # Not implemented yet
            
        G = nx.DiGraph()
        node_info = []
        
        for p_idx, process in enumerate(workflow.processes):
            node_id = f"process_{p_idx}"
            total_ops = len(process.ops)
            total_cost = sum(op.material_cost_usd + op.instrument_cost_usd for op in process.ops)
            
            G.add_node(node_id)
            node_info.append({
                'id': node_id,
                'name': process.name,
                'ops_count': total_ops,
                'cost': total_cost,
                'ops': process.ops
            })
            
            if p_idx > 0:
                G.add_edge(f"process_{p_idx-1}", node_id)
        
        # Layout
        pos = nx.spring_layout(G, k=2, iterations=50)
        for i, node_id in enumerate(G.nodes()):
            pos[node_id] = (0, -i * 2)
            
        # Edges
        edge_x, edge_y = [], []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=2, color='#888'),
            hoverinfo='none',
            mode='lines',
            showlegend=False
        )
        
        # Nodes
        node_x, node_y, node_text, node_customdata, shapes = [], [], [], [], []
        rect_width, rect_height = 3.5, 1.2
        
        for info in node_info:
            x, y = pos[info['id']]
            node_x.append(x)
            node_y.append(y)
            node_text.append(info['name'])
            
            color = get_color_for_name(info['name'])
            
            ops_list = "<br>".join([f"• {op.name}" for op in info['ops']])
            node_customdata.append(f"<b>{info['name']}</b><br>{info['ops_count']} operations<br>${info['cost']:.0f}<br><br><b>Operations:</b><br>{ops_list}")
            
            shapes.append(dict(
                type="rect",
                x0=x - rect_width/2, y0=y - rect_height/2,
                x1=x + rect_width/2, y1=y + rect_height/2,
                fillcolor=color,
                line=dict(color='#888', width=2),
                layer='below'
            ))
            
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='text',
            text=node_text,
            textposition="middle center",
            textfont=dict(size=12, color='black'),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=node_customdata,
            showlegend=False
        )
        
        return go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                title=dict(text=f"{workflow.name}", font=dict(size=20)),
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                plot_bgcolor='white',
                height=600,
                shapes=shapes
            )
        )

# Convenience functions to maintain API compatibility if needed, 
# or we can update callers to use classes directly.
def render_workflow_graph(workflow, title="Workflow Graph", detail_level="process"):
    return GraphvizRenderer().render(workflow, title, detail_level)

def render_workflow_plotly(workflow, detail_level="process"):
    return PlotlyRenderer().render(workflow, detail_level)
