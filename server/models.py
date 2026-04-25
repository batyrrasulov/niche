from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    oauth_provider: Mapped[str] = mapped_column(String(50), default="local")
    oauth_subject: Mapped[str] = mapped_column(String(255), default="")


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")

    threads = relationship("Thread", back_populates="workspace")
    sources = relationship("SourceDocument", back_populates="workspace")


class Thread(Base, TimestampMixin):
    __tablename__ = "threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="New thread")

    workspace = relationship("Workspace", back_populates="threads")
    messages = relationship("Message", back_populates="thread")


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("threads.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[dict] = mapped_column(JSON, default=list)
    tool_events: Mapped[dict] = mapped_column(JSON, default=list)

    thread = relationship("Thread", back_populates="messages")


class SourceDocument(Base, TimestampMixin):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    workspace = relationship("Workspace", back_populates="sources")


class MCPConnection(Base, TimestampMixin):
    __tablename__ = "mcp_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    server_url: Mapped[str] = mapped_column(String(1024))
    token: Mapped[str] = mapped_column(String(1024), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    tools_json: Mapped[dict] = mapped_column(JSON, default=list)


class AgentWorkflow(Base, TimestampMixin):
    __tablename__ = "agent_workflows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    steps_json: Mapped[dict] = mapped_column(JSON, default=list)


class SkillTemplate(Base, TimestampMixin):
    __tablename__ = "skill_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    manifest_json: Mapped[dict] = mapped_column(JSON, default=dict)
