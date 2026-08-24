import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import BotConfigForm from "../components/BotConfigForm.jsx";
import { apiGet, apiPost } from "../utils/api.js";

export default function LaunchPage() {
  const nav = useNavigate();
  const [cfg, setCfg] = useState({
    bot_name: "Overtone Agent",
    meeting_url: "",
    presentation_id: "",
    agent_name: "default",
  });
  const [presentations, setPresentations] = useState([]);
  const [agents, setAgents] = useState([]);
  const [presentationsError, setPresentationsError] = useState("");
  const [agentsError, setAgentsError] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadPresentations() {
      try {
        const data = await apiGet("/api/v1/presentations");
        if (cancelled) return;
        const list = (Array.isArray(data) ? data : []).filter((item) => item.status === "ready");
        setPresentations(list);
        setPresentationsError("");
        if (list.length > 0 && !cfg.presentation_id) {
          setCfg((prev) => ({ ...prev, presentation_id: list[0].presentation_id }));
        }
      } catch (e) {
        if (!cancelled) setPresentationsError(String(e.message || e));
      }
    }

    async function loadAgents() {
      try {
        const data = await apiGet("/api/v1/agents");
        if (cancelled) return;
        const names = Array.isArray(data?.agents) ? data.agents : ["default"];
        setAgents(names.map((agent_name) => ({ agent_name })));
        setAgentsError("");
      } catch (e) {
        if (!cancelled) setAgentsError(String(e.message || e));
      }
    }

    loadPresentations();
    loadAgents();
    return () => {
      cancelled = true;
    };
  }, []);

  async function launch() {
    setErr("");
    setLoading(true);
    try {
      const r = await apiPost("/api/v1/sessions/launch", {
        meeting_url: cfg.meeting_url,
        presentation_id: cfg.presentation_id,
        bot_name: cfg.bot_name,
        agent_name: cfg.agent_name || "default",
      });
      setResult(r);
      sessionStorage.setItem("overtone_session_id", r.session_id);
      sessionStorage.setItem("overtone_presentation_id", r.presentation_id);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="page-section">
      <header className="page-header reveal">
        <p className="eyebrow">Operations</p>
        <h1>Launch meeting bot</h1>
        <p className="lede">Paste a Meet/Zoom/Teams URL and a ready deck. Realtime voice only.</p>
      </header>

      {presentationsError && <p className="error">{presentationsError}</p>}
      {agentsError && <p className="error">{agentsError}</p>}
      {err && <p className="error">{err}</p>}

      <BotConfigForm
        value={cfg}
        onChange={setCfg}
        presentations={presentations}
        agents={agents}
        onSubmit={launch}
        disabled={loading}
      />

      <div className="row gap">
        {result?.session_id && (
          <button type="button" className="btn" onClick={() => nav("/session")}>
            Open session
          </button>
        )}
      </div>

      {result && (
        <div className="card stack-gap reveal" style={{ marginTop: 16 }}>
          <div className="section-heading">
            <h2>Session started</h2>
            <p className="helper-text">Bot is joining the meeting. Open Session to monitor live status.</p>
          </div>
          <dl className="launch-result-grid">
            <div>
              <dt>Session ID</dt>
              <dd><code>{result.session_id}</code></dd>
            </div>
            <div>
              <dt>Recall bot</dt>
              <dd><code>{result.recall_bot_id || "pending"}</code></dd>
            </div>
            <div>
              <dt>State</dt>
              <dd>{result.state}</dd>
            </div>
          </dl>
          <details>
            <summary className="helper-text">Raw launch response</summary>
            <pre className="code-block">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      )}
    </section>
  );
}
