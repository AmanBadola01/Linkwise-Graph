import type { Metadata } from "next";
import AskPage from "@/components/ask/ask-page";

export const metadata: Metadata = {
  title: "Ask · Linkwise-Graph",
  description: "Ask questions over your ingested PDF with vector, graph, or hybrid retrieval.",
};

export default function Ask() {
  return <AskPage />;
}