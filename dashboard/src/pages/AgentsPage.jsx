import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../utils/api.js";

export default function AgentsPage() {
  const nav = useNavigate();
  const [agents, setAgents] = useState([]);
  const [presentations, setPresentations] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [agentNameInput, setAgentNameInput] = useState("");
  const [selectedPresentationId, setSelectedPresentationId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [activeSnapshot, setActiveSnapshot] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const selectedPresentation = useMemo(
    () => presentations.find((p) => p.presentation_id === selectedPresentationId) || null,
    [presentations, selectedPresentationId]
  );

  async function loadPresentations() {
    const data = await apiGet("/api/v1/presentations");
    setPresentations(Array.isArray(data) ? data : []);
  }

  async function loadAgents() {
    const data = await apiGet("/api/agents");
    const list = Array.isArray(data) ? data : [];
    setAgents(list);
    return list;
  }

  async function loadActiveProfile(agentName) {
    if (!agentName) return;
    const data = await apiGet(`/api/agents/${encodeURIComponent(agentName)}/versions`);
    const list = Array.isArray(data) ? data : [];
    const active = list.find((v) => v.is_active) || list[0] || null;
    setPrompt(active?.system_prompt || "");
    setSelectedPresentationId(active?.presentation_id || "");
    setAgentNameInput(agentName);
    setActiveSnapshot(
      active
        ? { versionNumber: active.version_number, updatedAt: active.created_at }
        : null
    );
  }

  function selectAgent(agent) {
    setIsCreating(false);
    setSelectedAgent(agent.agent_name);
    setError("");
    setInfo("");
  }

  function startCreate() {
    setIsCreating(true);
    setSelectedAgent(null);
    setAgentNameInput("");
    setSelectedPresentationId("");
    setPrompt("");
    setActiveSnapshot(null);
    setError("");
    setInfo("");
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await loadPresentations();
        await loadAgents();
      } catch (e) {
        if (!cancelled) setError(String(e.message || e));
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!selectedAgent) return;
    let cancelled = false;
    (async () => {
      try {
        await loadActiveProfile(selectedAgent);
      } catch (e) {
        if (!cancelled) setError(String(e.message || e));
      }
    })();
    return () => { cancelled = true; };
  }, [selectedAgent]);

  async function saveProfile() {
    if (!agentNameInput.trim() || !prompt.trim()) return;
    setLoading(true);
    setError("");
    setInfo("");
    try {
      const created = await apiPost(
        `/api/agents/${encodeURIComponent(agentNameInput.trim())}/versions`,
        {
          system_prompt: prompt.trim(),
          presentation_id: selectedPresentationId || undefined,
          activate: true,
        }
      );
      setIsCreating(false);
      setSelectedAgent(created.agent_name);
      await loadAgents();
      await loadActiveProfile(created.agent_name);
      setInfo(`Saved ${created.agent_name} — v${created.version_number || "1"} is now active.`);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  const readyPresentations = presentations.filter((p) => p.status === "ready" && p.total_pages > 0);
  const showEditor = isCreating || selectedAgent;

  return (
    <section className="page-section">
      <header className="page-header reveal">
        <p className="eyebrow">Agents</p>
        <h1>Agent Studio</h1>
        <p className="helper-text">
          Create and manage AI agent profiles. Each agent has a system prompt and an
          optional knowledge base that constrains its RAG retrieval.
        </p>
      </header>

      {/* ── Agent Cards ─────────────────────────────────────────── */}
      <div className="card stack-gap reveal">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="section-heading" style={{ margin: 0 }}>
            <h2>Agents</h2>
          </div>
          <button
            type="button"
            className="button button-primary button-sm"
            onClick={startCreate}
          >
            + New agent
          </button>
        </div>

        {!agents.length && !isCreating ? (
          <div style={{ textAlign: "center", padding: "2rem 0" }}>
            <p style={{ color: "var(--text-muted)", marginBottom: "0.75rem" }}>
              No agents yet. Create your first one.
            </p>
            <button type="button" className="button button-primary" onClick={startCreate}>
              Create agent
            </button>
          </div>
        ) : (
          <div className="agent-card-grid">
            {agents.map((agent) => {
              const isSelected = !isCreating && selectedAgent === agent.agent_name;
              const kb = readyPresentations.find(
                (p) => p.presentation_id === agent.active_presentation_id
              );
              return (
                <button
                  key={agent.agent_name}
                  type="button"
                  className={`agent-card ${isSelected ? "agent-card-active" : ""}`}
                  onClick={() => selectAgent(agent)}
                >
                  <div className="agent-card-header">
                    <span className="agent-card-name">{agent.agent_name}</span>
                    {agent.active_version ? (
                      <span className="agent-card-version">v{agent.active_version}</span>
                    ) : null}
                  </div>
                  <div className="agent-card-meta">
                    {kb ? (
                      <span className="agent-card-kb" title={kb.presentation_id}>
                        {kb.filename}
                      </span>
                    ) : (
                      <span className="agent-card-kb agent-card-kb-none">No knowledge base</span>
                    )}
                  </div>
                  {isSelected && <div className="agent-card-indicator" />}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Editor Panel ────────────────────────────────────────── */}
      {showEditor ? (
        <div className="card stack-gap reveal" style={{ marginTop: "1rem" }}>
          <div className="section-heading">
            <h2>{isCreating ? "Create new agent" : `Edit: ${selectedAgent}`}</h2>
            {activeSnapshot && !isCreating ? (
              <p className="helper-text">
                Active version: <strong>v{activeSnapshot.versionNumber}</strong>
                {activeSnapshot.updatedAt
                  ? ` · ${new Date(activeSnapshot.updatedAt).toLocaleDateString()}`
                  : ""}
              </p>
            ) : null}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", alignItems: "start" }}>
            <label className="field">
              Agent name
              <input
                className="input"
                value={agentNameInput}
                onChange={(e) => setAgentNameInput(e.target.value)}
                placeholder="e.g. sales-agent, demo-bot"
                disabled={!isCreating && !!selectedAgent}
              />
              {!isCreating && selectedAgent ? (
                <span className="field-hint">Agent names are immutable after creation.</span>
              ) : null}
            </label>
            <label className="field">
              Knowledge base
              <select
                className="input"
                value={selectedPresentationId}
                onChange={(e) => setSelectedPresentationId(e.target.value)}
              >
                <option value="">None — general assistant</option>
                {readyPresentations.map((p) => (
                  <option key={p.presentation_id} value={p.presentation_id}>
                    {p.filename} ({p.total_pages} pages) — {p.presentation_id.slice(0, 8)}
                  </option>
                ))}
              </select>
              {!readyPresentations.length ? (
                <span className="field-hint">
                  No indexed presentations.{" "}
                  <button type="button" className="button-link" onClick={() => nav("/presentations")}>
                    Upload one
                  </button>
                </span>
              ) : null}
            </label>
          </div>

          {selectedPresentation ? (
            <div className="scope-banner">
              RAG scope: <strong>{selectedPresentation.filename}</strong> ({selectedPresentation.total_pages} pages)
            </div>
          ) : null}

          <label className="field">
            System prompt
            <textarea
              className="input"
              rows={10}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={"You are a presentation assistant for [Company].\n\nYour role is to walk participants through the deck, answer questions grounded in the slides, and navigate to the most relevant page when asked.\n\nAlways be concise — 2-3 sentences per answer."}
            />
          </label>

          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <button
              type="button"
              className="button button-primary"
              disabled={loading || !agentNameInput.trim() || !prompt.trim()}
              onClick={saveProfile}
            >
              {loading ? "Saving..." : isCreating ? "Create agent" : "Save new version"}
            </button>
            {showEditor && (
              <button
                type="button"
                className="button button-ghost"
                onClick={() => {
                  setIsCreating(false);
                  setSelectedAgent(null);
                  setInfo("");
                  setError("");
                }}
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      ) : null}

      {error ? <div className="alert error">{error}</div> : null}
      {info ? <div className="alert">{info}</div> : null}
    </section>
  );
}
