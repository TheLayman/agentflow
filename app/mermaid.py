from __future__ import annotations

from .models import Workflow


def to_mermaid(wf: Workflow, direction: str = "TD", detailed: bool = True) -> str:
    # Build edges from depends_on if edges not provided
    edges = set()
    for t in wf.tasks:
        for d in t.depends_on:
            edges.add((d, t.id))

    # Header
    out = [f"graph {direction}"]
    
    # Nodes with optional detailed information
    for t in wf.tasks:
        # Use title if available, fallback to name for backward compatibility
        title = (t.title or t.name or t.id).replace("\"", "'")
        
        if detailed:
            # Build detailed label with task information
            label_parts = [f"<b>{title}</b>"]
            
            # Add actor information
            actor_icon = "🤖" if t.actor == "agent" else "👤"
            label_parts.append(f"{actor_icon} {t.actor}")
            
            # Add tool if available
            if t.tool:
                label_parts.append(f"🔧 {t.tool}")
            
            # Add inputs if available
            if t.inputs:
                # Show inputs in a more readable format
                inputs_display = []
                for inp in t.inputs[:3]:  # Show up to 3 inputs
                    # Clean up input names for better readability
                    clean_inp = inp.replace('_', ' ').replace('.json', '').title()
                    inputs_display.append(clean_inp)
                
                inputs_str = ", ".join(inputs_display)
                if len(t.inputs) > 3:
                    inputs_str += f" (+{len(t.inputs)-3} more)"
                label_parts.append(f"📥 {inputs_str}")
            
            # Add outputs if available  
            if t.outputs:
                # Show outputs in a more readable format
                outputs_display = []
                for output in t.outputs[:3]:  # Show up to 3 outputs
                    # Clean up output names for better readability
                    clean_output = output.replace('_', ' ').replace('.json', '').title()
                    outputs_display.append(clean_output)
                
                outputs_str = ", ".join(outputs_display)
                if len(t.outputs) > 3:
                    outputs_str += f" (+{len(t.outputs)-3} more)"
                label_parts.append(f"📤 {outputs_str}")
            
            # Add approval status if not 'none'
            if t.approval and t.approval != "none":
                approval_icon = "✋" if t.approval == "human" else "⚡"
                label_parts.append(f"{approval_icon} {t.approval}")
            
            # Join all parts with line breaks
            full_label = "<br/>".join(label_parts)
        else:
            # Simple label with just title and actor icon
            actor_icon = "🤖" if t.actor == "agent" else "👤"
            full_label = f"{actor_icon} {title}"
        
        # Choose node shape based on actor type
        if t.actor == "human":
            # Use hexagon for human tasks
            out.append(f"  {t.id}{{{{{full_label}}}}}")
        else:
            # Use rectangle for agent tasks
            out.append(f"  {t.id}[\"{full_label}\"]")
    
    # Add styling for different actors
    out.append("")
    out.append("  %% Styling")
    out.append("  classDef humanTask fill:#ffe6e6,stroke:#ff6b6b,stroke-width:2px")
    out.append("  classDef agentTask fill:#e6f3ff,stroke:#4a90e2,stroke-width:2px")
    
    # Apply classes to nodes
    human_tasks = [t.id for t in wf.tasks if t.actor == "human"]
    agent_tasks = [t.id for t in wf.tasks if t.actor == "agent"]
    
    if human_tasks:
        out.append(f"  class {','.join(human_tasks)} humanTask")
    if agent_tasks:
        out.append(f"  class {','.join(agent_tasks)} agentTask")
    
    # Edges
    out.append("")
    out.append("  %% Dependencies")
    for a, b in sorted(edges):
        out.append(f"  {a} --> {b}")
    
    return "\n".join(out)

