from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import MCPConnection, Workspace, User
from schemas import MCPActionRequest, MCPConnectionCreate, MCPConnectionOut
from services_mcp import discover_tools, execute_tool

router = APIRouter(prefix="/workspaces/{workspace_id}/mcp")


@router.get("/connections", response_model=list[MCPConnectionOut])
def list_connections(
    workspace_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _assert_workspace(db, workspace_id, user.id)
    return db.query(MCPConnection).filter(MCPConnection.workspace_id == workspace_id).all()


@router.post("/connections", response_model=MCPConnectionOut)
async def create_connection(
    workspace_id: int,
    payload: MCPConnectionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_workspace(db, workspace_id, user.id)
    connection = MCPConnection(
        workspace_id=workspace_id,
        name=payload.name,
        server_url=payload.server_url,
        token=payload.token,
        tools_json=[],
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


@router.post("/connections/{connection_id}/discover", response_model=MCPConnectionOut)
async def discover_connection_tools(
    workspace_id: int,
    connection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_workspace(db, workspace_id, user.id)
    connection = (
        db.query(MCPConnection)
        .filter(MCPConnection.id == connection_id, MCPConnection.workspace_id == workspace_id)
        .first()
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    connection.tools_json = await discover_tools(connection)
    db.commit()
    db.refresh(connection)
    return connection


@router.post("/connections/{connection_id}/invoke")
async def invoke_connection_tool(
    workspace_id: int,
    connection_id: int,
    payload: MCPActionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _assert_workspace(db, workspace_id, user.id)
    connection = (
        db.query(MCPConnection)
        .filter(MCPConnection.id == connection_id, MCPConnection.workspace_id == workspace_id)
        .first()
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    if payload.require_confirmation:
        return {"status": "confirmation_required", "tool_name": payload.tool_name}
    result = await execute_tool(connection, payload.tool_name, payload.arguments)
    return {"status": "completed", "result": result}


def _assert_workspace(db: Session, workspace_id: int, user_id: int) -> None:
    workspace = (
        db.query(Workspace)
        .filter(Workspace.id == workspace_id, Workspace.owner_id == user_id)
        .first()
    )
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
