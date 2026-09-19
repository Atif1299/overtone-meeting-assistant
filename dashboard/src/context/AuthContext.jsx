import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { supabase, supabaseConfigured } from "../lib/supabase.js";
import { clearActivity, isAuthSessionExpired, markActivity } from "../lib/sessionExpiry.js";
import { apiGet, apiPost, setAuthTokenProvider } from "../utils/api.js";

const AuthContext = createContext(null);

async function expireSession() {
  clearActivity();
  if (supabase) {
    await supabase.auth.signOut();
  }
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setAuthTokenProvider(async () => {
      if (!supabase) return "";
      const { data } = await supabase.auth.getSession();
      const next = data.session;
      if (next && isAuthSessionExpired(next)) {
        await expireSession();
        return "";
      }
      return next?.access_token || "";
    });
  }, []);

  useEffect(() => {
    if (!supabaseConfigured || !supabase) {
      setLoading(false);
      return undefined;
    }

    supabase.auth.getSession().then(async ({ data }) => {
      const next = data.session;
      if (next && isAuthSessionExpired(next)) {
        await expireSession();
        setSession(null);
      } else {
        if (next) markActivity();
        setSession(next);
      }
      setLoading(false);
    });

    const { data: sub } = supabase.auth.onAuthStateChange((event, next) => {
      if (next && isAuthSessionExpired(next)) {
        expireSession().then(() => setSession(null));
        return;
      }
      if (event === "SIGNED_IN" || event === "TOKEN_REFRESHED" || event === "INITIAL_SESSION") {
        if (next) markActivity();
      }
      if (event === "SIGNED_OUT") {
        clearActivity();
      }
      setSession(next);
      if (event === "PASSWORD_RECOVERY" && window.location.pathname !== "/reset-password") {
        window.location.replace("/reset-password");
      }
    });

    return () => sub.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    function onUnauthorized() {
      expireSession().then(() => setSession(null));
    }
    window.addEventListener("deckvoice:unauthorized", onUnauthorized);
    return () => window.removeEventListener("deckvoice:unauthorized", onUnauthorized);
  }, []);

  useEffect(() => {
    function onVisible() {
      if (document.visibilityState !== "visible") return;
      if (session && isAuthSessionExpired(session)) {
        expireSession().then(() => setSession(null));
        return;
      }
      if (session) markActivity();
    }
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, [session]);

  useEffect(() => {
    if (!session?.access_token) {
      setProfile(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        await apiPost("/api/v1/auth/bootstrap", {});
        const me = await apiGet("/api/v1/me");
        if (!cancelled) setProfile(me);
      } catch (error) {
        if (error?.status === 401) {
          await expireSession();
          if (!cancelled) setSession(null);
        }
        if (!cancelled) setProfile(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [session]);

  async function refreshProfile() {
    if (!session?.access_token) return;
    const me = await apiGet("/api/v1/me");
    setProfile(me);
  }

  const value = useMemo(
    () => ({
      session,
      profile,
      loading,
      supabaseConfigured,
      refreshProfile,
      signOut: async () => {
        await expireSession();
      },
    }),
    [session, profile, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
