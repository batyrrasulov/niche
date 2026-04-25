from fastapi import APIRouter

from routes import auth, workspaces, threads, sources, mcp, agents, skills, health


def api_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    router.include_router(auth.router, tags=["auth"])
    router.include_router(workspaces.router, tags=["workspaces"])
    router.include_router(threads.router, tags=["threads"])
    router.include_router(sources.router, tags=["sources"])
    router.include_router(mcp.router, tags=["mcp"])
    router.include_router(agents.router, tags=["agents"])
    router.include_router(skills.router, tags=["skills"])
    return router


health_router = health.router
