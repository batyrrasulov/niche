import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken, MCPConnection, Source, Thread, Workspace } from "./api";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  citations?: Array<Record<string, unknown>>;
};

type FlowStep = {
  id: string;
  label: string;
  status: "todo" | "current" | "done";
};

export function App() {
  const [tokenInput, setTokenInput] = useState(getToken());
  const [sessionUser, setSessionUser] = useState<{ email: string; name: string } | null>(null);
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
    setError("");
    try {
      const me = await api.getMe();
      setSessionUser({ email: me.email, name: me.name });
    } catch {
      setSessionUser(null);
    }
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
    setError("");
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

  async function onInstallSkill(slug: string) {
    const result = await api.installSkill(slug);
    setToolLog((prev) => [...prev, `skill:${result.slug} -> ${result.status}`]);
  }

  const appReady = useMemo(() => !!getToken(), [tokenInput]);
  const flowSteps = useMemo<FlowStep[]>(() => {
    return [
      { id: "auth", label: "Auth session ready", status: appReady ? "done" : "current" },
      {
        id: "workspace",
        label: "Workspace selected",
        status: activeWorkspace ? "done" : appReady ? "current" : "todo"
      },
      {
        id: "thread",
        label: "Thread active",
        status: activeThread ? "done" : activeWorkspace ? "current" : "todo"
      },
      {
        id: "source",
        label: "Knowledge source loaded",
        status: sources.length ? "done" : activeWorkspace ? "current" : "todo"
      },
      {
        id: "mcp",
        label: "MCP connection online",
        status: connections.length ? "done" : activeWorkspace ? "current" : "todo"
      },
      {
        id: "workflow",
        label: "Workflow ready",
        status: workflows.length ? "done" : activeWorkspace ? "current" : "todo"
      },
      {
        id: "chat",
        label: "Chat orchestration stream",
        status: messages.length ? "done" : activeThread ? "current" : "todo"
      }
    ];
  }, [appReady, activeWorkspace, activeThread, sources.length, connections.length, workflows.length, messages.length]);

  const runtimeHealth = streaming ? "Streaming" : appReady ? "Ready" : "Idle";
  const authOnline = Boolean(sessionUser);
  const runtimeUp = runtimeHealth === "Ready" || runtimeHealth === "Streaming";
  const showMotto = messages.length === 0 && toolLog.length === 0 && !streaming && !prompt.trim();
  const artifacts = useMemo(
    () => [
      ...sources.slice(0, 3).map((source) => `source:${source.title}`),
      ...connections.slice(0, 2).map((connection) => `mcp:${connection.name}`),
      ...workflows.slice(0, 2).map((workflow) => `workflow:${workflow.name}`)
    ],
    [sources, connections, workflows]
  );
  const activityItems = useMemo(() => {
    if (toolLog.length > 0) {
      return toolLog.slice(-6).reverse().map((line) => {
        const lowered = line.toLowerCase();
        const status = lowered.includes("failed")
          ? "error"
          : lowered.includes("completed") || lowered.includes("installed") || lowered.includes("running")
            ? "done"
            : "current";
        return { title: line, detail: status === "done" ? "Done" : status === "error" ? "Needs attention" : "In progress", status };
      });
    }

    return flowSteps
      .filter((step) => step.status !== "todo")
      .slice(0, 6)
      .map((step) => ({
        title: step.label,
        detail: step.status === "done" ? "Done" : "In progress",
        status: step.status === "done" ? "done" : "current"
      }));
  }, [toolLog, flowSteps]);

  if (!appReady) {
    return (
      <main className="page">
        <section className="panel narrow">
          <h1>Niche</h1>
          <p className="muted">Terminal-first orchestration with live runtime context</p>
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
      <header className="topbar">
        <div>
          <h1>Niche</h1>
          <p>Agentic RAG + MCP tools + workflow runtime</p>
        </div>
        <div className="top-meta">
          <span className={`pill ${authOnline ? "pill-up" : "pill-down"}`}>Auth: {authOnline ? "Online" : "Token only"}</span>
          <span className={`pill ${runtimeUp ? "pill-up" : "pill-down"}`}>Runtime: {runtimeHealth}</span>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="layout">
        <aside className="panel">
          <section>
            <h2>Session</h2>
            <ul className="kv">
              <li>
                <span>User</span>
                <strong>{sessionUser?.email ?? "not signed in"}</strong>
              </li>
              <li>
                <span>Profile</span>
                <strong>{sessionUser?.name ?? "none"}</strong>
              </li>
              <li>
                <span>Workspace</span>
                <strong>{activeWorkspace?.name ?? "none"}</strong>
              </li>
              <li>
                <span>Thread</span>
                <strong>{activeThread?.title ?? "none"}</strong>
              </li>
              <li>
                <span>Catalog</span>
                <strong>{sources.length ? `${sources.length} sources` : "local only"}</strong>
              </li>
            </ul>
          </section>

          <section>
            <h2>Runtime</h2>
            <div className="group">
              <h3>Plugins</h3>
              <ul className="list">
                <li>{connections.length ? "mcp-runtime" : "none"}</li>
              </ul>
            </div>
            <div className="group">
              <h3>Skills</h3>
              <ul className="list">
                {(skills.length ? skills.slice(0, 4).map((skill) => skill.slug) : ["none"]).map((entry) => (
                  <li key={entry}>{entry}</li>
                ))}
              </ul>
            </div>
            <div className="group">
              <h3>MCP Connectors</h3>
              <ul className="list">
                {(connections.length ? connections.map((connection) => connection.name) : ["none"]).map((entry) => (
                  <li key={entry}>{entry}</li>
                ))}
              </ul>
            </div>
            <div className="group">
              <h3>Subagents</h3>
              <ul className="list">
                {(workflows.length ? workflows.map((workflow) => workflow.name) : ["none"]).map((entry) => (
                  <li key={entry}>{entry}</li>
                ))}
              </ul>
            </div>
          </section>
        </aside>

        <section className="terminal-wrap">
          <div className="terminal">
            {showMotto ? <p className="line sys motto">Niche is not just an "LLM wrapper". Try it by asking below.</p> : null}
            {messages.map((message, i) => (
              <div key={i}>
                <p className={`line ${message.role === "user" ? "cmd" : "ok"}`}>
                  {message.role === "user" ? "you@studio$" : "niche@runtime"} {message.content}
                </p>
                {message.citations?.length ? (
                  <p className="line sys">
                    citations: {message.citations.map((item) => String(item.title || "source")).join(", ")}
                  </p>
                ) : null}
              </div>
            ))}
            {toolLog.map((line, idx) => (
              <p key={`tool-${idx}`} className="line warn">
                {line}
              </p>
            ))}
          </div>
          <form onSubmit={onSendMessage} className="cmd-form">
            <span className="prompt">niche@studio:~$</span>
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Type here"
            />
            <button type="submit" disabled={streaming}>
              {streaming ? "Running" : "Run"}
            </button>
          </form>
        </section>

        <aside className="panel">
          <section>
            <h2>Activity</h2>
            <ul className="activity-list">
              {activityItems.length === 0 ? (
                <li className="activity-item idle">
                  <span className="activity-icon">○</span>
                  <div>
                    <p className="activity-title">No activity yet</p>
                    <p className="activity-detail">Start by creating a workspace or sending a prompt.</p>
                  </div>
                </li>
              ) : (
                activityItems.map((item, index) => (
                  <li key={`${item.title}-${index}`} className={`activity-item ${item.status}`}>
                    <span className="activity-icon">{item.status === "done" ? "✓" : item.status === "error" ? "!" : "•"}</span>
                    <div>
                      <p className="activity-title">{item.title}</p>
                      <p className="activity-detail">{item.detail}</p>
                    </div>
                  </li>
                ))
              )}
            </ul>
          </section>

          <section>
            <h2>Artifacts</h2>
            <ul className="list">
              {(artifacts.length ? artifacts : ["none"]).map((artifact) => (
                <li key={artifact}>{artifact}</li>
              ))}
            </ul>
          </section>

          <section>
            <h2>Quick Commands</h2>
            <div className="quick">
              <button onClick={onCreateWorkspace}>/workspace new</button>
              <button onClick={onCreateThread}>/thread new</button>
              <button onClick={onAddTextSource}>/source add text</button>
              <button onClick={onAddUrlSource}>/source add url</button>
              <button onClick={onAddConnection}>/mcp connect</button>
              <button onClick={onCreateWorkflow}>/workflow create</button>
              <button onClick={() => setPrompt("Summarize the current workspace context and sources.")}>/chat summarize</button>
            </div>
          </section>

          <section>
            <h2>Workspaces</h2>
            <ul className="list">
              {workspaces.map((ws) => (
                <li key={ws.id}>
                  <button
                    className={activeWorkspace?.id === ws.id ? "active block" : "block"}
                    onClick={async () => {
                      setActiveWorkspace(ws);
                      await loadWorkspace(ws.id);
                    }}
                  >
                    {ws.name}
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2>Threads</h2>
            <ul className="list">
              {threads.map((thread) => (
                <li key={thread.id}>
                  <button
                    className={activeThread?.id === thread.id ? "active block" : "block"}
                    onClick={async () => {
                      setActiveThread(thread);
                      if (!activeWorkspace) return;
                      setMessages((await api.listMessages(activeWorkspace.id, thread.id)) as ChatMessage[]);
                    }}
                  >
                    {thread.title}
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2>MCP</h2>
            {connections.map((connection) => (
              <div key={connection.id} className="entity-card">
                <p className="entity-title">{connection.name}</p>
                <p className="entity-subtitle">{connection.server_url}</p>
                <div className="row entity-actions">
                  <button onClick={() => onDiscover(connection)}>Discover</button>
                  <button onClick={() => onInvoke(connection)}>Invoke</button>
                </div>
              </div>
            ))}
          </section>

          <section>
            <h2>Skills</h2>
            {skills.map((skill) => (
              <div key={skill.slug} className="entity-card">
                <p className="entity-title">{skill.name}</p>
                <p className="entity-subtitle">{skill.description}</p>
                <button onClick={() => onInstallSkill(skill.slug)}>Install</button>
              </div>
            ))}
          </section>

          <section>
            <h2>Workflows</h2>
            {workflows.map((workflow) => (
              <div key={workflow.id} className="entity-card">
                <p className="entity-title">{workflow.name}</p>
                <div className="row entity-actions">
                  <button onClick={() => onRunWorkflow(workflow.id)}>Run</button>
                </div>
              </div>
            ))}
          </section>
        </aside>
      </section>
    </main>
  );
}

function promptUser(label: string): string {
  const value = window.prompt(label);
  return value ? value.trim() : "";
}
