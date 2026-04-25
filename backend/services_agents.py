from models import AgentWorkflow


def run_workflow(workflow: AgentWorkflow, prompt: str, context: dict) -> dict:
    events = []
    output = prompt
    for index, step in enumerate(workflow.steps_json or []):
        step_name = step.get("name", f"step-{index+1}")
        mode = step.get("mode", "transform")
        if mode == "append-context":
            output = f"{output}\n\nContext:\n{context}"
        elif mode == "tool":
            output = f"{output}\n\n[Tool:{step.get('tool', 'unknown')} invoked]"
        else:
            output = f"{output}\n\n[{step_name} complete]"
        events.append({"type": "workflow_step", "step": step_name, "mode": mode})
    return {"result": output, "events": events}
