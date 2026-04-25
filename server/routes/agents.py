from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import AgentWorkflow, Workspace, User
from schemas import AgentRunRequest, AgentWorkflowCreate
from services_agents import run_workflow

router = APIRouter(prefix="/workspaces/{workspace_id}/agents")


@router.get("/workflows")
def list_workflows(
    workspace_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _assert_workspace(db, workspace_id, user.id)
    rows = db.query(AgentWorkflow).filter(AgentWorkflow.workspace_id == workspace_id).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "steps": row.steps_json or [],
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/workflows")
def create_workflow(
    workspace_id: int,
    payload: AgentWorkflowCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_workspace(db, workspace_id, user.id)
    workflow = AgentWorkflow(
        workspace_id=workspace_id,
        name=payload.name,
        description=payload.description,
        steps_json=payload.steps,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    return {"id": workflow.id, "name": workflow.name, "steps": workflow.steps_json}


@router.post("/workflows/{workflow_id}/run")
def run_agent_workflow(
    workspace_id: int,
    workflow_id: int,
    payload: AgentRunRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_workspace(db, workspace_id, user.id)
    workflow = (
        db.query(AgentWorkflow)
        .filter(AgentWorkflow.id == workflow_id, AgentWorkflow.workspace_id == workspace_id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    result = run_workflow(workflow, payload.prompt, payload.context)
    return {"workflow_id": workflow.id, **result}


def _assert_workspace(db: Session, workspace_id: int, user_id: int) -> None:
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.owner_id == user_id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
