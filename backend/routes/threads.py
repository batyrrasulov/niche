import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import MCPConnection, Message, SourceDocument, Thread, Workspace, User
from schemas import ChatRequest, ThreadCreate, ThreadOut
from services_mcp import discover_tools, execute_tool
from services_retrieval import retrieve_top_sources
from services_web import search_web

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
async def chat_stream(
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
    tool_events: list[dict] = [
        {
            "type": "retrieval",
            "status": "completed",
            "metadata": {"candidate_sources": len(docs), "grounded_sources": len(citations)},
        }
    ]

    web_results: list[dict] = []
    if payload.use_web:
        try:
            web_results = await search_web(payload.content, limit=3)
            tool_events.append(
                {
                    "type": "web_search",
                    "status": "completed" if web_results else "no_results",
                    "metadata": {"results": len(web_results)},
                }
            )
        except Exception as exc:
            tool_events.append({"type": "web_search", "status": "failed", "error": str(exc)})
    else:
        tool_events.append({"type": "web_search", "status": "skipped"})

    mcp_snapshot: dict = {}
    if payload.use_mcp:
        connection = (
            db.query(MCPConnection)
            .filter(MCPConnection.workspace_id == workspace_id, MCPConnection.enabled.is_(True))
            .order_by(MCPConnection.created_at.asc())
            .first()
        )
        if not connection:
            tool_events.append({"type": "mcp_action", "status": "skipped", "metadata": {"reason": "no_connection"}})
        else:
            try:
                tools = connection.tools_json or []
                if not tools:
                    tools = await discover_tools(connection)
                    connection.tools_json = tools
                    db.commit()
                if not tools:
                    tool_events.append(
                        {"type": "mcp_action", "status": "skipped", "metadata": {"reason": "no_tools_discovered"}}
                    )
                else:
                    tool_name = tools[0].get("name") or tools[0].get("tool_name") or "unknown_tool"
                    mcp_snapshot = await execute_tool(connection, tool_name, {})
                    tool_events.append(
                        {
                            "type": "mcp_action",
                            "status": "completed",
                            "metadata": {"connection": connection.name, "tool_name": tool_name},
                        }
                    )
            except Exception as exc:
                tool_events.append({"type": "mcp_action", "status": "failed", "error": str(exc)})
    else:
        tool_events.append({"type": "mcp_action", "status": "skipped"})

    grounded = [c for c in citations if c["score"] > 0]
    grounded_lines = (
        "\n".join([f"- {c['title']} (score={c['score']})" for c in grounded]) if grounded else "- No direct matches."
    )
    web_lines = (
        "\n".join([f"- {item.get('title', 'result')} ({item.get('url', 'no-url')})" for item in web_results])
        if web_results
        else "- No web context."
    )
    mcp_line = f"- MCP result keys: {', '.join(sorted(mcp_snapshot.keys()))}" if mcp_snapshot else "- No MCP output."
    answer = (
        "Niche answer based on orchestrated stages.\n\n"
        f"Question: {payload.content}\n\n"
        "Grounded sources:\n"
        f"{grounded_lines}\n\n"
        "Web context:\n"
        f"{web_lines}\n\n"
        "MCP context:\n"
        f"{mcp_line}\n"
    )
    tool_events.append({"type": "synthesis", "status": "completed"})

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
