import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC = new Set(["/login", "/signup"]);
// Routes that actually exist. Unknown paths must render the 404 page, not
// bounce to login (BUG-18).
const KNOWN = ["/", "/login", "/signup", "/upload", "/graph", "/ask", "/about", "/account"];

function isKnown(pathname: string): boolean {
  return KNOWN.some((p) => pathname === p || (p !== "/" && pathname.startsWith(`${p}/`)));
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (!isKnown(pathname)) {
    return NextResponse.next(); // -> not-found.tsx
  }

  // Presence check only (the backend validates the HttpOnly session cookie
  // on every API call); UX gate, not a security boundary.
  const signedIn = Boolean(request.cookies.get("lw_session")?.value);

  if (signedIn && PUBLIC.has(pathname)) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  if (!signedIn && !PUBLIC.has(pathname)) {
    const login = new URL("/login", request.url);
    if (pathname !== "/") {
      login.searchParams.set("next", pathname);
    }
    return NextResponse.redirect(login);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|originkit).*)"],
};
