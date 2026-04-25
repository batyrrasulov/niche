from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import SourceDocument, Workspace, User
from schemas import SourceCreate, SourceOut
from services_ingestion import fetch_url_text

router = APIRouter(prefix="/workspaces/{workspace_id}/sources")


@router.get("", response_model=list[SourceOut])
def list_sources(workspace_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _assert_workspace(db, user.id, workspace_id)
    return (
        db.query(SourceDocument)
        .filter(SourceDocument.workspace_id == workspace_id)
        .order_by(SourceDocument.created_at.desc())
        .all()
    )


@router.post("", response_model=SourceOut)
async def add_source(
    workspace_id: int,
    payload: SourceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_workspace(db, user.id, workspace_id)
    body = payload.body
    metadata = {}
    if payload.source_type == "url" and payload.url:
        body = await fetch_url_text(payload.url)
        metadata["url"] = payload.url
    source = SourceDocument(
        workspace_id=workspace_id,
        source_type=payload.source_type,
        title=payload.title,
        body=body,
        metadata_json=metadata,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.post("/upload", response_model=SourceOut)
async def upload_source(
    workspace_id: int,
    title: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_workspace(db, user.id, workspace_id)
    content = (await file.read()).decode("utf-8", errors="ignore")
    source = SourceDocument(
        workspace_id=workspace_id,
        source_type="file",
        title=title,
        body=content,
        metadata_json={"filename": file.filename},
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def _assert_workspace(db: Session, user_id: int, workspace_id: int) -> None:
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.owner_id == user_id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
