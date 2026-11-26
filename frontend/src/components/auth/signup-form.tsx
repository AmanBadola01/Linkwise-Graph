"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { AuthShell } from "@/components/auth/auth-shell";
import { AuthField } from "@/components/auth/auth-field";
import { parseApiError } from "@/lib/api-client";
import {
  isValidEmail,
  normalizeDisplayName,
  normalizeEmail,
  validateDisplayName,
  validateSignupPassword,
} from "@/lib/auth-validation";
import { saveAuthSession, type AuthUser } from "@/lib/auth-session";
import { tw } from "@/components/layout/linkwise-theme";

export default function SignupForm() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{
    displayName?: string;
    email?: string;
    password?: string;
  }>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function validateFields(): boolean {
    const displayErr = validateDisplayName(displayName) ?? undefined;
    const emailErr = !isValidEmail(normalizeEmail(email)) ? "Enter a valid email address" : undefined;
    const passwordErr = validateSignupPassword(password) ?? undefined;
    setFieldErrors({ displayName: displayErr, email: emailErr, password: passwordErr });
    return !displayErr && !emailErr && !passwordErr;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!validateFields()) return;

    const payload = {
      email: normalizeEmail(email),
      password,
      display_name: normalizeDisplayName(displayName),
    };
    setLoading(true);
    try {
      const res = await fetch("/api/v1/auth/signup", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await parseApiError(res));
      const data = (await res.json()) as { user: AuthUser };
      saveAuthSession(data.user);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Account"
      title="Sign up"
      subtitle="Create your workspace. Uploaded PDFs, graphs, and answers stay tied to this account only."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-[#FFF8F2] underline-offset-2 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
        {error && (
          <div role="alert" className="rounded-2xl border border-red-300/40 bg-red-950/30 px-4 py-3 text-sm text-red-100">
            {error}
          </div>
        )}
        <AuthField
          name="displayName"
          label="Display name"
          type="text"
          required
          autoComplete="name"
          maxLength={80}
          value={displayName}
          error={fieldErrors.displayName}
          onChange={(e) => {
            setDisplayName(e.target.value);
            if (fieldErrors.displayName) setFieldErrors((f) => ({ ...f, displayName: undefined }));
          }}
          onBlur={() => setDisplayName((v) => normalizeDisplayName(v))}
        />
        <AuthField
          name="email"
          label="Email"
          type="email"
          required
          autoComplete="email"
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
          autoComplete="new-password"
          minLength={8}
          maxLength={128}
          value={password}
          hint="At least 8 characters. Spaces are allowed and treated as part of your password."
          error={fieldErrors.password}
          onChange={(e) => {
            setPassword(e.target.value);
            if (fieldErrors.password) setFieldErrors((f) => ({ ...f, password: undefined }));
          }}
        />
        <button type="submit" disabled={loading} className={`mt-2 ${tw.btnPrimary}`}>
          {loading ? "Creating account…" : "Create account"}
        </button>
      </form>
    </AuthShell>
  );
}