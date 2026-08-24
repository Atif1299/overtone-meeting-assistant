import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../utils/api.js";

export default function AgentsPage() {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState("default");
  const [prompt, setPrompt] = useState("");
  const [version, setVersion] = useState(null);
  const [nameInput, setNameInput] = useState("default");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  async function refresh() {
    const data = await apiGet("/api/v1/agents");
    const names = Array.isArray(data?.agents) ? data.agents : ["default"];
    setAgents(names);
    const activeName = selectedAgent || names[0] || "default";
    const versions = await apiGet(`/api/v1/agents/${encodeURIComponent(activeName)}/versions`);
    const list = Array.isArray(versions) ? versions : [];
    const active = list.find((v) => v.is_active) || list[0];
    setPrompt(active?.instructions || "");
    setVersion(active?.version ?? null);
    setNameInput(activeName);
  }

  useEffect(() => {
    refresh().catch((e) => setError(String(e.message || e)));
  }, [selectedAgent]);

  async function save() {
    setLoading(true);
    setError("");
    setInfo("");
    try {
      const name = nameInput.trim() || "default";
      const created = await apiPost(`/api/v1/agents/${encodeURIComponent(name)}/versions`, {
        instructions: prompt.trim(),
      });
      await apiPost(`/api/v1/agents/${encodeURIComponent(name)}/activate`, {
        version: created.version,
      });
      setSelectedAgent(name);
      setInfo(`Saved ${name} v${created.version} and activated.`);
      await refresh();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-section">
      <header className="page-header">
        <p className="eyebrow">Agents</p>
        <h1>Agent Studio</h1>
        <p className="helper-text">Versioned system instructions for the realtime voice agent.</p>
      </header>

      <div className="card stack-gap">
        <label className="field">
          Agent
          <select
            className="input"
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
          >
            {agents.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Agent name (for new version / new agent)
          <input className="input" value={nameInput} onChange={(e) => setNameInput(e.target.value)} />
        </label>
        <label className="field">
          Instructions {version != null ? `(active v${version})` : ""}
          <textarea className="input" rows={12} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </label>
        <button type="button" className="button button-primary" disabled={loading || !prompt.trim()} onClick={save}>
          {loading ? "Saving…" : "Save & activate"}
        </button>
      </div>
      {error ? <div className="alert error">{error}</div> : null}
      {info ? <div className="alert">{info}</div> : null}
    </section>
  );
}
