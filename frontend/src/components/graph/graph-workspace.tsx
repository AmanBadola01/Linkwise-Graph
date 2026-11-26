"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { parseApiError } from "@/lib/api-client";
import { authFetch } from "@/lib/auth-session";
import type { GraphDataResponse } from "@/lib/graph-types";

// Lazy-load the d3-force canvas view so its JS isn't parsed on every tab
// switch; it only loads when the Graph tab (and its data) is actually shown.
const Neo4jGraphView = dynamic(() => import("@/components/graph/neo4j-graph-view"), {
  ssr: false,
  loading: () => <div className="h-[560px] animate-pulse rounded-2xl bg-[#0B132B]/20" aria-label="Loading graph view" />,
});

export default function GraphWorkspace() {
  const [data, setData] = useState<GraphDataResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [viewKey, setViewKey] = useState(0);

  const loadGraph = useCallback(async (opts?: { soft?: boolean }) => {
    const soft = opts?.soft ?? false;
    if (soft) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const res = await authFetch("/api/v1/graph", { cache: "no-store" });
      if (!res.ok) throw new Error(await parseApiError(res));
      const json = (await res.json()) as GraphDataResponse;
      setData(json);
      setViewKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load graph.");
    } finally {
      if (soft) setRefreshing(false);
      else setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  const typeEntries = useMemo(
    () => (data ? Object.entries(data.entity_types).sort((a, b) => b[1] - a[1]) : []),
    [data],
  );

  const refreshBusy = loading || refreshing;

  return (
    <div className="flex flex-col gap-6">
      {loading && (
        <div className="h-2 overflow-hidden rounded-full bg-[#0B132B]/25">
          <div className="h-full w-1/3 animate-pulse rounded-full bg-gradient-to-r from-[#E8A598] to-[#FFF8F2]" />
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-2xl border border-red-300/40 bg-red-950/30 px-4 py-3 text-sm text-red-100">
          {error}
        </div>
      )}

      {data && (
        <>
          <div className="flex flex-wrap items-center gap-2 text-sm text-[#EDE6DE]">
            <span className="rounded-full border border-[#E8A598]/35 bg-[#E8A598]/12 px-3 py-1">
              {data.total_nodes} nodes
            </span>
            <span className="rounded-full border border-[#E8A598]/35 bg-[#E8A598]/12 px-3 py-1">
              {data.total_edges} edges
            </span>
            <button
              type="button"
              onClick={() => void loadGraph({ soft: true })}
              disabled={refreshBusy}
              className="ml-auto inline-flex items-center justify-center rounded-full border border-[#E8A598]/55 bg-[#E8A598]/25 px-5 py-2 text-sm font-medium text-[#FFF8F2] backdrop-blur-md transition hover:bg-[#E8A598]/35 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {refreshing ? "Refreshing…" : "Refresh graph"}
            </button>
          </div>

          {typeEntries.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {typeEntries.map(([type, count]) => (
                <li
                  key={type}
                  className="rounded-full border border-[#E8A598]/25 bg-[#0B132B]/10 px-3 py-1 text-xs text-[#F0DCC8]"
                >
                  {type} · {count}
                </li>
              ))}
            </ul>
          )}

          <Neo4jGraphView key={viewKey} nodes={data.nodes} edges={data.edges} height={560} />

          {!compactEmpty(data) && (
            <p className="text-xs text-[#F0DCC8]">
              Force-directed graph (Neo4j-style): drag nodes, pan the canvas, zoom with scroll or the toolbar. Use{" "}
              <strong className="font-medium text-[#EDE6DE]">Refresh graph</strong> after Ask to reload the full graph from
              the server.
            </p>
          )}
        </>
      )}

      <div className="flex flex-wrap gap-3">
        <Link
          href="/upload"
          className="inline-flex items-center justify-center rounded-full border border-[#E8A598]/35 bg-white/5 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-md transition hover:bg-[#E8A598]/15"
        >
          Upload
        </Link>
        <Link
          href="/ask"
          className="inline-flex items-center justify-center rounded-full border border-[#FFF4EA]/55 bg-[#FFF8F2] px-6 py-2.5 text-sm font-semibold text-[#1E2A35] shadow-sm transition hover:bg-[#F0E4D8]"
        >
          Ask a question
        </Link>
      </div>
    </div>
  );
}

function compactEmpty(data: GraphDataResponse): boolean {
  return data.total_nodes === 0;
}