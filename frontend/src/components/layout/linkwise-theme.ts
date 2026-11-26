import type { CSSProperties } from "react";

/** Warm palette — balances cool sky background with graph salmon. */
export const WARM_CORAL = "#E8A598";
export const WARM_CREAM = "#FFF8F2";
export const TEXT_EYEBROW = "#F0DCC8";
export const TEXT_BODY = "#EDE6DE";
export const TEXT_MUTED = "#D9D0C8";
export const TEXT_INK = "#1E2A35";

export const HEADING_STYLE: CSSProperties = {
  fontFamily: "var(--display)",
  letterSpacing: "0.03em",
  background: `linear-gradient(135deg, ${WARM_CREAM} 0%, ${WARM_CORAL} 42%, #B8D4F0 100%)`,
  WebkitBackgroundClip: "text",
  backgroundClip: "text",
  color: "transparent",
};

export const PAGE_SKY_BACKGROUND =
  "linear-gradient(178deg, #8FAEC8 0%, #5E7F9E 38%, #6B8FAE 72%, #3D4A52 100%)";

export const PAGE_WARM_OVERLAY_CLASS =
  "absolute inset-0 -z-10 bg-[linear-gradient(168deg,transparent_25%,rgba(232,165,152,0.22)_88%,rgba(245,184,65,0.12)_100%)]";

export const STEP_BADGE_GRADIENT = `linear-gradient(145deg, #C4897E 0%, ${WARM_CORAL} 48%, ${WARM_CREAM} 100%)`;

export const tw = {
  eyebrow: "text-[#F0DCC8]",
  body: "text-[#EDE6DE]",
  muted: "text-[#D9D0C8]",
  label: "text-[#F0DCC8]",
  glassPanel:
    "rounded-3xl border border-[#E8A598]/30 bg-[#0B132B]/15 shadow-[0_10px_40px_rgba(11,19,43,0.28)] backdrop-blur-md",
  glassInner: "rounded-2xl border border-[#E8A598]/25 bg-[#0B132B]/12",
  glassSubtle: "rounded-2xl border border-[#E8A598]/20 bg-[#0B132B]/10",
  iconBadge:
    "flex items-center justify-center rounded-2xl border border-[#E8A598]/35 bg-[#E8A598]/12 text-[#FFF4EA]",
  checkBubble: "bg-[#E8A598]/35 text-[#FFF8F2]",
  btnPrimary:
    "inline-flex items-center justify-center rounded-full border border-[#E8A598]/55 bg-[#E8A598]/25 px-5 py-2.5 text-sm font-medium text-[#FFF8F2] backdrop-blur-md transition hover:bg-[#E8A598]/35 disabled:opacity-50",
  btnSecondary:
    "inline-flex items-center justify-center rounded-full border border-[#E8A598]/35 bg-white/5 px-5 py-2.5 text-sm font-medium text-white backdrop-blur-md transition hover:bg-[#E8A598]/15 disabled:opacity-50",
  btnSolid:
    "inline-flex items-center justify-center rounded-full border border-[#FFF4EA]/55 bg-[#FFF8F2] px-6 py-2.5 text-sm font-semibold text-[#1E2A35] shadow-sm transition hover:bg-[#F0E4D8] disabled:cursor-not-allowed disabled:border-[#FFF4EA]/30 disabled:bg-[#FFF8F2]/50 disabled:text-[#1E2A35]/55",
  input:
    "w-full rounded-2xl border border-[#E8A598]/30 bg-[#0B132B]/20 px-4 py-3 text-sm text-white placeholder:text-[#F0DCC8] focus:border-[#E8A598]/55 focus:outline-none",
  progress: "bg-gradient-to-r from-[#E8A598] to-[#FFF8F2]",
  accent: "accent-[#E8A598]",
  stepBadge:
    "flex h-9 w-9 items-center justify-center rounded-full border border-[#FFF4EA]/35 text-sm font-semibold text-[#1E2A35] shadow-[inset_0_1px_0_rgba(255,248,242,0.45)]",
} as const;