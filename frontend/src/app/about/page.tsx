import type { Metadata } from "next";
import AboutPage from "@/components/about/about-page";

export const metadata: Metadata = {
  title: "About · Linkwise-Graph",
  description:
    "Learn how Linkwise-Graph combines Neo4j GraphRAG, ChromaDB vector search, and Gemini synthesis for cited, hybrid document Q&A.",
  openGraph: {
    title: "About Linkwise-Graph",
    description:
      "Hybrid GraphRAG and vector retrieval for PDFs — multi-hop reasoning, citations, and an interactive knowledge graph.",
  },
};

export default function About() {
  return <AboutPage />;
}
