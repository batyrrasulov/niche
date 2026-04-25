import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Message, SourceDocument, Thread, Workspace, User
from schemas import ChatRequest, ThreadCreate, ThreadOut
from services_retrieval import retrieve_top_sources

router = APIRouter(prefix="/workspaces/{workspace_id}/threads")


@router.get("", response_model=list[ThreadOut])
def list_threads(workspace_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.owner_id == user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return db.query(Thread).filter(Thread.workspace_id == workspace_id).order_by(Thread.updated_at.desc()).all()


@router.post("", response_model=ThreadOut)
def create_thread(
    workspace_id: int,
    payload: ThreadCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.owner_id == user.id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    thread = Thread(workspace_id=workspace_id, title=payload.title)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@router.get("/{thread_id}/messages")
def list_messages(
    workspace_id: int, thread_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _assert_thread_access(db, user.id, workspace_id, thread_id)
    rows = db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.created_at.asc()).all()
    return [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "citations": row.citations or [],
            "tool_events": row.tool_events or [],
        }
        for row in rows
    ]


@router.post("/{thread_id}/messages")
def chat_stream(
    workspace_id: int,
    thread_id: int,
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_thread_access(db, user.id, workspace_id, thread_id)

    user_message = Message(thread_id=thread_id, role="user", content=payload.content, citations=[], tool_events=[])
    db.add(user_message)
    db.commit()

    docs = db.query(SourceDocument).filter(SourceDocument.workspace_id == workspace_id).all()
    citations = retrieve_top_sources(payload.content, docs, limit=4)
    answer = (
        "NicheGPT answer based on your workspace data.\n\n"
        f"Question: {payload.content}\n\n"
        "Top grounded sources:\n"
        + "\n".join([f"- {c['title']} (score={c['score']})" for c in citations if c["score"] > 0])
    )
    tool_events = []
    if payload.use_web:
        tool_events.append({"type": "web_search", "status": "completed"})
    if payload.use_mcp:
        tool_events.append({"type": "mcp_capability_scan", "status": "completed"})

    assistant = Message(
        thread_id=thread_id,
        role="assistant",
        content=answer,
        citations=citations,
        tool_events=tool_events,
    )
    db.add(assistant)
    db.commit()
    db.refresh(assistant)

    def event_stream():
        for event in tool_events:
            yield _sse("tool_event", event)
        for token in answer.split():
            yield _sse("token", {"token": token + " "})
        yield _sse(
            "final",
            {
                "message_id": assistant.id,
                "content": answer,
                "citations": citations,
                "tool_events": tool_events,
            },
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _assert_thread_access(db: Session, user_id: int, workspace_id: int, thread_id: int) -> None:
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.owner_id == user_id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.workspace_id == workspace_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"
