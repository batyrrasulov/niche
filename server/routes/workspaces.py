from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Workspace, User
from schemas import WorkspaceCreate, WorkspaceOut

router = APIRouter(prefix="/workspaces")


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Workspace)
        .filter(Workspace.owner_id == user.id)
        .order_by(Workspace.updated_at.desc())
        .all()
    )


@router.post("", response_model=WorkspaceOut)
def create_workspace(
    payload: WorkspaceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    workspace = Workspace(owner_id=user.id, name=payload.name, description=payload.description)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(
    workspace_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.owner_id == user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace
