import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { apiGet, apiPost } from "../utils/api.js";

function UsageBar({ label, used, limit }) {
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div className="usage-bar-block">
      <div className="usage-bar-head">
        <span>{label}</span>
        <span>{used} / {limit}</span>
      </div>
      <div className="usage-bar-track">
        <div className="usage-bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function BillingPage() {
  const { profile } = useAuth();
  const [params] = useSearchParams();
  const [usage, setUsage] = useState(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");

  async function load() {
    const data = await apiGet("/api/v1/billing/usage");
    setUsage(data);
  }

  useEffect(() => {
    load().catch((e) => setMessage(String(e.message || e)));
  }, []);

  useEffect(() => {
    if (params.get("checkout") === "success") {
      setMessage("Subscription updated — thank you!");
      load();
    }
  }, [params]);

  async function checkout(plan) {
    setBusy(plan);
    setMessage("");
    try {
      const { url } = await apiPost("/api/v1/billing/checkout", { plan });
      window.location.href = url;
    } catch (e) {
      setMessage(String(e.message || e));
    } finally {
      setBusy("");
    }
  }

  async function portal() {
    setBusy("portal");
    try {
      const { url } = await apiPost("/api/v1/billing/portal", {});
      window.location.href = url;
    } catch (e) {
      setMessage(String(e.message || e));
    } finally {
      setBusy("");
    }
  }

  const plan = usage?.plan || profile?.plan || "free";

  return (
    <section className="page-section">
      <p className="eyebrow">Billing</p>
      <h1>Plan &amp; usage</h1>
      <p className="lede">Current plan: <strong className="plan-pill">{plan}</strong></p>

      {usage ? (
        <div className="card billing-card">
          <UsageBar label="Bot launches this month" used={usage.launches.used} limit={usage.launches.limit} />
          <UsageBar label="Deck uploads this month" used={usage.uploads.used} limit={usage.uploads.limit} />
        </div>
      ) : null}

      <div className="billing-actions">
        <button type="button" className="button button-primary" disabled={!!busy} onClick={() => checkout("starter")}>
          {busy === "starter" ? "Redirecting…" : "Upgrade to Starter — $10/mo"}
        </button>
        <button type="button" className="button button-secondary" disabled={!!busy} onClick={() => checkout("pro")}>
          {busy === "pro" ? "Redirecting…" : "Upgrade to Pro — $20/mo"}
        </button>
        <button type="button" className="button button-ghost" disabled={!!busy} onClick={portal}>
          Manage subscription
        </button>
      </div>

      {message ? <p className="banner-note">{message}</p> : null}
    </section>
  );
}
