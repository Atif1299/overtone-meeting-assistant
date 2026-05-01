import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import BotConfigForm from "../components/BotConfigForm.jsx";
import { apiGet, apiPost, apiBase } from "../utils/api.js";

export default function LaunchPage() {
  const nav = useNavigate();
  const [cfg, setCfg] = useState({
    bot_name: "Overtone Agent",
    meeting_url: "",
    presentation_id: "",
    agent_name: "default",
    agent_mode: "realtime",
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
        const list = Array.isArray(data) ? data : [];
        setPresentations(list);
        setPresentationsError("");
        if (
          list.length > 0 &&
          (!cfg.presentation_id || !list.some((item) => item.presentation_id === cfg.presentation_id))
        ) {
          setCfg((prev) => ({ ...prev, presentation_id: list[0].presentation_id }));
        }
      } catch (e) {
        if (!cancelled) {
          setPresentationsError(String(e.message || e));
        }
      }
    }

    async function loadAgents() {
      try {
        const data = await apiGet("/api/agents");
        if (cancelled) return;
        const list = Array.isArray(data) ? data : [];
        setAgents(list);
        setAgentsError("");
        if (list.length > 0) {
          const matched = list.find((item) => item.agent_name === cfg.agent_name) || list[0];
          setCfg((prev) => ({
            ...prev,
            agent_name: matched.agent_name,
            presentation_id:
              matched.active_presentation_id || prev.presentation_id || list[0].active_presentation_id || "",
          }));
        }
      } catch (e) {
        if (!cancelled) {
          setAgentsError(String(e.message || e));
        }
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
      const payload = {
        ...cfg,
        presentation_id: cfg.presentation_id || undefined,
      };
      const r = await apiPost("/api/launch-bot", payload);
      setResult(r);
      sessionStorage.setItem("overtone_session_id", r.session_id);
      sessionStorage.setItem("overtone_bot_id", r.bot_id);
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
        <p className="helper-text">
          Join a meeting, bind an agent profile, and route output media to the presentation UI.
          The selected presentation remains the strict filter for RAG retrieval.
        </p>
      </header>

      <div className="card stack-gap reveal">
        <div className="section-heading">
          <h2>Launch configuration</h2>
          <p className="helper-text">
            Fill the meeting details, choose mode/profile, then launch with one action.
          </p>
        </div>
        <BotConfigForm
          value={cfg}
          presentations={presentations}
          agents={agents}
          onChange={setCfg}
          onSubmit={launch}
          disabled={loading}
        />
        {presentationsError ? (
          <div className="alert warning">
            Could not load presentations automatically: {presentationsError}
          </div>
        ) : null}
        {agentsError ? (
          <div className="alert warning">Could not load agents automatically: {agentsError}</div>
        ) : null}
      </div>

      {err ? <div className="alert error">{err}</div> : null}

      {result ? (
        <div className="card stack-gap launch-result reveal">
          <h2>Bot launched</h2>
          <div className="session-metrics-grid">
            <p>
              <strong>session_id:</strong> {result.session_id}
            </p>
            <p>
              <strong>bot_id:</strong> {result.bot_id}
            </p>
            <p>
              <strong>Agent mode:</strong> {result.agent_mode}
            </p>
            <p>
              <strong>Agent:</strong> {result.agent_name}
              {result.agent_version ? ` (v${result.agent_version})` : ""}
            </p>
          </div>
          <p className="helper-text break-all">
            <strong>Output media URL:</strong> {result.output_media_url}
          </p>
          {result.realtime_relay_url ? (
            <p className="helper-text break-all">
              <strong>Realtime relay:</strong> {result.realtime_relay_url}
            </p>
          ) : null}
          <div className="button-row">
            <button
              type="button"
              className="button button-primary"
              onClick={() => nav(`/session?sid=${encodeURIComponent(result.session_id)}`)}
            >
              Open session monitor
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
