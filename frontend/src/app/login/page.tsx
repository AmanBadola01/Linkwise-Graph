import type { Metadata } from "next";
import { Suspense } from "react";
import LoginForm from "@/components/auth/login-form";

export const metadata: Metadata = {
  title: "Sign in · Linkwise-Graph",
};

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="pt-28 text-center text-[#F0DCC8]">Loading…</p>}>
      <LoginForm />
    </Suspense>
  );
}