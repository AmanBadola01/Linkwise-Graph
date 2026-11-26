import type { SubgraphSnapshot } from "@/lib/graph-types";

const USER_KEY = "linkwise_user";

export type QueryMode = "vector" | "graph" | "hybrid";

export type IngestionSnapshot = {
  filename: string;
  sections_parsed: number;
  nodes_created: number;
  edges_created: number;
  chunks_indexed: number;
};

export type RagSession = {
  mode: QueryMode;
  top_k: number;
  max_hops: number;
  ingestion?: IngestionSnapshot;
  lastSubgraph?: SubgraphSnapshot;
};

const LEGACY_STORAGE_KEY = "linkwise-rag-session";

const DEFAULTS: RagSession = {
  mode: "hybrid",
  top_k: 3,
  max_hops: 3,
};

function storageKeyForUser(userId: string): string {
  return `linkwise-rag-session:${userId}`;
}

function currentUserId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { id?: string };
    return parsed.id ?? null;
  } catch {
    return null;
  }
}

function currentStorageKey(): string | null {
  const userId = currentUserId();
  if (!userId) return null;
  return storageKeyForUser(userId);
}

export function clearLegacyRagSession(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(LEGACY_STORAGE_KEY);
}

export function clearRagSessionForCurrentUser(): void {
  if (typeof window === "undefined") return;
  const key = currentStorageKey();
  if (key) localStorage.removeItem(key);
}

export function loadRagSession(): RagSession {
  if (typeof window === "undefined") return { ...DEFAULTS };
  const key = currentStorageKey();
  if (!key) return { ...DEFAULTS };
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return { ...DEFAULTS };
    const parsed = JSON.parse(raw) as Partial<RagSession>;
    return {
      mode: parsed.mode ?? DEFAULTS.mode,
      top_k: clamp(parsed.top_k ?? DEFAULTS.top_k, 1, 10),
      max_hops: clamp(parsed.max_hops ?? DEFAULTS.max_hops, 1, 5),
      ingestion: parsed.ingestion,
      lastSubgraph: parsed.lastSubgraph,
    };
  } catch {
    return { ...DEFAULTS };
  }
}

export function saveRagSession(session: RagSession): void {
  if (typeof window === "undefined") return;
  const key = currentStorageKey();
  if (!key) return;
  localStorage.setItem(key, JSON.stringify(session));
}

export function updateRagSession(patch: Partial<RagSession>): RagSession {
  const next = { ...loadRagSession(), ...patch };
  saveRagSession(next);
  return next;
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}