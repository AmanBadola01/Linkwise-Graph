import type { ReactNode } from "react";
import Link from "next/link";
import { Icon, type IconName } from "@/components/about/icons";
import { FONT_VARS } from "@/components/layout/page-shell";
import {
  HEADING_STYLE,
  PAGE_SKY_BACKGROUND,
  PAGE_WARM_OVERLAY_CLASS,
  STEP_BADGE_GRADIENT,
  tw,
} from "@/components/layout/linkwise-theme";

const GITHUB_URL = "https://github.com/AmanBadola01/Linkwise-Graph";

const HERO_POINTS: string[] = [
  "Hybrid GraphRAG and vector retrieval for document intelligence",
  "Every answer includes [Page X] citations and a visible reasoning chain",
  "Interactive D3 graph explorer with query-time subgraph highlighting",
  "Per-account authentication with isolated graph and vector data",
  "Open source (MIT) — FastAPI, Next.js, Neo4j, ChromaDB, and Gemini",
];

type Feature = { icon: IconName; title: string; text: string };

const WHAT_IT_DOES: Feature[] = [
  { icon: "file", title: "Reads PDFs", text: "Extracts the text and removes repeated headers and footers." },
  { icon: "network", title: "Builds a knowledge graph", text: "Stores entities and their relationships in Neo4j." },
  { icon: "layers", title: "Builds a vector index", text: "Stores text chunks in ChromaDB for semantic search." },
  { icon: "message", title: "Answers with citations", text: "Each answer points to the source pages it used." },
];

const WHY_IT_MATTERS: string[] = [
  "Vector-only RAG finds semantically similar passages but cannot reliably trace how entities connect.",
  "Graph traversal follows relationship chains across 2–4 hops with auditable steps and page references.",
  "Hybrid mode fuses both retrieval paths so complex questions stay grounded in your source material.",
];

const PIPELINE: { title: string; text: string }[] = [
  {
    title: "Safety screen",
    text: "Reject PDFs that carry scripts, embedded files, or launch actions before any parsing begins.",
  },
  {
    title: "Parse and deduplicate",
    text: "Layout-aware extraction with header/footer removal; identical uploads reuse prior results per account.",
  },
  {
    title: "Index vectors",
    text: "Embed sections locally with all-MiniLM-L6-v2 (ONNX) and store them in ChromaDB for semantic search.",
  },
  {
    title: "Extract the graph",
    text: "Gemini extracts entities, types, relationships, and source pages under a strict schema.",
  },
  {
    title: "Clean and resolve",
    text: "Filter noise (dates, orphans, self-loops) and merge aliases with RapidFuzz entity resolution.",
  },
  {
    title: "Commit or rollback",
    text: "Write nodes and edges to Neo4j on success; on failure, roll back partial graph and vector writes.",
  },
];

const SECURITY_FEATURES: Feature[] = [
  {
    icon: "server",
    title: "Authenticated sessions",
    text: "JWT sessions in HttpOnly cookies, bcrypt password hashing, and rate-limited auth endpoints.",
  },
  {
    icon: "database",
    title: "Tenant isolation",
    text: "Every ingest, graph query, and vector search is scoped to your account in Neo4j and ChromaDB.",
  },
  {
    icon: "layers",
    title: "Safe ingestion",
    text: "Parse-before-mutate ordering, content screening, and transactional rollback on pipeline failure.",
  },
];

const QUERY_MODES: Feature[] = [
  { icon: "search", title: "Vector", text: 'Semantic search over text chunks. Best for "what does the document say about X?"' },
  { icon: "route", title: "Graph", text: 'Multi-hop reasoning over relationships. Best for "how is A connected to C?"' },
  { icon: "sparkles", title: "Hybrid", text: "Runs both and fuses them into one cited answer for complex questions." },
];

const STACK: { icon: IconName; title: string; items: string[] }[] = [
  {
    icon: "server",
    title: "Backend",
    items: ["FastAPI and Uvicorn", "Pydantic v2 typed models", "PyPDF for PDF parsing", "RapidFuzz for entity matching"],
  },
  {
    icon: "database",
    title: "Data stores",
    items: ["Neo4j 5 Community (graph)", "ChromaDB with HNSW cosine index (vectors)"],
  },
  {
    icon: "cpu",
    title: "AI models",
    items: ["Google Gemini gemini-3.5-flash-lite", "all-MiniLM-L6-v2 (ONNX, 384-dim, runs on CPU)"],
  },
  {
    icon: "code",
    title: "Frontend",
    items: [
      "Next.js 16 and React 19",
      "TypeScript and Tailwind CSS v4",
      "D3 force-directed graph explorer",
    ],
  },
];

// A transparent glass card that holds content over the shared background.
function GlassCard({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`${tw.glassPanel} p-6 md:p-8 ${className}`}>{children}</div>;
}

function IconBadge({ name }: { name: IconName }) {
  return (
    <span className={`h-11 w-11 shrink-0 ${tw.iconBadge}`}>
      <Icon name={name} className="h-5 w-5" />
    </span>
  );
}

function SectionTitle({ id, eyebrow, title }: { id: string; eyebrow: string; title: string }) {
  return (
    <div className="px-1">
      <p className="text-xs uppercase tracking-[0.2em] text-[#F0DCC8]" style={{ fontFamily: "var(--outfit)" }}>
        {eyebrow}
      </p>
      <h2
        id={id}
        className="mt-2 text-2xl uppercase leading-tight md:text-3xl"
        style={HEADING_STYLE}
      >
        {title}
      </h2>
    </div>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-3 text-[15px] leading-6 text-[#EDE6DE]">
          <span className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#E8A598]/35 text-[#FFF8F2]">
            <Icon name="check" className="h-3 w-3" />
          </span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function FeatureCard({ feature }: { feature: Feature }) {
  return (
    <GlassCard className="p-5">
      <IconBadge name={feature.icon} />
      <h3 className="mt-4 text-base font-semibold text-white">{feature.title}</h3>
      <p className="mt-2 text-sm leading-6 text-[#D9D0C8]">{feature.text}</p>
    </GlassCard>
  );
}

export default function AboutPage() {
  return (
    <div
      className="relative isolate min-h-screen overflow-hidden text-[#f6f6f6]"
      style={{ ...FONT_VARS, fontFamily: "var(--jakarta)" }}
    >
      {/* Same background as the home hero: sky gradient, mist and mountain ridge. */}
      <div
        aria-hidden="true"
        className="absolute inset-0 -z-10"
        style={{ background: PAGE_SKY_BACKGROUND }}
      />
      <div aria-hidden="true" className={PAGE_WARM_OVERLAY_CLASS} />
      <img
        aria-hidden="true"
        alt=""
        src="/originkit/hero-44/mist-overlay.webp"
        className="absolute inset-0 -z-10 h-full w-full object-cover opacity-60 mix-blend-soft-light"
      />
      <img
        aria-hidden="true"
        alt=""
        src="/originkit/hero-44/ridge.webp"
        className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 w-full object-cover opacity-40"
      />

      <main className="relative mx-auto flex max-w-6xl flex-col gap-10 px-5 pb-16 pt-28 md:px-8">
        {/* Intro */}
        <GlassCard>
          <p className="text-xs uppercase tracking-[0.2em] text-[#F0DCC8]" style={{ fontFamily: "var(--outfit)" }}>
            About the project
          </p>
          <h1
            className="mt-3 text-4xl uppercase leading-tight md:text-6xl"
            style={HEADING_STYLE}
          >
            Linkwise-Graph
          </h1>
          <p className="mt-4 max-w-3xl text-[15px] leading-7 text-[#EDE6DE] md:text-base">
            Linkwise-Graph is a hybrid GraphRAG and vector retrieval platform. It indexes each PDF as a Neo4j
            knowledge graph and a ChromaDB semantic index, then answers questions in vector, graph, or hybrid mode
            with citations, reasoning chains, and an explorable subgraph.
          </p>
          <div className="mt-6">
            <BulletList items={HERO_POINTS} />
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/upload"
              className={`gap-2 ${tw.btnPrimary}`}
            >
              <Icon name="file" className="h-4 w-4" />
              Upload a PDF
            </Link>
            <Link href="/ask" className={`gap-2 ${tw.btnSecondary}`}>
              <Icon name="message" className="h-4 w-4" />
              Ask a question
            </Link>
            <Link href="/graph" className={`gap-2 ${tw.btnSecondary}`}>
              <Icon name="network" className="h-4 w-4" />
              View graph
            </Link>
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={`gap-2 ${tw.btnSecondary} text-[#EDE6DE]`}
            >
              <Icon name="code" className="h-4 w-4" />
              Source on GitHub
            </a>
          </div>
        </GlassCard>

        {/* What it does */}
        <section aria-labelledby="what-it-does" className="flex flex-col gap-5">
          <SectionTitle id="what-it-does" eyebrow="What it does" title="From PDF to cited answer" />
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {WHAT_IT_DOES.map((feature) => (
              <FeatureCard key={feature.title} feature={feature} />
            ))}
          </div>
        </section>

        {/* Why it matters + query modes */}
        <section aria-labelledby="why-it-matters" className="grid gap-5 lg:grid-cols-2">
          <GlassCard>
            <SectionTitle id="why-it-matters" eyebrow="Why it matters" title="Why two stores" />
            <div className="mt-6">
              <BulletList items={WHY_IT_MATTERS} />
            </div>
          </GlassCard>
          <GlassCard>
            <SectionTitle id="query-modes" eyebrow="Query modes" title="Three ways to ask" />
            <ul className="mt-6 space-y-4">
              {QUERY_MODES.map((mode) => (
                <li key={mode.title} className="flex items-start gap-4">
                  <IconBadge name={mode.icon} />
                  <div>
                    <h3 className="text-base font-semibold text-white">{mode.title}</h3>
                    <p className="mt-1 text-sm leading-6 text-[#D9D0C8]">{mode.text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </GlassCard>
        </section>

        {/* How it works */}
        <section aria-labelledby="how-it-works" className="flex flex-col gap-5">
          <SectionTitle id="how-it-works" eyebrow="How it works" title="The ingestion pipeline" />
          <ol className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {PIPELINE.map((step, index) => (
              <li key={step.title}>
                <GlassCard className="h-full p-5">
                  <span
                    className={tw.stepBadge}
                    style={{ fontFamily: "var(--outfit)", background: STEP_BADGE_GRADIENT }}
                  >
                    {index + 1}
                  </span>
                  <h3 className="mt-4 text-base font-semibold text-white">{step.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-[#D9D0C8]">{step.text}</p>
                </GlassCard>
              </li>
            ))}
          </ol>
        </section>

        {/* Security */}
        <section aria-labelledby="security" className="flex flex-col gap-5">
          <SectionTitle id="security" eyebrow="Security" title="Built for multi-user use" />
          <div className="grid gap-5 sm:grid-cols-3">
            {SECURITY_FEATURES.map((feature) => (
              <FeatureCard key={feature.title} feature={feature} />
            ))}
          </div>
        </section>

        {/* Tech stack */}
        <section aria-labelledby="tech-stack" className="flex flex-col gap-5">
          <SectionTitle id="tech-stack" eyebrow="Tech stack" title="What it is built with" />
          <div className="grid gap-5 sm:grid-cols-2">
            {STACK.map((group) => (
              <GlassCard key={group.title} className="p-6">
                <div className="flex items-center gap-4">
                  <IconBadge name={group.icon} />
                  <h3 className="text-lg font-semibold text-white">{group.title}</h3>
                </div>
                <div className="mt-5">
                  <BulletList items={group.items} />
                </div>
              </GlassCard>
            ))}
          </div>
        </section>

        {/* Open source */}
        <section aria-labelledby="open-source" className="flex flex-col gap-5">
          <SectionTitle id="open-source" eyebrow="Open source" title="Repository and license" />
          <GlassCard>
            <p className="max-w-3xl text-sm leading-7 text-[#D9D0C8] md:text-[15px]">
              The full stack — FastAPI API, ingestion pipeline, hybrid RAG engines, and this Next.js client — is
              published under the MIT License. Documentation, API reference, and deployment notes live in the
              repository README.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                className={`gap-2 ${tw.btnPrimary}`}
              >
                <Icon name="code" className="h-4 w-4" />
                AmanBadola01/Linkwise-Graph
              </a>
              <Link href="/" className={`gap-2 ${tw.btnSecondary}`}>
                <Icon name="arrow-left" className="h-4 w-4" />
                Back to home
              </Link>
            </div>
          </GlassCard>
        </section>

        {/* Footer */}
        <GlassCard className="flex flex-col items-start justify-between gap-4 p-5 sm:flex-row sm:items-center">
          <p className="text-sm text-[#D9D0C8]">Linkwise-Graph · MIT License · Document intelligence with cited GraphRAG</p>
        </GlassCard>
      </main>
    </div>
  );
}
