import type { GraphEdge, GraphNode } from "@/lib/graph-types";

export function resolveNodeRef(
  ref: string,
  byId: Map<string, GraphNode>,
  byName: Map<string, GraphNode>,
): string | null {
  if (byId.has(ref)) return ref;
  const n = byName.get(ref);
  return n?.id ?? null;
}

export const TYPE_COLORS: Record<string, string> = {
  Person: "#E8A598",
  Team: "#E8A598",
  Organization: "#E8A598",
  Product: "#E8A598",
  Technology: "#E8A598",
  Location: "#E8A598",
  Concept: "#E8A598",
  Service: "#E8A598",
};

/** Neo4j Bloom–like salmon default; type tint available via map. */
export function colorForType(type: string): string {
  return TYPE_COLORS[type] ?? "#E8A598";
}