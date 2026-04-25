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
    return db.query(Thread).filter(Thread.workspace_id == workspace_id).order_by(Thread.created_at.desc()).all()


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
                    "status": "completed",
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
    top_grounded = grounded[:2]
    highlight_lines = (
        "\n".join([f"- {item['title']}: {item['excerpt'][:140]}..." for item in top_grounded])
        if top_grounded
        else "- No strongly matching internal sources were found for this prompt."
    )

    risk_lines = []
    if not top_grounded:
        risk_lines.append("- Internal grounding confidence is low for this specific request.")
    if not web_results:
        risk_lines.append("- No strong external web corroboration was retrieved in this run.")
    if not mcp_snapshot:
        risk_lines.append("- MCP output is limited, so operational data may be incomplete.")
    if not risk_lines:
        risk_lines.append("- No critical blockers detected from the current context.")

    action_lines = [
        "- Validate top assumptions against the highest-scoring source excerpts.",
        "- Convert the top risk into one measurable owner and deadline.",
        "- Run one follow-up query to narrow uncertainty before execution.",
    ]
    if web_results:
        action_lines.append("- Cross-check with one external reference before final sign-off.")
    if mcp_snapshot:
        action_lines.append("- Use MCP output to confirm runtime/tooling readiness before launch.")

    answer = (
        "Here is a concise readiness summary:\n\n"
        "Highlights\n"
        f"{highlight_lines}\n\n"
        "Key risks\n"
        f"{chr(10).join(risk_lines)}\n\n"
        "Recommended next actions\n"
        f"{chr(10).join(action_lines[:4])}"
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
