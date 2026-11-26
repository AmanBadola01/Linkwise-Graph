"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LiquidGlassPill, LiquidNavbar, type LiquidNavItem } from "@/components/ui/liquid-glass-navbar";
import Link from "next/link";
import { authFetch, clearAuthSession, loadAuthUser, type AuthUser } from "@/lib/auth-session";

const BASE_NAV: LiquidNavItem[] = [
  { label: "Home", href: "/" },
  { label: "Upload", href: "/upload" },
  { label: "Graph", href: "/graph" },
  { label: "Ask", href: "/ask" },
  { label: "About", href: "/about" },
];

const UPLOAD_INDEX = 1;
const GRAPH_INDEX = 2;
const ASK_INDEX = 3;
const ABOUT_INDEX = 4;

const NAV_FONT = { fontFamily: '"Plus Jakarta Sans", sans-serif' } as const;

function navActiveIndex(pathname: string): number {
  if (pathname === "/about") return ABOUT_INDEX;
  if (pathname === "/upload") return UPLOAD_INDEX;
  if (pathname === "/graph") return GRAPH_INDEX;
  if (pathname === "/ask") return ASK_INDEX;
  return 0;
}

export default function SiteNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);

  // Load the user once. Re-reading localStorage (and re-rendering the whole
  // navbar) on every route change made tab switches feel sluggish.
  useEffect(() => {
    setUser(loadAuthUser());
  }, []);

  if (!user || pathname === "/login" || pathname === "/signup") {
    return null;
  }

  const activeIndex = navActiveIndex(pathname);

  async function logout() {
    // Server-side revocation first (invalidates every token for this user),
    // then local cleanup. Previously logout only deleted local copies.
    try {
      await authFetch("/api/v1/auth/logout", { method: "POST" });
    } catch {
      // Local cleanup below still runs if the network call fails.
    }
    clearAuthSession();
    setUser(null);
    router.push("/login");
  }

  return (
    <>
      <header className="pointer-events-none fixed inset-x-0 top-3 z-50 flex justify-center px-4">
        <div className="pointer-events-auto">
          {/* Controlled `active` instead of key-remount: keep this mounted so
              switching tabs only moves the highlight instead of tearing down
              and rebuilding the WebGL navbar (shader recompile + canvas init)
              on every navigation. */}
          <LiquidNavbar tone="light" active={activeIndex} items={BASE_NAV} style={NAV_FONT} />
        </div>
      </header>

      <aside className="pointer-events-none fixed bottom-4 left-4 z-50 px-4 pb-[env(safe-area-inset-bottom)]">
        <div className="pointer-events-auto">
          <LiquidGlassPill tone="light" aria-label="Account" style={NAV_FONT}>
            <span className="nimbus-item nimbus-item--static" title={user.display_name}>
              {user.display_name}
            </span>
            <Link href="/account" className="nimbus-item">
              Account
            </Link>
            <button type="button" className="nimbus-item" onClick={() => void logout()}>
              Log out
            </button>
          </LiquidGlassPill>
        </div>
      </aside>
    </>
  );
}