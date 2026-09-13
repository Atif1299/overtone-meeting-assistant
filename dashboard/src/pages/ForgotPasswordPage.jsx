import { useState } from "react";
import { Link } from "react-router-dom";
import { requireSupabase } from "../lib/supabase.js";
import { authRedirectTo } from "../lib/authRedirect.js";
import AuthLayout from "../components/AuthLayout.jsx";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const client = requireSupabase();
      const { error: err } = await client.auth.resetPasswordForEmail(email, {
        redirectTo: authRedirectTo(),
      });
      if (err) throw err;
      setNotice("If that email has an account, we sent a reset link. Check your inbox.");
    } catch (err) {
      setError(err.message || "Could not send reset email");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <div className="auth-card">
        <h1>Reset your password</h1>
        <p className="auth-sub">We’ll email you a link to choose a new password.</p>
        <form onSubmit={onSubmit} className="auth-form">
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          {error ? <p className="auth-error">{error}</p> : null}
          {notice ? <p className="auth-notice">{notice}</p> : null}
          <button type="submit" className="button button-primary auth-submit" disabled={busy}>
            {busy ? "Sending…" : "Send reset link"}
          </button>
        </form>
        <p className="auth-foot">
          <Link to="/login">Back to sign in</Link>
        </p>
      </div>
    </AuthLayout>
  );
}
