"use client";

import { useEffect } from "react";
import { GlassPanel, HEADING_STYLE, PageShell } from "@/components/layout/page-shell";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <PageShell maxWidth="max-w-2xl">
      <GlassPanel>
        <p className="text-xs uppercase tracking-[0.2em] text-[#F0DCC8]" style={{ fontFamily: "var(--outfit)" }}>
          Something went wrong
        </p>
        <h1 className="mt-3 text-4xl uppercase leading-tight md:text-5xl" style={HEADING_STYLE}>
          This page failed to load
        </h1>
        <p className="mt-4 text-sm leading-6 text-[#EDE6DE]">
          An unexpected error stopped this page from rendering. Your documents and graph are unaffected — try again.
        </p>
        <div className="mt-8">
          <button
            type="button"
            onClick={reset}
            className="inline-flex items-center justify-center rounded-full border border-[#FFF4EA]/55 bg-[#FFF8F2] px-6 py-2.5 text-sm font-semibold text-[#1E2A35] shadow-sm transition hover:bg-[#F0E4D8]"
          >
            Try again
          </button>
        </div>
      </GlassPanel>
    </PageShell>
  );
}
