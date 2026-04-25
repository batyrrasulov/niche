export type Workspace = { id: number; name: string; description: string };
export type Thread = { id: number; workspace_id: number; title: string };
export type Source = { id: number; title: string; source_type: string; metadata_json: Record<string, unknown> };
export type MCPConnection = { id: number; name: string; server_url: string; tools_json: Array<Record<string, unknown>> };

const TOKEN_KEY = "niche-token";
const API = "/api/v1";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined)
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${API}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  oauthStart: (provider: "google" | "github") => request<{ authorization_url: string }>(`/auth/oauth/${provider}/start`),
  getMe: () => request<{ id: number; email: string; name: string }>("/auth/me"),
  listWorkspaces: () => request<Workspace[]>("/workspaces"),
  createWorkspace: (name: string) => request<Workspace>("/workspaces", { method: "POST", body: JSON.stringify({ name }) }),
  listThreads: (workspaceId: number) => request<Thread[]>(`/workspaces/${workspaceId}/threads`),
  createThread: (workspaceId: number, title: string) =>
    request<Thread>(`/workspaces/${workspaceId}/threads`, { method: "POST", body: JSON.stringify({ title }) }),
  listMessages: (workspaceId: number, threadId: number) =>
    request<Array<{ role: string; content: string; citations: Array<Record<string, unknown>> }>>(
      `/workspaces/${workspaceId}/threads/${threadId}/messages`
    ),
  listSources: (workspaceId: number) => request<Source[]>(`/workspaces/${workspaceId}/sources`),
  addSource: (workspaceId: number, payload: { source_type: string; title: string; body?: string; url?: string }) =>
    request<Source>(`/workspaces/${workspaceId}/sources`, { method: "POST", body: JSON.stringify(payload) }),
  listMcpConnections: (workspaceId: number) => request<MCPConnection[]>(`/workspaces/${workspaceId}/mcp/connections`),
  addMcpConnection: (workspaceId: number, payload: { name: string; server_url: string; token?: string }) =>
    request<MCPConnection>(`/workspaces/${workspaceId}/mcp/connections`, { method: "POST", body: JSON.stringify(payload) }),
  discoverMcpTools: (workspaceId: number, connectionId: number) =>
    request<MCPConnection>(`/workspaces/${workspaceId}/mcp/connections/${connectionId}/discover`, { method: "POST" }),
  invokeMcpTool: (workspaceId: number, connectionId: number, tool_name: string, args: Record<string, unknown>) =>
    request<{ status: string; result?: Record<string, unknown> }>(`/workspaces/${workspaceId}/mcp/connections/${connectionId}/invoke`, {
      method: "POST",
      body: JSON.stringify({ tool_name, arguments: args, require_confirmation: false })
    }),
  listSkills: () => request<Array<{ slug: string; name: string; description: string }>>("/skills/catalog"),
  installSkill: (slug: string) => request<{ status: string; slug: string }>("/skills/install", { method: "POST", body: JSON.stringify({ slug }) }),
  listWorkflows: (workspaceId: number) => request<Array<{ id: number; name: string; description: string }>>(`/workspaces/${workspaceId}/agents/workflows`),
  createWorkflow: (workspaceId: number, payload: { name: string; description: string; steps: Array<Record<string, unknown>> }) =>
    request<{ id: number }>(`/workspaces/${workspaceId}/agents/workflows`, { method: "POST", body: JSON.stringify(payload) }),
  runWorkflow: (workspaceId: number, workflowId: number, prompt: string) =>
    request<{ result: string }>(`/workspaces/${workspaceId}/agents/workflows/${workflowId}/run`, {
      method: "POST",
      body: JSON.stringify({ prompt, context: {} })
    })
};
