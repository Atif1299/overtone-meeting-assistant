import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { supabase, supabaseConfigured } from "../lib/supabase.js";
import { apiGet, apiPost, setAuthTokenProvider } from "../utils/api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setAuthTokenProvider(async () => {
      if (!supabase) return "";
      const { data } = await supabase.auth.getSession();
      return data.session?.access_token || "";
    });
  }, []);

  useEffect(() => {
    if (!supabaseConfigured || !supabase) {
      setLoading(false);
      return undefined;
    }

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const { data: sub } = supabase.auth.onAuthStateChange((event, next) => {
      setSession(next);
      if (event === "PASSWORD_RECOVERY" && window.location.pathname !== "/reset-password") {
        window.location.replace("/reset-password");
      }
    });

    return () => sub.subscription.unsubscribe();
  }, []);

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
      } catch {
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
        if (supabase) await supabase.auth.signOut();
      },
    }),
    [session, profile, loading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
