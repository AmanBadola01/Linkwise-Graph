import Link from "next/link";
import { GlassPanel, HEADING_STYLE, PageShell } from "@/components/layout/page-shell";

export default function NotFound() {
  return (
    <PageShell maxWidth="max-w-2xl">
      <GlassPanel>
        <p className="text-xs uppercase tracking-[0.2em] text-[#F0DCC8]" style={{ fontFamily: "var(--outfit)" }}>
          404
        </p>
        <h1 className="mt-3 text-4xl uppercase leading-tight md:text-5xl" style={HEADING_STYLE}>
          Page not found
        </h1>
        <p className="mt-4 text-sm leading-6 text-[#EDE6DE]">
          That page does not exist. Head back to your documents, or sign in if you were logged out.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/"
            className="inline-flex items-center justify-center rounded-full border border-[#FFF4EA]/55 bg-[#FFF8F2] px-6 py-2.5 text-sm font-semibold text-[#1E2A35] shadow-sm transition hover:bg-[#F0E4D8]"
          >
            Home
          </Link>
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-full border border-[#E8A598]/35 bg-white/5 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-md transition hover:bg-[#E8A598]/15"
          >
            Sign in
          </Link>
        </div>
      </GlassPanel>
    </PageShell>
  );
}
