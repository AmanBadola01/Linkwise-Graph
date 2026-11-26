import { PageShell } from "@/components/layout/page-shell";

export default function Loading() {
  return (
    <PageShell maxWidth="max-w-3xl">
      <div className="h-4 w-24 animate-pulse rounded bg-white/15" />
      <div className="mt-4 h-10 w-72 animate-pulse rounded bg-white/15" />
      <div className="mt-6 h-56 animate-pulse rounded-3xl bg-white/10" />
    </PageShell>
  );
}
