import plotly.graph_objects as go
import networkx as nx
from typing import List, Any, Union
from cell_os.workflows import Workflow, Process

def render_workflow_plotly(workflow: Workflow, detail_level: str = "process"):
    """
    Generates an interactive Plotly graph for a Workflow.
    
    Args:
        workflow: Workflow object
        detail_level: "process" (high-level) or "unitop" (detailed)
    
    Returns:
        Plotly Figure object
    """
    G = nx.DiGraph()
    
    if detail_level == "process":
        # High-level view: Just show processes as nodes
        node_info = []
        
        for p_idx, process in enumerate(workflow.processes):
            node_id = f"process_{p_idx}"
            
            # Calculate stats
            total_ops = len(process.ops)
            total_cost = sum(op.material_cost_usd + op.instrument_cost_usd for op in process.ops)
            
            # Add node to graph
            G.add_node(node_id)
            
            # Store metadata
            node_info.append({
                'id': node_id,
                'name': process.name,
                'ops_count': total_ops,
                'cost': total_cost,
                'ops': process.ops
            })
            
            # Add edge to next process
            if p_idx > 0:
                G.add_edge(f"process_{p_idx-1}", node_id)
        
        # Layout using hierarchical positioning
        pos = nx.spring_layout(G, k=2, iterations=50)
        
        # Manually position nodes in a vertical line for better workflow visualization
        for i, node_id in enumerate(G.nodes()):
            pos[node_id] = (0, -i * 2)  # Vertical layout
        
        # Create edge traces
        edge_x = []
        edge_y = []
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
        
        # Create node traces (just for text and hover, no visible markers)
        node_x = []
        node_y = []
        node_text = []
        node_customdata = []
        shapes = []  # For drawing rectangles
        
        rect_width = 3.5  # Width of rectangle
        rect_height = 1.2  # Height of rectangle
        
        for info in node_info:
            x, y = pos[info['id']]
            node_x.append(x)
            node_y.append(y)
            node_text.append(info['name'])
            
            # Color based on process type
            if 'construction' in info['name'].lower() or 'library' in info['name'].lower():
                color = '#f3e5f5'  # Purple
            elif 'preparation' in info['name'].lower() or 'cell' in info['name'].lower():
                color = '#fff3e0'  # Orange
            elif 'screening' in info['name'].lower() or 'phenotyp' in info['name'].lower():
                color = '#fce4ec'  # Pink
            elif 'analysis' in info['name'].lower() or 'data' in info['name'].lower():
                color = '#e8f5e9'  # Green
            else:
                color = '#e3f2fd'  # Blue
            
            # Store ops list for hover
            ops_list = "<br>".join([f"• {op.name}" for op in info['ops']])
            node_customdata.append(f"<b>{info['name']}</b><br>{info['ops_count']} operations<br>${info['cost']:.0f}<br><br><b>Operations:</b><br>{ops_list}")
            
            # Add rectangle shape
            shapes.append(dict(
                type="rect",
                x0=x - rect_width/2,
                y0=y - rect_height/2,
                x1=x + rect_width/2,
                y1=y + rect_height/2,
                fillcolor=color,
                line=dict(color='#888', width=2),
                layer='below'
            ))
        
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='text',  # Only text, no markers
            text=node_text,
            textposition="middle center",
            textfont=dict(size=12, color='black'),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=node_customdata,
            showlegend=False
        )
        
        # Create figure with shapes
        fig = go.Figure(data=[edge_trace, node_trace],
                       layout=go.Layout(
                           title=dict(text=f"{workflow.name}", font=dict(size=20)),
                           showlegend=False,
                           hovermode='closest',
                           margin=dict(b=20, l=5, r=5, t=40),
                           xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                           yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                           plot_bgcolor='white',
                           height=600,
                           shapes=shapes  # Add rectangle shapes
                       ))
        
        return fig
    
    else:  # detail_level == "unitop"
        # Detailed view: Show all UnitOps
        # This would be more complex - for now, return a message
        # Could implement later if needed
        return None
