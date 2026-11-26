import { Suspense } from "react";
import { GlassPanel, HEADING_STYLE, PageShell } from "@/components/layout/page-shell";
import AskWorkspace from "@/components/ask/ask-workspace";

export default function AskPage() {
  return (
    <PageShell maxWidth="max-w-3xl">
      <GlassPanel>
        <p className="text-xs uppercase tracking-[0.2em] text-[#F0DCC8]" style={{ fontFamily: "var(--outfit)" }}>
          Query
        </p>
        <h1 className="mt-3 text-4xl uppercase leading-tight md:text-5xl" style={HEADING_STYLE}>
          Ask
        </h1>
        <p className="mt-4 text-sm leading-6 text-[#EDE6DE]">
          Questions use the retrieval mode you chose on Upload. Answers include citations and optional graph context.
        </p>
        <div className="mt-8">
          <Suspense fallback={<p className="text-sm text-[#F0DCC8]">Loading…</p>}>
            <AskWorkspace />
          </Suspense>
        </div>
      </GlassPanel>
    </PageShell>
  );
}