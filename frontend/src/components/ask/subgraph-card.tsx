"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import type { GraphEdge, GraphNode } from "@/lib/graph-types";

// Same lazy split as the Graph tab: don't parse d3-force until a subgraph
// actually renders.
const KnowledgeGraphView = dynamic(() => import("@/components/graph/knowledge-graph-view"), {
  ssr: false,
  loading: () => <div className="h-[260px] animate-pulse rounded-xl bg-[#0B132B]/20" aria-label="Loading subgraph" />,
});

type Props = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export default function SubgraphCard({ nodes, edges }: Props) {
  if (nodes.length === 0 && edges.length === 0) return null;

  const nodeList = nodes.slice(0, 12);

  return (
    <section className="rounded-2xl border border-[#E8A598]/30 bg-[#0B132B]/15 p-5" aria-labelledby="subgraph-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p id="subgraph-heading" className="text-xs font-semibold uppercase tracking-[0.15em] text-[#F0DCC8]">
            Subgraph for this answer
          </p>
          <p className="mt-1 text-sm text-white">
            {nodes.length} nodes · {edges.length} edges used in graph reasoning
          </p>
        </div>
        <Link
          href="/graph"
          className="shrink-0 rounded-full border border-[#E8A598]/35 bg-white/5 px-4 py-1.5 text-xs font-medium text-white hover:bg-[#E8A598]/15"
        >
          Open full graph
        </Link>
      </div>

      <div className="mt-4">
        <KnowledgeGraphView nodes={nodes} edges={edges} height={260} compact highlightIds={new Set(nodes.map((n) => n.id))} />
      </div>

      {nodeList.length > 0 && (
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {nodeList.map((n) => (
            <li key={n.id} className="rounded-xl border border-[#E8A598]/20 bg-[#0B132B]/10 px-3 py-2 text-xs text-[#EDE6DE]">
              <span className="font-medium text-white">{n.name}</span>
              <span className="text-[#F0DCC8]"> · {n.type}</span>
              {n.page ? <span className="text-[#F0DCC8]"> · p.{n.page}</span> : null}
            </li>
          ))}
        </ul>
      )}

      {edges.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-[#F0DCC8]">
          {edges.slice(0, 6).map((e) => (
            <li key={e.id}>
              {e.source} —<span className="text-white/90"> {e.type.replace(/_/g, " ").toLowerCase()} </span>→{" "}
              {e.target}
            </li>
          ))}
          {edges.length > 6 && <li>+{edges.length - 6} more relationships</li>}
        </ul>
      )}
    </section>
  );
}