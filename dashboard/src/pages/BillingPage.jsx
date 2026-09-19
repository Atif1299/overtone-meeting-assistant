import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { apiGet, apiPost } from "../utils/api.js";

const PADDLE_JS = "https://cdn.paddle.com/paddle/v2/paddle.js";

let paddleInit = null;
let paddleEventHandler = () => {};
const openedTransactions = new Set();

function loadPaddleScript() {
  if (window.Paddle) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector("script[data-paddle-js]");
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("Paddle.js failed to load")));
      return;
    }
    const script = document.createElement("script");
    script.src = PADDLE_JS;
    script.async = true;
    script.dataset.paddleJs = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Paddle.js failed to load"));
    document.head.appendChild(script);
  });
}

function ensurePaddle(config) {
  if (!paddleInit) {
    paddleInit = loadPaddleScript().then(() => {
      if (config.environment === "sandbox") {
        window.Paddle.Environment.set("sandbox");
      }
      const init = {
        token: config.client_token,
        checkout: {
          settings: {
            successUrl: `${window.location.origin}/app/billing?checkout=success`,
          },
        },
        eventCallback: (event) => paddleEventHandler(event),
      };
      if (config.paddle_customer_id && String(config.paddle_customer_id).startsWith("ctm_")) {
        init.pwCustomer = { id: config.paddle_customer_id };
      }
      window.Paddle.Initialize(init);
    });
  }
  return paddleInit;
}

function openCheckout(transactionId) {
  if (!transactionId || !window.Paddle || openedTransactions.has(transactionId)) return;
  openedTransactions.add(transactionId);
  window.Paddle.Checkout.open({ transactionId });
}

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
  const { profile, refreshProfile } = useAuth();
  const [params] = useSearchParams();
  const [usage, setUsage] = useState(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");

  async function load() {
    const data = await apiGet("/api/v1/billing/usage");
    setUsage(data);
    if (refreshProfile) {
      await refreshProfile();
    }
  }

  useEffect(() => {
    paddleEventHandler = (event) => {
      if (event?.name === "checkout.completed") {
        setMessage("Subscription updated — thank you!");
        load();
        setBusy("");
      }
      if (event?.name === "checkout.closed") {
        setBusy("");
      }
    };
  });

  useEffect(() => {
    load().catch((e) => setMessage(String(e.message || e)));
  }, []);

  useEffect(() => {
    if (params.get("checkout") === "success") {
      setMessage("Subscription updated — thank you!");
      load();
    }
  }, [params]);

  useEffect(() => {
    const txn = params.get("_ptxn");
    let cancelled = false;
    apiGet("/api/v1/billing/paddle-config")
      .then((config) => ensurePaddle(config))
      .then(() => {
        if (!cancelled && txn) openCheckout(txn);
      })
      .catch((e) => {
        if (!cancelled) setMessage(String(e.message || e));
      });
    return () => {
      cancelled = true;
    };
  }, [params]);

  async function checkout(plan) {
    setBusy(plan);
    setMessage("");
    try {
      const config = await apiGet("/api/v1/billing/paddle-config");
      await ensurePaddle(config);
      const { url, transaction_id: transactionId } = await apiPost("/api/v1/billing/checkout", { plan });
      if (transactionId && window.Paddle) {
        openCheckout(transactionId);
        return;
      }
      window.location.href = url;
    } catch (e) {
      setMessage(String(e.message || e));
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
  const showStarter = plan === "free";
  const showPro = plan === "free" || plan === "starter";
  const showPortal = plan === "starter" || plan === "pro";

  return (
    <section className="page-section">
      <p className="eyebrow">Billing</p>
      <h1>Plan &amp; usage</h1>
      <p className="lede">Current plan: <strong className="plan-pill">{plan}</strong></p>
      {plan === "free" ? (
        <p className="helper-text">Free trial includes 1 deck upload and 5 bot launches each month. No card required.</p>
      ) : null}
      {plan === "starter" ? (
        <p className="helper-text">Starter includes 3 deck uploads and 5 bot launches each month.</p>
      ) : null}
      {plan === "pro" ? (
        <p className="helper-text">Pro includes 10 deck uploads and 20 bot launches each month.</p>
      ) : null}

      {usage ? (
        <div className="card billing-card">
          <UsageBar label="Bot launches this month" used={usage.launches.used} limit={usage.launches.limit} />
          <UsageBar label="Deck uploads this month" used={usage.uploads.used} limit={usage.uploads.limit} />
        </div>
      ) : null}

      <div className="billing-actions">
        {showStarter ? (
          <button type="button" className="button button-primary" disabled={!!busy} onClick={() => checkout("starter")}>
            {busy === "starter" ? "Opening checkout…" : "Upgrade to Starter — $10/mo"}
          </button>
        ) : null}
        {showPro ? (
          <button type="button" className="button button-secondary" disabled={!!busy} onClick={() => checkout("pro")}>
            {busy === "pro" ? "Opening checkout…" : "Upgrade to Pro — $20/mo"}
          </button>
        ) : null}
        {showPortal ? (
          <button type="button" className="button button-ghost" disabled={!!busy} onClick={portal}>
            Manage subscription
          </button>
        ) : null}
      </div>

      {message ? <p className="banner-note">{message}</p> : null}
    </section>
  );
}
