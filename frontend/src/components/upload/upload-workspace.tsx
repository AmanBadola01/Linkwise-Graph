"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { Icon } from "@/components/about/icons";
import { parseApiError } from "@/lib/api-client";
import { authFetch } from "@/lib/auth-session";
import {
  loadRagSession,
  saveRagSession,
  type IngestionSnapshot,
  type QueryMode,
  type RagSession,
} from "@/lib/rag-session";
import RetrievalSettings from "@/components/upload/retrieval-settings";

type IngestionResult = IngestionSnapshot & {
  status: string;
  message: string;
};

type UploadPhase = "idle" | "uploading" | "success" | "error";
type WizardStep = 1 | 2 | 3;

const ACCEPT = ".pdf,application/pdf";
const MAX_MB = 50;

const WIZARD_LABELS = ["Upload PDF", "Retrieval method", "Your first question"] as const;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isPdf(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".pdf") || file.type === "application/pdf";
}

function StepIndicator({ step }: { step: WizardStep }) {
  return (
    <ol className="flex flex-wrap gap-2">
      {WIZARD_LABELS.map((label, i) => {
        const n = (i + 1) as WizardStep;
        const active = step === n;
        const done = step > n;
        return (
          <li
            key={label}
            className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${
              active
                ? "border-[#E8A598]/55 bg-[#E8A598]/25 text-white"
                : done
                  ? "border-emerald-300/40 bg-emerald-950/20 text-emerald-100"
                  : "border-[#E8A598]/25 bg-[#0B132B]/10 text-[#F0DCC8]"
            }`}
          >
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] ${
                done ? "bg-emerald-400/30" : active ? "bg-[#E8A598]/40" : "bg-[#E8A598]/15"
              }`}
            >
              {done ? <Icon name="check" className="h-3 w-3" /> : n}
            </span>
            {label}
          </li>
        );
      })}
    </ol>
  );
}

export default function UploadWorkspace() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [wizardStep, setWizardStep] = useState<WizardStep>(1);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadPhase, setUploadPhase] = useState<UploadPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<IngestionResult | null>(null);
  const [hasExistingData, setHasExistingData] = useState(false);

  const [mode, setMode] = useState<QueryMode>("hybrid");
  const [topK, setTopK] = useState(3);
  const [maxHops, setMaxHops] = useState(3);
  const [question, setQuestion] = useState("");

  useEffect(() => {
    const session = loadRagSession();
    setMode(session.mode);
    setTopK(session.top_k);
    setMaxHops(session.max_hops);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authFetch("/api/v1/graph", { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as { total_nodes?: number; total_edges?: number };
        const hasData =
          (data.total_nodes ?? 0) > 0 || (data.total_edges ?? 0) > 0;
        if (!cancelled) setHasExistingData(hasData);
      } catch {
        /* backend offline */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const persistSession = useCallback(
    (ingestion?: IngestionSnapshot): RagSession => {
      const session: RagSession = { mode, top_k: topK, max_hops: maxHops, ingestion };
      saveRagSession(session);
      return session;
    },
    [mode, topK, maxHops],
  );

  const resetUpload = useCallback(() => {
    setFile(null);
    setUploadPhase("idle");
    setError(null);
    setResult(null);
    setWizardStep(1);
    if (inputRef.current) inputRef.current.value = "";
  }, []);

  const pickFile = useCallback((candidate: File | null) => {
    if (!candidate) return;
    if (!isPdf(candidate)) {
      setError("Only PDF files (.pdf) are supported.");
      return;
    }
    if (candidate.size > MAX_MB * 1024 * 1024) {
      setError(`File is too large. Maximum size is ${MAX_MB} MB.`);
      return;
    }
    setError(null);
    setResult(null);
    setUploadPhase("idle");
    setFile(candidate);
  }, []);

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    pickFile(e.target.files?.[0] ?? null);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    pickFile(e.dataTransfer.files?.[0] ?? null);
  };

  const onUpload = async () => {
    if (!file || uploadPhase === "uploading") return;
    setUploadPhase("uploading");
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await authFetch("/api/v1/ingest", { method: "POST", body: formData });
      if (!res.ok) throw new Error(await parseApiError(res));
      const data = (await res.json()) as IngestionResult;
      setResult(data);
      setUploadPhase("success");
      const snapshot: IngestionSnapshot = {
        filename: data.filename,
        sections_parsed: data.sections_parsed,
        nodes_created: data.nodes_created,
        edges_created: data.edges_created,
        chunks_indexed: data.chunks_indexed,
      };
      persistSession(snapshot);
      setWizardStep(2);
    } catch (err) {
      setUploadPhase("error");
      setError(err instanceof Error ? err.message : "Something went wrong while uploading.");
    }
  };

  const goToAsk = (q?: string) => {
    const snapshot = result
      ? {
          filename: result.filename,
          sections_parsed: result.sections_parsed,
          nodes_created: result.nodes_created,
          edges_created: result.edges_created,
          chunks_indexed: result.chunks_indexed,
        }
      : loadRagSession().ingestion;
    persistSession(snapshot);
    const trimmed = q?.trim();
    const url = trimmed ? `/ask?q=${encodeURIComponent(trimmed)}` : "/ask";
    router.push(url);
  };

  const busy = uploadPhase === "uploading";

  return (
    <div className="flex flex-col gap-6">
      <StepIndicator step={wizardStep} />

      {wizardStep === 1 && (
        <>
          {hasExistingData && (
            <div className="rounded-2xl border border-[#E8A598]/25 bg-[#0B132B]/12 px-4 py-3 text-sm text-[#EDE6DE]">
              You already have indexed data on the server.{" "}
              <button
                type="button"
                className="font-medium text-white underline decoration-white/40 underline-offset-2"
                onClick={() => setWizardStep(2)}
              >
                Skip upload and set retrieval method
              </button>
            </div>
          )}

          <div
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => !busy && inputRef.current?.click()}
            className={`rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
              dragOver
                ? "border-white/70 bg-white/15"
                : "border-white/35 bg-white/5 hover:border-white/50 hover:bg-white/10"
            } ${busy ? "pointer-events-none opacity-60" : "cursor-pointer"}`}
          >
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              className="sr-only"
              onChange={onInputChange}
              disabled={busy}
            />
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-white/25 bg-white/15 text-[#FFF4EA]">
              <Icon name="file" className="h-7 w-7" />
            </div>
            <p className="mt-4 text-base font-medium text-white">Drag and drop your PDF here</p>
            <p className="mt-1 text-sm text-[#F0DCC8]">or click to browse — up to {MAX_MB} MB</p>
          </div>

          {file && (
            <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-[#E8A598]/25 bg-[#0B132B]/12 px-4 py-3">
              <Icon name="file" className="h-5 w-5 shrink-0 text-[#FFF4EA]" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-white">{file.name}</p>
                <p className="text-xs text-[#F0DCC8]">{formatBytes(file.size)}</p>
              </div>
              <button
                type="button"
                onClick={resetUpload}
                disabled={busy}
                className="rounded-full border border-white/30 bg-white/10 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-white/20 disabled:opacity-50"
              >
                Remove
              </button>
            </div>
          )}

          {busy && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-white">Ingesting document…</p>
              <p className="text-xs text-[#F0DCC8]">Parsing, embedding chunks, and building the knowledge graph.</p>
              <div className="h-2 overflow-hidden rounded-full bg-white/15">
                <div className="h-full w-1/3 animate-pulse rounded-full bg-gradient-to-r from-[#E8A598] to-[#FFF8F2]" />
              </div>
            </div>
          )}

          {uploadPhase === "success" && result && (
            <div className="rounded-2xl border border-emerald-300/35 bg-emerald-950/25 px-5 py-4">
              <p className="flex items-center gap-2 text-sm font-semibold text-emerald-100">
                <Icon name="check" className="h-4 w-4" />
                {result.message || "Ingestion complete"}
              </p>
              <ul className="mt-3 grid gap-2 text-sm text-[#EDE6DE] sm:grid-cols-2">
                <li>• Sections parsed: {result.sections_parsed}</li>
                <li>• Graph nodes: {result.nodes_created}</li>
                <li>• Graph edges: {result.edges_created}</li>
                <li>• Vector chunks: {result.chunks_indexed}</li>
              </ul>
            </div>
          )}

          {error && (
            <div role="alert" className="rounded-2xl border border-red-300/40 bg-red-950/30 px-4 py-3 text-sm text-red-100">
              {error}
            </div>
          )}

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={onUpload}
              disabled={!file || busy}
              className="inline-flex items-center justify-center rounded-full border border-[#FFF4EA]/55 bg-[#FFF8F2] px-6 py-2.5 text-sm font-semibold text-[#1E2A35] shadow-sm transition hover:bg-[#F0E4D8] disabled:cursor-not-allowed disabled:border-[#FFF4EA]/30 disabled:bg-[#FFF8F2]/50 disabled:text-[#1E2A35]/55"
            >
              {busy ? "Uploading…" : "Upload PDF"}
            </button>
            {uploadPhase === "success" && (
              <button
                type="button"
                onClick={() => setWizardStep(2)}
                className="inline-flex items-center justify-center rounded-full border border-[#E8A598]/35 bg-white/5 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-md transition hover:bg-[#E8A598]/15"
              >
                Continue to retrieval
              </button>
            )}
          </div>
        </>
      )}

      {wizardStep === 2 && (
        <>
          <RetrievalSettings
            mode={mode}
            topK={topK}
            maxHops={maxHops}
            onMode={setMode}
            onTopK={setTopK}
            onMaxHops={setMaxHops}
          />
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setWizardStep(1)}
              className="inline-flex items-center justify-center rounded-full border border-[#E8A598]/35 bg-white/5 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-md transition hover:bg-[#E8A598]/15"
            >
              Back
            </button>
            <button
              type="button"
              onClick={() => {
                persistSession(loadRagSession().ingestion);
                setWizardStep(3);
              }}
              className="inline-flex items-center justify-center rounded-full border border-[#FFF4EA]/55 bg-[#FFF8F2] px-6 py-2.5 text-sm font-semibold text-[#1E2A35] shadow-sm transition hover:bg-[#F0E4D8]"
            >
              Continue
            </button>
            <Link
              href="/graph"
              className="inline-flex items-center justify-center rounded-full border border-[#E8A598]/35 bg-white/5 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-md transition hover:bg-[#E8A598]/15"
            >
              Preview graph
            </Link>
          </div>
        </>
      )}

      {wizardStep === 3 && (
        <>
          <p className="text-sm text-[#EDE6DE]">
            Mode: <span className="font-semibold capitalize text-white">{mode}</span>
            {(mode === "vector" || mode === "hybrid") && (
              <span className="text-[#F0DCC8]"> · top_k {topK}</span>
            )}
            {(mode === "graph" || mode === "hybrid") && (
              <span className="text-[#F0DCC8]"> · max hops {maxHops}</span>
            )}
          </p>
          <label className="block space-y-2">
            <span className="text-sm font-medium text-white">Your question</span>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={4}
              placeholder='e.g. "How are the main teams connected?"'
              className="w-full resize-y rounded-2xl border border-[#E8A598]/30 bg-[#0B132B]/15 px-4 py-3 text-sm text-white placeholder:text-[#F0DCC8] focus:border-[#E8A598]/55 focus:outline-none"
            />
          </label>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => goToAsk(question)}
              disabled={!question.trim()}
              className="inline-flex items-center justify-center rounded-full border border-[#FFF4EA]/55 bg-[#FFF8F2] px-6 py-2.5 text-sm font-semibold text-[#1E2A35] shadow-sm transition hover:bg-[#F0E4D8] disabled:cursor-not-allowed disabled:border-[#FFF4EA]/30 disabled:bg-[#FFF8F2]/50 disabled:text-[#1E2A35]/55"
            >
              Ask on Ask page
            </button>
            <button
              type="button"
              onClick={() => setWizardStep(2)}
              className="inline-flex items-center justify-center rounded-full border border-[#E8A598]/35 bg-white/5 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-md transition hover:bg-[#E8A598]/15"
            >
              Back
            </button>
            <button
              type="button"
              onClick={() => goToAsk()}
              className="inline-flex items-center justify-center rounded-full border border-[#E8A598]/35 bg-white/5 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-md transition hover:bg-[#E8A598]/15"
            >
              Open Ask without a question
            </button>
          </div>
        </>
      )}
    </div>
  );
}