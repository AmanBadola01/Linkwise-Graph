import type { Metadata } from "next";
import AboutPage from "@/components/about/about-page";

export const metadata: Metadata = {
  title: "About · Linkwise-Graph",
  description:
    "Linkwise-Graph turns PDFs into a cited knowledge graph — upload, ask, and explore relationships.",
};

export default function About() {
  return <AboutPage />;
}
