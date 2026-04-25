# NicheGPT Naming and API Contract

## Canonical names

- Product name: `NicheGPT`
- Backend service ID: `nichegpt-api`
- Frontend app ID: `nichegpt-web`
- API prefix: `/api/v1`
- Health endpoint: `/health`
- Metrics endpoint: `/metrics`

## Core resources

- `/api/v1/auth/*`
- `/api/v1/workspaces`
- `/api/v1/workspaces/{workspaceId}/threads`
- `/api/v1/workspaces/{workspaceId}/sources`
- `/api/v1/workspaces/{workspaceId}/mcp`
- `/api/v1/workspaces/{workspaceId}/agents`
- `/api/v1/skills/catalog`

## Streaming contract

- Chat stream endpoint:
  - `POST /api/v1/workspaces/{workspaceId}/threads/{threadId}/messages`
- Content type:
  - `text/event-stream`
- Events:
  - `tool_event`: tool lifecycle/status entries
  - `token`: incremental text tokens
  - `final`: final assistant payload with citations and tool events