import { clearLegacyRagSession, clearRagSessionForCurrentUser } from "@/lib/rag-session";

export type AuthUser = {
  id: string;
  email: string;
  display_name: string;
};

// Only the public profile is kept in localStorage. The session itself lives
// in the HttpOnly `lw_session` cookie set by the backend, which JavaScript
// cannot read (BUG-06). Previously the raw JWT was stored in localStorage
// AND a JS-readable cookie for 14 days.
const USER_KEY = "linkwise_user";
const LEGACY_TOKEN_KEY = "linkwise_access_token";

export function loadAuthUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function saveAuthSession(user: AuthUser): void {
  const previous = loadAuthUser();
  if (previous && previous.id !== user.id) {
    localStorage.removeItem(`linkwise-rag-session:${previous.id}`);
  }
  clearLegacyRagSession();
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuthSession(): void {
  clearRagSessionForCurrentUser();
  clearLegacyRagSession();
  localStorage.removeItem(LEGACY_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  // Clear old JS-readable cookies if any linger. The real HttpOnly session
  // cookie is cleared by the backend (it deletes it on every 401/logout).
  document.cookie = "lw_token=; path=/; max-age=0";
  document.cookie = "lw_session=; path=/; max-age=0";
}

function handleUnauthorized(res: Response): void {
  // Expired/revoked session: clear local state and go to login instead of
  // trapping the user on a page with a raw error (BUG-09).
  if (res.status !== 401 || typeof window === "undefined") return;
  const path = window.location.pathname;
  if (path === "/login" || path === "/signup") return;
  clearAuthSession();
  const next = encodeURIComponent(path + window.location.search);
  window.location.assign(`/login?next=${next}&reason=session-expired`);
}

export async function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const res = await fetch(input, { ...init, credentials: "include" });
  handleUnauthorized(res);
  return res;
}
