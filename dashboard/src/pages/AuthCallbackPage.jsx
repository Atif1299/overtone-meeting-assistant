import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { requireSupabase } from "../lib/supabase.js";
import AuthLayout from "../components/AuthLayout.jsx";

export default function AuthCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function complete() {
      try {
        const client = requireSupabase();
        const params = new URLSearchParams(window.location.search);
        const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
        const code = params.get("code");
        let recovery = (params.get("type") || hash.get("type") || "") === "recovery";
        const { data: listener } = client.auth.onAuthStateChange((event) => {
          if (event === "PASSWORD_RECOVERY") recovery = true;
        });

        if (code) {
          const { error: exchangeError } = await client.auth.exchangeCodeForSession(window.location.href);
          if (exchangeError) throw exchangeError;
        }

        const { data } = await client.auth.getSession();
        listener.subscription.unsubscribe();
        if (!data.session) {
          throw new Error("Could not complete sign-in from that email link. Try signing in.");
        }

        if (!cancelled) {
          navigate(recovery ? "/reset-password" : "/app", { replace: true });
        }
      } catch (err) {
        if (!cancelled) setError(err.message || "Email link failed");
      }
    }

    complete();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  return (
    <AuthLayout>
      <div className="auth-card">
        <h1>Signing you in</h1>
        <p className="auth-sub">Finishing the email link…</p>
        {error ? (
          <>
            <p className="auth-error">{error}</p>
            <p className="auth-foot">
              <a href="/login">Back to sign in</a>
            </p>
          </>
        ) : null}
      </div>
    </AuthLayout>
  );
}
