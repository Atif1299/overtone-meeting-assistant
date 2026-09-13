import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { requireSupabase } from "../lib/supabase.js";
import AuthLayout from "../components/AuthLayout.jsx";

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const client = requireSupabase();
      const { data } = await client.auth.getSession();
      if (!data.session) {
        throw new Error("That reset link expired. Request a new one.");
      }
      const { error: err } = await client.auth.updateUser({ password });
      if (err) throw err;
      navigate("/app", { replace: true });
    } catch (err) {
      setError(err.message || "Could not update password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <div className="auth-card">
        <h1>Choose a new password</h1>
        <p className="auth-sub">Then you’ll enter your free-trial dashboard.</p>
        <form onSubmit={onSubmit} className="auth-form">
          <label>
            New password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
          </label>
          {error ? <p className="auth-error">{error}</p> : null}
          <button type="submit" className="button button-primary auth-submit" disabled={busy}>
            {busy ? "Saving…" : "Save password"}
          </button>
        </form>
        <p className="auth-foot">
          <Link to="/forgot-password">Request a new link</Link>
        </p>
      </div>
    </AuthLayout>
  );
}
