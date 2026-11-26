import { Icon } from "@/components/about/icons";
import { GlassPanel, HEADING_STYLE, PageShell } from "@/components/layout/page-shell";
import UploadWorkspace from "@/components/upload/upload-workspace";

export default function UploadPage() {
  return (
    <PageShell maxWidth="max-w-3xl">
      <GlassPanel>
        <p className="text-xs uppercase tracking-[0.2em] text-[#F0DCC8]" style={{ fontFamily: "var(--outfit)" }}>
          Workflow
        </p>
        <h1 className="mt-3 text-4xl uppercase leading-tight md:text-5xl" style={HEADING_STYLE}>
          Upload &amp; configure
        </h1>
        <p className="mt-4 text-sm leading-6 text-[#EDE6DE]">
          Complete all steps here: ingest your PDF, pick vector / graph / hybrid retrieval, then go to Ask with your
          first question.
        </p>
        <ul className="mt-6 space-y-2">
          {[
            "Upload — parse PDF, build Neo4j graph and ChromaDB index",
            "Retrieval — choose mode, top_k and max_hops",
            "Question — type your first query and open the Ask page",
          ].map((step) => (
            <li key={step} className="flex items-start gap-3 text-sm leading-6 text-[#EDE6DE]">
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#E8A598]/35 text-[#FFF8F2]">
                <Icon name="check" className="h-3 w-3" />
              </span>
              {step}
            </li>
          ))}
        </ul>
        <div className="mt-8">
          <UploadWorkspace />
        </div>
      </GlassPanel>
    </PageShell>
  );
}