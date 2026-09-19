const ACTIVITY_KEY = "deckvoice:last-activity:v1";

export const SESSION_TTL_MS = 24 * 60 * 60 * 1000;

export function markActivity() {
  try {
    localStorage.setItem(ACTIVITY_KEY, String(Date.now()));
  } catch {
    // private mode / storage blocked
  }
}

export function clearActivity() {
  try {
    localStorage.removeItem(ACTIVITY_KEY);
  } catch {
    // ignore
  }
}

export function isAuthSessionExpired(session) {
  if (!session) return true;

  const lastSignIn = Date.parse(session.user?.last_sign_in_at || "");
  if (Number.isFinite(lastSignIn) && Date.now() - lastSignIn > SESSION_TTL_MS) {
    return true;
  }

  try {
    const activity = Number(localStorage.getItem(ACTIVITY_KEY) || 0);
    if (activity && Date.now() - activity > SESSION_TTL_MS) {
      return true;
    }
  } catch {
    // ignore storage errors
  }

  return false;
}
