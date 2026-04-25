import httpx
from models import MCPConnection


async def discover_tools(connection: MCPConnection) -> list[dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        headers = _auth_headers(connection.token)
        resp = await client.get(f"{connection.server_url.rstrip('/')}/tools", headers=headers)
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict) and "tools" in payload:
            return payload["tools"]
        if isinstance(payload, list):
            return payload
    return []


async def execute_tool(connection: MCPConnection, tool_name: str, arguments: dict) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        headers = _auth_headers(connection.token)
        resp = await client.post(
            f"{connection.server_url.rstrip('/')}/invoke",
            json={"tool_name": tool_name, "arguments": arguments},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()


def _auth_headers(token: str) -> dict:
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}
