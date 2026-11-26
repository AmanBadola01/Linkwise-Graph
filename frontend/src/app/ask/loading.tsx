import { GlassPanel, PageShell } from "@/components/layout/page-shell";

export default function Loading() {
  return (
    <PageShell maxWidth="max-w-3xl">
      <GlassPanel>
        <div className="h-4 w-16 animate-pulse rounded bg-white/15" />
        <div className="mt-4 h-10 w-32 animate-pulse rounded bg-white/15" />
        <div className="mt-6 h-32 animate-pulse rounded-2xl bg-white/10" />
      </GlassPanel>
    </PageShell>
  );
}
