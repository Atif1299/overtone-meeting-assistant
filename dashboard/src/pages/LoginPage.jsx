import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { requireSupabase } from "../lib/supabase.js";
import AuthLayout from "../components/AuthLayout.jsx";

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const client = requireSupabase();
      const { error: err } = await client.auth.signInWithPassword({ email, password });
      if (err) throw err;
      navigate("/app");
    } catch (err) {
      setError(err.message || "Sign in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <div className="auth-card">
        <h1>Sign in to Overtone</h1>
        <p className="auth-sub">Upload decks, launch bots, and present live in meetings.</p>
        <form onSubmit={onSubmit} className="auth-form">
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {error ? <p className="auth-error">{error}</p> : null}
          <button type="submit" className="button button-primary auth-submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="auth-foot">
          No account? <Link to="/signup">Start free trial</Link>
        </p>
      </div>
    </AuthLayout>
  );
}
