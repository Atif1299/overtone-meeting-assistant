import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "../utils/api.js";

function MetricCard({ label, value, note }) {
  return (
    <article className="metric-card reveal">
      <p className="metric-label">{label}</p>
      <p className="metric-value">{value}</p>
      {note ? <p className="metric-note">{note}</p> : null}
    </article>
  );
}

export default function OverviewPage() {
  const [health, setHealth] = useState(null);
  const [presentations, setPresentations] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [healthData, presentationData] = await Promise.all([
          apiGet("/health"),
          apiGet("/api/v1/presentations"),
        ]);
        if (!cancelled) {
          setHealth(healthData);
          setPresentations(Array.isArray(presentationData) ? presentationData : []);
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(String(err.message || err));
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const latestPresentation = presentations[0];

  return (
    <section className="page-section">
      <header className="page-header reveal">
        <p className="eyebrow">Command Deck</p>
        <h1>Operations overview</h1>
        <p className="helper-text">
          End-to-end health, ingestion readiness, and launch workflow visibility in one place.
          Built for operators running high-stakes live presentation agents.
        </p>
      </header>

      {error ? (
        <div className="alert error">Unable to load overview data: {error}</div>
      ) : (
        <div className="metric-grid">
          <MetricCard
            label="Backend status"
            value={health?.status ? "Online" : "Unknown"}
            note={health ? "Health endpoint reachable" : "Checking connection..."}
          />
          <MetricCard
            label="Active sessions"
            value={health?.active_sessions ?? "—"}
            note="In-memory sessions currently live"
          />
          <MetricCard
            label="Transcript queue"
            value={health?.transcript_queue_depth ?? "—"}
            note="Pending final transcript jobs"
          />
          <MetricCard
            label="Presentations"
            value={presentations.length}
            note={latestPresentation ? `Latest: ${latestPresentation.filename}` : "No uploads yet"}
          />
        </div>
      )}

      <div className="card stack-gap reveal">
        <div className="section-heading">
          <h2>Quick actions</h2>
          <p className="helper-text">
            Jump directly into the flow: ingest knowledge, launch a bot, and monitor conversations.
          </p>
        </div>
        <div className="button-row quick-actions-grid">
          <Link to="/upload" className="button button-primary">
            Knowledge base
          </Link>
          <Link to="/launch" className="button button-secondary">
            Launch meeting bot
          </Link>
          <Link to="/session" className="button button-ghost">
            Monitor session
          </Link>
        </div>
      </div>
    </section>
  );
}
