export type GraphNode = {
  id: string;
  name: string;
  type: string;
  description?: string;
  page?: number;
  degree?: number;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  description?: string;
  page?: number;
};

export type GraphDataResponse = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  entity_types: Record<string, number>;
};

export type SubgraphSnapshot = {
  query: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  savedAt: number;
};