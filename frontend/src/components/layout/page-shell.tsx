import type { CSSProperties, ReactNode } from "react";
import { HEADING_STYLE, PAGE_SKY_BACKGROUND, PAGE_WARM_OVERLAY_CLASS, tw } from "@/components/layout/linkwise-theme";

export { HEADING_STYLE } from "@/components/layout/linkwise-theme";

export const FONT_VARS = {
  "--display": '"Brigends Expanded", "Archivo", sans-serif',
  "--jakarta": '"Plus Jakarta Sans", sans-serif',
  "--outfit": '"Outfit", sans-serif',
} as CSSProperties;

export function PageShell({
  children,
  maxWidth = "max-w-2xl",
}: {
  children: ReactNode;
  maxWidth?: string;
}) {
  return (
    <div
      className="relative isolate min-h-screen overflow-hidden text-[#f6f6f6]"
      style={{ ...FONT_VARS, fontFamily: "var(--jakarta)" }}
    >
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
      <main className={`relative mx-auto flex flex-col gap-8 px-5 pb-16 pt-28 md:px-8 ${maxWidth}`}>
        {children}
      </main>
    </div>
  );
}

export function GlassPanel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`${tw.glassPanel} p-8 md:p-10 ${className}`}>{children}</div>;
}