"use client";

import { useState, type FormEvent } from "react";
import { AuthField } from "@/components/auth/auth-field";
import { AuthShell } from "@/components/auth/auth-shell";
import { parseApiError } from "@/lib/api-client";
import { authFetch, loadAuthUser } from "@/lib/auth-session";
import { tw } from "@/components/layout/linkwise-theme";

export default function AccountForm() {
  const user = loadAuthUser();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setDone(false);
    setLoading(true);
    try {
      const res = await authFetch("/api/v1/auth/change-password", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      if (!res.ok) throw new Error(await parseApiError(res));
      setDone(true);
      setCurrent("");
      setNext("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password change failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Account"
      title="Change password"
      subtitle={
        user
          ? `Signed in as ${user.email}. Changing your password signs out every other session.`
          : "Change your password. This signs out every other session."
      }
      footer={<span className={tw.muted}>Sessions last 12 hours and can be revoked anytime by logging out.</span>}
    >
      <form className="flex flex-col gap-5" onSubmit={(e) => void onSubmit(e)}>
        <AuthField
          label="Current password"
          name="current_password"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
        <AuthField
          label="New password"
          name="new_password"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          required
          hint="At least 8 characters, at most 72 bytes."
        />
        {error && (
          <p role="alert" className="rounded-xl border border-red-300/40 bg-red-950/30 px-4 py-3 text-sm text-red-100">
            {error}
          </p>
        )}
        {done && (
          <p role="status" className="rounded-xl border border-emerald-300/40 bg-emerald-950/30 px-4 py-3 text-sm text-emerald-100">
            Password changed. Other sessions have been signed out.
          </p>
        )}
        <button type="submit" disabled={loading} className={tw.btnSolid}>
          {loading ? "Saving…" : "Change password"}
        </button>
      </form>
    </AuthShell>
  );
}
