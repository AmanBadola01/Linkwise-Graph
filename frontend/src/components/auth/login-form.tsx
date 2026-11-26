"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useMemo, useState } from "react";
import { AuthShell } from "@/components/auth/auth-shell";
import { AuthField } from "@/components/auth/auth-field";
import { parseApiError } from "@/lib/api-client";
import {
  isValidEmail,
  normalizeEmail,
  safeNextPath,
  validateLoginPassword,
} from "@/lib/auth-validation";
import { saveAuthSession, type AuthUser } from "@/lib/auth-session";
import { tw } from "@/components/layout/linkwise-theme";

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = useMemo(() => safeNextPath(searchParams.get("next")), [searchParams]);
  const sessionExpired = searchParams.get("reason") === "session-expired";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function validateFields(): boolean {
    const normalized = normalizeEmail(email);
    const emailErr = !isValidEmail(normalized) ? "Enter a valid email address" : undefined;
    const passwordErr = validateLoginPassword(password) ?? undefined;
    setFieldErrors({ email: emailErr, password: passwordErr });
    return !emailErr && !passwordErr;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!validateFields()) return;

    const payload = { email: normalizeEmail(email), password };
    setLoading(true);
    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await parseApiError(res));
      const data = (await res.json()) as { user: AuthUser };
      saveAuthSession(data.user);
      router.replace(nextPath);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Account"
      title="Sign in"
      subtitle="Access your private graph and documents. Each account only sees its own data."
      footer={
        <>
          New here?{" "}
          <Link href="/signup" className="font-medium text-[#FFF8F2] underline-offset-2 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
        {sessionExpired && !error && (
          <div role="status" className="rounded-2xl border border-[#E8A598]/40 bg-[#E8A598]/15 px-4 py-3 text-sm text-[#FFF4EA]">
            Your session expired. Please sign in again.
          </div>
        )}
        {error && (
          <div role="alert" className="rounded-2xl border border-red-300/40 bg-red-950/30 px-4 py-3 text-sm text-red-100">
            {error}
          </div>
        )}
        <AuthField
          name="email"
          label="Email"
          type="email"
          required
          autoComplete="username"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          inputMode="email"
          maxLength={254}
          value={email}
          hint="Not case-sensitive — we store your email in lowercase."
          error={fieldErrors.email}
          onChange={(e) => {
            setEmail(e.target.value);
            if (fieldErrors.email) setFieldErrors((f) => ({ ...f, email: undefined }));
          }}
          onBlur={() => setEmail((v) => normalizeEmail(v))}
        />
        <AuthField
          name="password"
          label="Password"
          type="password"
          required
          autoComplete="current-password"
          maxLength={128}
          value={password}
          error={fieldErrors.password}
          onChange={(e) => {
            setPassword(e.target.value);
            if (fieldErrors.password) setFieldErrors((f) => ({ ...f, password: undefined }));
          }}
        />
        <button type="submit" disabled={loading} className={`mt-2 ${tw.btnPrimary}`}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </AuthShell>
  );
}