import type { Metadata } from "next";
import { Suspense } from "react";
import AccountForm from "@/components/auth/account-form";

export const metadata: Metadata = {
  title: "Account · Linkwise-Graph",
};

export default function AccountPage() {
  return (
    <Suspense fallback={<p className="pt-28 text-center text-[#F0DCC8]">Loading…</p>}>
      <AccountForm />
    </Suspense>
  );
}
