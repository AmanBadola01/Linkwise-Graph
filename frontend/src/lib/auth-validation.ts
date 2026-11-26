/** Client-side auth input normalization and validation (mirrors backend rules). */

const EMAIL_MAX = 254;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function normalizeEmail(raw: string): string {
  return raw.trim().toLowerCase();
}

export function isValidEmail(raw: string): boolean {
  const email = normalizeEmail(raw);
  if (!email || email.length > EMAIL_MAX) return false;
  if (email.includes(" ") || email.includes("..")) return false;
  return EMAIL_RE.test(email);
}

export function validateLoginPassword(password: string): string | null {
  if (!password || !password.trim()) return "Password is required";
  if (password.length < 8) return "Password must be at least 8 characters";
  if (password.length > 128) return "Password is too long";
  return null;
}

export function validateSignupPassword(password: string): string | null {
  return validateLoginPassword(password);
}

export function normalizeDisplayName(raw: string): string {
  return raw.trim().replace(/\s+/g, " ");
}

export function validateDisplayName(raw: string): string | null {
  const name = normalizeDisplayName(raw);
  if (!name) return "Display name is required";
  if (name.length > 80) return "Display name is too long";
  return null;
}

/** Safe in-app redirect target only. */
export function safeNextPath(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return "/";
  if (next.startsWith("/login") || next.startsWith("/signup")) return "/";
  return next;
}