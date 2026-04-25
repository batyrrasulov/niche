import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken, MCPConnection, Source, Thread, Workspace } from "./api";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: Array<Record<string, unknown>>;
};

export function App() {
  const [tokenInput, setTokenInput] = useState(getToken());
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThread, setActiveThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [connections, setConnections] = useState<MCPConnection[]>([]);
  const [skills, setSkills] = useState<Array<{ slug: string; name: string; description: string }>>([]);
  const [workflows, setWorkflows] = useState<Array<{ id: number; name: string; description: string }>>([]);
  const [prompt, setPrompt] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [toolLog, setToolLog] = useState<string[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) return;
    bootstrap().catch((err: Error) => setError(err.message));
  }, []);

  async function bootstrap() {
    const ws = await api.listWorkspaces();
    setWorkspaces(ws);
    if (!ws.length) return;
    setActiveWorkspace(ws[0]);
    await loadWorkspace(ws[0].id);
  }

  async function loadWorkspace(workspaceId: number) {
    const [t, s, c, sk, wf] = await Promise.all([
      api.listThreads(workspaceId),
      api.listSources(workspaceId),
      api.listMcpConnections(workspaceId),
      api.listSkills(),
      api.listWorkflows(workspaceId)
    ]);
    setThreads(t);
    setSources(s);
    setConnections(c);
    setSkills(sk);
    setWorkflows(wf);
    if (t.length) {
      setActiveThread(t[0]);
      const existing = await api.listMessages(workspaceId, t[0].id);
      setMessages(existing as ChatMessage[]);
    } else {
      setActiveThread(null);
      setMessages([]);
    }
  }

  async function onSaveToken(e: FormEvent) {
    e.preventDefault();
    setToken(tokenInput.trim());
    await bootstrap();
  }

  async function onCreateWorkspace() {
    const name = promptUser("Workspace name");
    if (!name) return;
    const ws = await api.createWorkspace(name);
    const next = [ws, ...workspaces];
    setWorkspaces(next);
    setActiveWorkspace(ws);
    await loadWorkspace(ws.id);
  }

  async function onCreateThread() {
    if (!activeWorkspace) return;
    const title = promptUser("Thread title") || "New thread";
    const thread = await api.createThread(activeWorkspace.id, title);
    setThreads([thread, ...threads]);
    setActiveThread(thread);
    setMessages([]);
  }

  async function onAddTextSource() {
    if (!activeWorkspace) return;
    const title = promptUser("Source title");
    const body = promptUser("Paste content");
    if (!title || !body) return;
    const source = await api.addSource(activeWorkspace.id, { source_type: "text", title, body });
    setSources([source, ...sources]);
  }

  async function onAddUrlSource() {
    if (!activeWorkspace) return;
    const url = promptUser("URL to ingest");
    if (!url) return;
    const source = await api.addSource(activeWorkspace.id, { source_type: "url", title: url, url });
    setSources([source, ...sources]);
  }

  async function onSendMessage(e: FormEvent) {
    e.preventDefault();
    if (!activeWorkspace || !activeThread || !prompt.trim() || streaming) return;
    const content = prompt.trim();
    setPrompt("");
    setMessages((prev) => [...prev, { role: "user", content }, { role: "assistant", content: "" }]);
    setStreaming(true);
    setToolLog([]);

    const res = await fetch(
      `/api/v1/workspaces/${activeWorkspace.id}/threads/${activeThread.id}/messages`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${getToken()}`
        },
        body: JSON.stringify({ content, use_web: true, use_mcp: true })
      }
    );
    if (!res.body) {
      setStreaming(false);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const raw of events) {
        const eventLine = raw.split("\n").find((line) => line.startsWith("event:"));
        const dataLine = raw.split("\n").find((line) => line.startsWith("data:"));
        if (!eventLine || !dataLine) continue;
        const event = eventLine.replace("event:", "").trim();
        const payload = JSON.parse(dataLine.replace("data:", "").trim());
        if (event === "token") {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === "assistant") {
              last.content += payload.token;
            }
            return next;
          });
        }
        if (event === "tool_event") {
          setToolLog((prev) => [...prev, `${payload.type}: ${payload.status}`]);
        }
        if (event === "final") {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === "assistant") {
              last.content = payload.content;
              last.citations = payload.citations;
            }
            return next;
          });
        }
      }
    }
    setStreaming(false);
  }

  async function onAddConnection() {
    if (!activeWorkspace) return;
    const name = promptUser("Connection name");
    const server_url = promptUser("MCP server URL");
    if (!name || !server_url) return;
    const created = await api.addMcpConnection(activeWorkspace.id, { name, server_url });
    setConnections((prev) => [created, ...prev]);
  }

  async function onDiscover(connection: MCPConnection) {
    if (!activeWorkspace) return;
    const updated = await api.discoverMcpTools(activeWorkspace.id, connection.id);
    setConnections((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
  }

  async function onInvoke(connection: MCPConnection) {
    if (!activeWorkspace) return;
    const toolName = promptUser("Tool name to invoke");
    if (!toolName) return;
    const result = await api.invokeMcpTool(activeWorkspace.id, connection.id, toolName, {});
    setToolLog((prev) => [...prev, `invoke:${toolName} -> ${result.status}`]);
  }

  async function onCreateWorkflow() {
    if (!activeWorkspace) return;
    const name = promptUser("Workflow name");
    if (!name) return;
    await api.createWorkflow(activeWorkspace.id, {
      name,
      description: "Generated in app",
      steps: [{ name: "kb-step", mode: "append-context" }, { name: "tool-step", mode: "tool", tool: "mcp" }]
    });
    setWorkflows(await api.listWorkflows(activeWorkspace.id));
  }

  async function onRunWorkflow(workflowId: number) {
    if (!activeWorkspace) return;
    const result = await api.runWorkflow(activeWorkspace.id, workflowId, "Run workflow from UI");
    setToolLog((prev) => [...prev, `workflow:${workflowId} -> ${result.result.slice(0, 80)}`]);
  }

  const appReady = useMemo(() => !!getToken(), [tokenInput]);

  if (!appReady) {
    return (
      <main className="page">
        <section className="card narrow">
          <h1>NicheGPT</h1>
          <p>Paste a valid bearer token from OAuth callback to start.</p>
          <form onSubmit={onSaveToken} className="stack">
            <input value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} placeholder="Bearer token" />
            <button type="submit">Save token</button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="page">
      <header className="header">
        <div>
          <h1>NicheGPT Studio</h1>
          <p>RAG + MCP actions + workflows</p>
        </div>
        <button onClick={onCreateWorkspace}>New Workspace</button>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="grid">
        <aside className="card">
          <h2>Workspaces</h2>
          {workspaces.map((ws) => (
            <button
              key={ws.id}
              className={activeWorkspace?.id === ws.id ? "active" : ""}
              onClick={async () => {
                setActiveWorkspace(ws);
                await loadWorkspace(ws.id);
              }}
            >
              {ws.name}
            </button>
          ))}
          <hr />
          <h3>Threads</h3>
          <button onClick={onCreateThread}>New Thread</button>
          {threads.map((thread) => (
            <button key={thread.id} className={activeThread?.id === thread.id ? "active" : ""} onClick={async () => {
              setActiveThread(thread);
              if (!activeWorkspace) return;
              setMessages(await api.listMessages(activeWorkspace.id, thread.id) as ChatMessage[]);
            }}>
              {thread.title}
            </button>
          ))}
        </aside>

        <section className="card">
          <h2>Chat</h2>
          <div className="messages">
            {messages.map((message, i) => (
              <article key={i} className={`bubble ${message.role}`}>
                <strong>{message.role}</strong>
                <p>{message.content}</p>
                {message.citations && message.citations.length > 0 && (
                  <div className="citations">
                    {message.citations.map((item, idx) => (
                      <span key={idx}>{String(item.title || "Source")}</span>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
          <form onSubmit={onSendMessage} className="stack">
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Ask with your data..." />
            <button type="submit" disabled={streaming}>{streaming ? "Streaming..." : "Send"}</button>
          </form>
        </section>

        <aside className="card">
          <h2>Sources</h2>
          <div className="row">
            <button onClick={onAddTextSource}>Add Text</button>
            <button onClick={onAddUrlSource}>Add URL</button>
          </div>
          <ul>{sources.map((s) => <li key={s.id}>{s.title}</li>)}</ul>

          <h2>MCP</h2>
          <button onClick={onAddConnection}>Add Connection</button>
          {connections.map((connection) => (
            <div key={connection.id} className="mini">
              <strong>{connection.name}</strong>
              <p>{connection.server_url}</p>
              <div className="row">
                <button onClick={() => onDiscover(connection)}>Discover</button>
                <button onClick={() => onInvoke(connection)}>Invoke</button>
              </div>
            </div>
          ))}

          <h2>Skills</h2>
          {skills.map((skill) => (
            <div key={skill.slug} className="mini">
              <strong>{skill.name}</strong>
              <p>{skill.description}</p>
              <button onClick={() => api.installSkill(skill.slug)}>Install</button>
            </div>
          ))}

          <h2>Workflows</h2>
          <button onClick={onCreateWorkflow}>Create Workflow</button>
          {workflows.map((w) => (
            <div key={w.id} className="mini">
              <strong>{w.name}</strong>
              <button onClick={() => onRunWorkflow(w.id)}>Run</button>
            </div>
          ))}

          <h2>Action Log</h2>
          <ul>{toolLog.map((line, idx) => <li key={idx}>{line}</li>)}</ul>
        </aside>
      </section>
    </main>
  );
}

function promptUser(label: string): string {
  const value = window.prompt(label);
  return value ? value.trim() : "";
}
