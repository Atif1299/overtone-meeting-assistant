import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import LiveTranscript from "../components/LiveTranscript.jsx";
import { apiGet } from "../utils/api.js";

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

function assistantAnswer(data) {
  if (!data?.last_status_message) return "";
  const message = String(data.last_status_message).trim();
  const statusCode = String(data.last_status_code || "").trim().toLowerCase();
  if (!message) return "";
  if (statusCode && message.toLowerCase() === statusCode) return "";
  return message;
}

export default function SessionPage() {
  const [params] = useSearchParams();
  const qSid = params.get("sid");
  const [sessionId, setSessionId] = useState(
    qSid || sessionStorage.getItem("overtone_session_id") || ""
  );
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);

  useEffect(() => {
    if (qSid) setSessionId(qSid);
  }, [qSid]);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    const tick = () => {
      apiGet(`/api/session/${sessionId}`)
        .then((d) => {
          if (!cancelled) {
            setData(d);
            setErr("");
            setLastUpdatedAt(Date.now());
          }
        })
        .catch((e) => {
          if (!cancelled) setErr(String(e.message || e));
        });
    };
    tick();
    const id = setInterval(tick, 2500);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [sessionId]);

  return (
    <section className="page-section">
      <header className="page-header reveal">
        <p className="eyebrow">Monitoring</p>
        <h1>Live session monitor</h1>
        <p className="helper-text">
          Polls session state every 2.5s — bot status, relay health, tool performance,
          and live Q&amp;A visibility for operator confidence.
        </p>
      </header>

      <div className="card stack-gap reveal">
        <label className="field">
          Session ID
          <input
            className="input"
            value={sessionId}
            placeholder="Paste a session ID or launch a bot to auto-populate"
            onChange={(e) => setSessionId(e.target.value)}
          />
        </label>
        <p className="helper-text">
          Last update:{" "}
          {lastUpdatedAt ? new Date(lastUpdatedAt).toLocaleTimeString() : "Not loaded yet"}
        </p>
      </div>

      {err ? <div className="alert error">{err}</div> : null}

      {data ? (
        <div className="card stack-gap reveal">
          <div className="section-heading">
            <h2>Session telemetry</h2>
            <p className="helper-text">
              Transport state, relay health, and tool performance for this active session.
            </p>
          </div>

          <div className="session-metrics-grid">
            <article className="stat-tile">
              <span className="stat-label">State</span>
              <span className={`badge status-${String(data.state || "unknown")}`}>
                {String(data.state || "unknown").replaceAll("_", " ")}
              </span>
            </article>
            <article className="stat-tile">
              <span className="stat-label">Agent mode</span>
              <strong>{data.agent_mode || "—"}</strong>
            </article>
            <article className="stat-tile">
              <span className="stat-label">Agent</span>
              <strong>
                {data.agent_name || "—"}
                {data.agent_version ? ` (v${data.agent_version})` : ""}
              </strong>
            </article>
            <article className="stat-tile">
              <span className="stat-label">Relay status</span>
              <strong>{data.relay_status || "—"}</strong>
            </article>
            <article className="stat-tile">
              <span className="stat-label">Tool calls / failures</span>
              <strong>
                {data.tool_calls || 0} / {data.tool_failures || 0}
              </strong>
            </article>
            <article className="stat-tile">
              <span className="stat-label">First audio latency</span>
              <strong>
                {data.first_audio_latency_ms ? `${Math.round(data.first_audio_latency_ms)} ms` : "—"}
              </strong>
            </article>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <tbody>
                <tr>
                  <th>Session ID</th>
                  <td>{data.session_id || "—"}</td>
                  <th>Bot ID</th>
                  <td>{data.bot_id || "—"}</td>
                </tr>
                <tr>
                  <th>Bot name</th>
                  <td>{data.bot_name || "—"}</td>
                  <th>Meeting</th>
                  <td className="break-all">{data.meeting_url || "—"}</td>
                </tr>
                <tr>
                  <th>Created</th>
                  <td>{formatTime(data.created_at)}</td>
                  <th>Updated</th>
                  <td>{formatTime(data.updated_at)}</td>
                </tr>
                <tr>
                  <th>Relay connected</th>
                  <td>{formatTime(data.relay_connected_at)}</td>
                  <th>Relay last event</th>
                  <td>{formatTime(data.relay_last_event_at)}</td>
                </tr>
                {data.relay_last_error ? (
                  <tr>
                    <th>Relay error</th>
                    <td colSpan={3} className="text-danger">
                      {data.relay_last_error}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>

          <LiveTranscript
            snippet={data.last_transcript_snippet}
            answerText={assistantAnswer(data)}
            state={String(data.state || "")}
          />
        </div>
      ) : (
        <div className="card">
          <p className="helper-text">
            Enter a session ID above, or launch a bot from the{" "}
            <strong>Launch</strong> section — the session ID will auto-populate here.
          </p>
        </div>
      )}
    </section>
  );
}
