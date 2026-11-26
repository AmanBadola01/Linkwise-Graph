import type { Metadata } from "next";
import GraphPage from "@/components/graph/graph-page";

export const metadata: Metadata = {
  title: "Graph · Linkwise-Graph",
  description: "Explore the knowledge graph built from your documents.",
};

export default function Graph() {
  return <GraphPage />;
}