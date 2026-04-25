from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    oauth_provider: str

    class Config:
        from_attributes = True


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = ""


class WorkspaceOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ThreadCreate(BaseModel):
    title: str = "New thread"


class ThreadOut(BaseModel):
    id: int
    workspace_id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    content: str = Field(min_length=1)
    use_web: bool = True
    use_mcp: bool = True


class SourceCreate(BaseModel):
    source_type: str
    title: str
    body: str = ""
    url: str = ""


class SourceOut(BaseModel):
    id: int
    workspace_id: int
    source_type: str
    title: str
    metadata_json: dict
    created_at: datetime

    class Config:
        from_attributes = True


class MCPConnectionCreate(BaseModel):
    name: str
    server_url: str
    token: str = ""


class MCPConnectionOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    server_url: str
    enabled: bool
    tools_json: list

    class Config:
        from_attributes = True


class MCPActionRequest(BaseModel):
    tool_name: str
    arguments: dict = Field(default_factory=dict)
    require_confirmation: bool = False


class AgentWorkflowCreate(BaseModel):
    name: str
    description: str = ""
    steps: list[dict] = Field(default_factory=list)


class AgentRunRequest(BaseModel):
    prompt: str
    context: dict = Field(default_factory=dict)


class SkillInstallRequest(BaseModel):
    slug: str
