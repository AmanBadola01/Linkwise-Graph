import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Hide the default bottom-left Next.js dev badge (static/dynamic route indicator).
  devIndicators: false,
  // Dev-only: lets the browser load Next's live-reload connection through the
  // Cloudflare tunnel and the server IP. Without this React never starts.
  allowedDevOrigins: ["*.trycloudflare.com", "116.202.210.102"],
  // No rewrites for /api/v1/*: src/app/api/v1/[...path]/route.ts proxies to
  // LINKWISE_BACKEND_URL via fetch (no 30s rewrite-proxy timeout, which
  // aborted long PDF ingests with "socket hang up" / Internal Server Error).
  experimental: {
    // Client router cache: reuse a tab's RSC payload for 30s instead of
    // refetching it on every switch (Next defaults dynamic pages to 0s, so
    // Home <-> Upload <-> Ask round-trips re-requested the page each time).
    staleTimes: { dynamic: 30, static: 120 },
    // Tree-shake the two heavy libs so tab bundles stay small.
    optimizePackageImports: ["d3-force", "framer-motion"],
  },
};

export default nextConfig;
