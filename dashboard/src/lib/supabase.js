import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL || "";
const anon = import.meta.env.VITE_SUPABASE_ANON_KEY || "";

export const supabaseConfigured = Boolean(url && anon);

export const supabase = supabaseConfigured
  ? createClient(url, anon)
  : null;

export function requireSupabase() {
  if (!supabaseConfigured || !supabase) {
    throw new Error("Account service isn’t ready. Refresh the page and try again.");
  }
  return supabase;
}

export async function getAccessToken() {
  if (!supabase) return "";
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token || "";
}
