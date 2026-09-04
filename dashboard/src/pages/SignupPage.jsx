import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { requireSupabase } from "../lib/supabase.js";
import AuthLayout from "../components/AuthLayout.jsx";

export default function SignupPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
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
      const { data, error: err } = await client.auth.signUp({
        email,
        password,
        options: { data: { full_name: name } },
      });
      if (err) throw err;
      if (!data.session) {
        const { data: signedIn, error: signInErr } = await client.auth.signInWithPassword({
          email,
          password,
        });
        if (signInErr || !signedIn.session) {
          setNotice("Account created. Check your email to confirm, then sign in.");
          return;
        }
      }
      navigate("/app");
    } catch (err) {
      setError(err.message || "Sign up failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <div className="auth-card">
        <h1>Start your free trial</h1>
        <p className="auth-sub">1 deck upload and 1 bot launch included — no credit card required.</p>
        <form onSubmit={onSubmit} className="auth-form">
          <label>
            Name
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} />
          </label>
          {error ? <p className="auth-error">{error}</p> : null}
          {notice ? <p className="auth-notice">{notice}</p> : null}
          <button type="submit" className="button button-primary auth-submit" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>
        <p className="auth-foot">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </AuthLayout>
  );
}
