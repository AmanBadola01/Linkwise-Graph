import type { ReactNode } from "react";
import { FONT_VARS, HEADING_STYLE } from "@/components/layout/page-shell";
import { PAGE_SKY_BACKGROUND, PAGE_WARM_OVERLAY_CLASS, tw } from "@/components/layout/linkwise-theme";

export function AuthShell({
  eyebrow,
  title,
  subtitle,
  children,
  footer,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div
      className="relative isolate min-h-screen overflow-hidden text-[#f6f6f6]"
      style={{ ...FONT_VARS, fontFamily: "var(--jakarta)" }}
    >
      <div aria-hidden="true" className="absolute inset-0 -z-10" style={{ background: PAGE_SKY_BACKGROUND }} />
      <div aria-hidden="true" className={PAGE_WARM_OVERLAY_CLASS} />
      <img
        aria-hidden="true"
        alt=""
        src="/originkit/hero-44/mist-overlay.webp"
        className="absolute inset-0 -z-10 h-full w-full object-cover opacity-60 mix-blend-soft-light"
      />
      <main className="relative mx-auto flex max-w-md flex-col gap-6 px-5 pb-16 pt-28 md:px-8">
        <div className={`${tw.glassPanel} p-8`}>
          <p className={`text-xs uppercase tracking-[0.2em] ${tw.eyebrow}`} style={{ fontFamily: "var(--outfit)" }}>
            {eyebrow}
          </p>
          <h1 className="mt-3 text-3xl uppercase leading-tight md:text-4xl" style={HEADING_STYLE}>
            {title}
          </h1>
          <p className={`mt-3 text-sm leading-6 ${tw.body}`}>{subtitle}</p>
          <div className="mt-8">{children}</div>
          <div className="mt-8 border-t border-[#E8A598]/20 pt-6 text-center text-sm">{footer}</div>
        </div>
      </main>
    </div>
  );
}