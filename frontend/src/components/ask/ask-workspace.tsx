"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { parseApiError } from "@/lib/api-client";
import { authFetch } from "@/lib/auth-session";
import type { GraphEdge, GraphNode } from "@/lib/graph-types";
import {
  loadRagSession,
  saveRagSession,
  updateRagSession,
  type IngestionSnapshot,
  type QueryMode,
  type RagSession,
} from "@/lib/rag-session";
import SubgraphCard from "@/components/ask/subgraph-card";
import RetrievalSettings from "@/components/upload/retrieval-settings";

type MatchedChunk = {
  chunk_id: string;
  document_name: string;
  page_number: number;
  section_title: string;
  content: string;
  score: number;
};

type QueryResponse = {
  query: string;
  mode: QueryMode;
  answer: string;
  reasoning_chain: string[];
  subgraph_nodes: GraphNode[];
  subgraph_edges: GraphEdge[];
  matched_chunks: MatchedChunk[];
  source_pages: number[];
};

export default function AskWorkspace() {
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") ?? "";

  const [mode, setMode] = useState<QueryMode>("hybrid");
  const [topK, setTopK] = useState(3);
  const [maxHops, setMaxHops] = useState(3);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [ingestion, setIngestion] = useState<IngestionSnapshot | undefined>();

  const executeQuery = useCallback(async (trimmed: string, session: RagSession) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await authFetch("/api/v1/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: trimmed,
          mode: session.mode,
          top_k: session.top_k,
          max_hops: session.max_hops,
        }),
      });
      if (!res.ok) throw new Error(await parseApiError(res));
      const data = (await res.json()) as QueryResponse;
      setResult(data);
      if (data.subgraph_nodes.length > 0 || data.subgraph_edges.length > 0) {
        updateRagSession({
          lastSubgraph: {
            query: trimmed,
            nodes: data.subgraph_nodes,
            edges: data.subgraph_edges,
            savedAt: Date.now(),
          },
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const session = loadRagSession();
    setMode(session.mode);
    setTopK(session.top_k);
    setMaxHops(session.max_hops);
    setIngestion(session.ingestion);
    setQuery(initialQ);
    const trimmed = initialQ.trim();
    if (trimmed) void executeQuery(trimmed, session);
  }, [initialQ, executeQuery]);

  const runQuery = async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) {
      setError("Enter a question first.");
      return;
    }
    const session: RagSession = {
      ...loadRagSession(),
      mode,
      top_k: topK,
      max_hops: maxHops,
    };
    saveRagSession(session);
    await executeQuery(trimmed, session);
  };

  return (
    <div className="flex flex-col gap-6">
      {ingestion && (
        <div className="rounded-2xl border border-[#E8A598]/25 bg-[#0B132B]/12 px-4 py-3 text-sm text-[#EDE6DE]">
          Last ingest: <span className="font-medium text-white">{ingestion.filename}</span>
          <span className="text-[#F0DCC8]">
            {" "}
            · {ingestion.nodes_created} nodes · {ingestion.chunks_indexed} chunks
          </span>
        </div>
      )}

      <button
        type="button"
        onClick={() => setShowSettings((v) => !v)}
        className="flex w-full items-center justify-between rounded-2xl border border-white/20 bg-white/5 px-4 py-3 text-left text-sm font-medium text-white"
      >
        Retrieval settings
        <span className="text-xs capitalize text-[#F0DCC8]">
          {mode}
          {mode !== "graph" ? ` · top_k ${topK}` : ""}
          {mode !== "vector" ? ` · hops ${maxHops}` : ""}
        </span>
      </button>

      {showSettings && (
        <RetrievalSettings
          mode={mode}
          topK={topK}
          maxHops={maxHops}
          onMode={setMode}
          onTopK={setTopK}
          onMaxHops={setMaxHops}
        />
      )}

      <label className="block space-y-2">
        <span className="text-sm font-medium text-white">Question</span>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          className="w-full resize-y rounded-2xl border border-[#E8A598]/30 bg-[#0B132B]/15 px-4 py-3 text-sm text-white placeholder:text-[#F0DCC8] focus:border-[#E8A598]/55 focus:outline-none"
          placeholder="Ask anything about your uploaded document…"
        />
      </label>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => runQuery(query)}
          disabled={loading || !query.trim()}
          className="inline-flex items-center justify-center rounded-full border border-[#FFF4EA]/55 bg-[#FFF8F2] px-6 py-2.5 text-sm font-semibold text-[#1E2A35] shadow-sm transition hover:bg-[#F0E4D8] disabled:cursor-not-allowed disabled:border-[#FFF4EA]/30 disabled:bg-[#FFF8F2]/50 disabled:text-[#1E2A35]/55"
        >
          {loading ? "Thinking…" : "Ask"}
        </button>
        <Link
          href="/upload"
          className="inline-flex items-center justify-center rounded-full border border-[#E8A598]/35 bg-white/5 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-md transition hover:bg-[#E8A598]/15"
        >
          Upload another PDF
        </Link>
        <Link
          href="/graph"
          className="inline-flex items-center justify-center rounded-full border border-[#E8A598]/35 bg-white/5 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-md transition hover:bg-[#E8A598]/15"
        >
          View graph
        </Link>
      </div>

      {loading && (
        <div className="h-2 overflow-hidden rounded-full bg-white/15">
          <div className="h-full w-2/5 animate-pulse rounded-full bg-gradient-to-r from-[#E8A598] to-[#FFF8F2]" />
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-2xl border border-red-300/40 bg-red-950/30 px-4 py-3 text-sm text-red-100">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-4 rounded-2xl border border-[#E8A598]/30 bg-[#0B132B]/15 p-6">
          <p className="text-xs uppercase tracking-[0.15em] text-[#F0DCC8]">
            Answer · {result.mode} mode
          </p>
          <p className="whitespace-pre-wrap text-sm leading-7 text-white">{result.answer}</p>

          {result.source_pages.length > 0 && (
            <p className="text-xs text-[#F0DCC8]">
              Sources: pages {result.source_pages.join(", ")}
            </p>
          )}

          {result.reasoning_chain.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#F0DCC8]">Reasoning chain</p>
              <ul className="space-y-2 text-sm text-[#EDE6DE]">
                {result.reasoning_chain.map((step, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-[#F0DCC8]">{i + 1}.</span>
                    {step}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <SubgraphCard nodes={result.subgraph_nodes} edges={result.subgraph_edges} />

          {result.matched_chunks.length > 0 && (
            <details className="text-sm text-[#EDE6DE]">
              <summary className="cursor-pointer font-medium text-white">
                Matched chunks ({result.matched_chunks.length})
              </summary>
              <ul className="mt-3 space-y-3">
                {result.matched_chunks.map((c) => (
                  <li key={c.chunk_id} className="rounded-xl border border-white/15 bg-white/5 p-3">
                    <p className="text-xs text-[#F0DCC8]">
                      Page {c.page_number} · score {c.score.toFixed(3)}
                    </p>
                    <p className="mt-1 line-clamp-4 text-sm">{c.content}</p>
                  </li>
                ))}
              </ul>
            </details>
          )}

        </div>
      )}
    </div>
  );
}