import type { Metadata } from "next";
import UploadPage from "@/components/upload/upload-page";

export const metadata: Metadata = {
  title: "Upload · Linkwise-Graph",
  description: "Upload PDF documents to ingest into the knowledge graph and vector index.",
};

export default function Upload() {
  return <UploadPage />;
}