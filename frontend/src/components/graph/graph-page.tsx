import { Suspense } from "react";
import { GlassPanel, HEADING_STYLE, PageShell } from "@/components/layout/page-shell";
import GraphWorkspace from "@/components/graph/graph-workspace";

export default function GraphPage() {
  return (
    <PageShell maxWidth="max-w-4xl">
      <GlassPanel>
        <p className="text-xs uppercase tracking-[0.2em] text-[#F0DCC8]" style={{ fontFamily: "var(--outfit)" }}>
          Knowledge graph
        </p>
        <h1 className="mt-3 text-4xl uppercase leading-tight md:text-5xl" style={HEADING_STYLE}>
          Graph
        </h1>
        <p className="mt-4 text-sm leading-6 text-[#EDE6DE]">
          Interactive Neo4j-style graph of entities and relationships from your ingested documents. Use Refresh graph to
          reload the full graph from the server after visiting from Ask.
        </p>
        <div className="mt-8">
          <Suspense fallback={<p className="text-sm text-[#F0DCC8]">Loading graph…</p>}>
            <GraphWorkspace />
          </Suspense>
        </div>
      </GlassPanel>
    </PageShell>
  );
}