"use client";

import { Icon, type IconName } from "@/components/about/icons";
import type { QueryMode } from "@/lib/rag-session";

type ModeDef = {
  id: QueryMode;
  title: string;
  text: string;
  icon: IconName;
};

const MODES: ModeDef[] = [
  {
    id: "vector",
    title: "Vector",
    text: "Semantic search over text chunks — best for “what does the document say about X?”",
    icon: "search",
  },
  {
    id: "graph",
    title: "Graph",
    text: "Multi-hop reasoning over relationships — best for “how is A connected to B?”",
    icon: "route",
  },
  {
    id: "hybrid",
    title: "Hybrid",
    text: "Combines vector + graph for complex questions that need both text and links.",
    icon: "sparkles",
  },
];

type Props = {
  mode: QueryMode;
  topK: number;
  maxHops: number;
  onMode: (m: QueryMode) => void;
  onTopK: (n: number) => void;
  onMaxHops: (n: number) => void;
};

export default function RetrievalSettings({ mode, topK, maxHops, onMode, onTopK, onMaxHops }: Props) {
  const showTopK = mode === "vector" || mode === "hybrid";
  const showHops = mode === "graph" || mode === "hybrid";

  return (
    <div className="space-y-6">
      <p className="text-sm leading-6 text-[#EDE6DE]">
        Choose how questions are answered. You can change this later on the Ask page.
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        {MODES.map((m) => {
          const active = mode === m.id;
          return (
            <button
              key={m.id}
              type="button"
              onClick={() => onMode(m.id)}
              className={`rounded-2xl border p-4 text-left transition ${
                active
                  ? "border-[#E8A598]/60 bg-[#E8A598]/20 shadow-inner"
                  : "border-[#E8A598]/25 bg-[#0B132B]/10 hover:border-[#E8A598]/45 hover:bg-[#E8A598]/12"
              }`}
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#E8A598]/35 bg-[#E8A598]/12 text-[#FFF4EA]">
                <Icon name={m.icon} className="h-4 w-4" />
              </span>
              <p className="mt-3 text-sm font-semibold text-white">{m.title}</p>
              <p className="mt-1 text-xs leading-5 text-[#F0DCC8]">{m.text}</p>
            </button>
          );
        })}
      </div>

      {showTopK && (
        <label className="block space-y-2">
          <span className="flex justify-between text-sm text-white">
            <span>Chunks to retrieve (top_k)</span>
            <span className="font-mono text-[#F0DCC8]">{topK}</span>
          </span>
          <input
            type="range"
            min={1}
            max={10}
            value={topK}
            onChange={(e) => onTopK(Number(e.target.value))}
            className="w-full accent-white"
          />
        </label>
      )}

      {showHops && (
        <label className="block space-y-2">
          <span className="flex justify-between text-sm text-white">
            <span>Graph hop depth (max_hops)</span>
            <span className="font-mono text-[#F0DCC8]">{maxHops}</span>
          </span>
          <input
            type="range"
            min={1}
            max={5}
            value={maxHops}
            onChange={(e) => onMaxHops(Number(e.target.value))}
            className="w-full accent-white"
          />
        </label>
      )}
    </div>
  );
}