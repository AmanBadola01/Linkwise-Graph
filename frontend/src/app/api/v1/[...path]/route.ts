import { type NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.LINKWISE_BACKEND_URL ?? "http://127.0.0.1:8003";
// Long ingests run for tens of seconds; bound the proxy wait instead of
// hanging forever (the old 30s rewrite proxy aborted uploads, BUG-16).
const PROXY_TIMEOUT_MS = Number(process.env.PROXY_TIMEOUT_MS ?? 600_000);

type Ctx = { params: Promise<{ path: string[] }> };

const SKIP_REQUEST_HEADERS = new Set(["host", "content-length", "connection"]);
const SKIP_RESPONSE_HEADERS = new Set(["content-length", "connection", "transfer-encoding", "content-encoding"]);

async function proxyRequest(req: NextRequest, ctx: Ctx, method: string) {
  const { path } = await ctx.params;
  const suffix = path.join("/");
  const target = `${BACKEND_URL}/api/v1/${suffix}${req.nextUrl.search}`;

  // Forward all client headers (cookie session, authorization, custom
  // headers) instead of an allowlist that silently dropped them (BUG-16).
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!SKIP_REQUEST_HEADERS.has(key.toLowerCase())) headers.set(key, value);
  });

  const hasBody = method !== "GET" && method !== "HEAD";

  let res: Response;
  try {
    res = await fetch(target, {
      method,
      headers,
      // Stream the request body instead of buffering the whole upload in
      // this server's memory (BUG-16). duplex is required for streaming.
      body: hasBody ? req.body : undefined,
      // @ts-expect-error Node fetch streaming requires duplex
      duplex: hasBody ? "half" : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(PROXY_TIMEOUT_MS),
    });
  } catch (err) {
    const timedOut = err instanceof Error && err.name === "TimeoutError";
    return NextResponse.json(
      {
        detail: timedOut
          ? "The Linkwise-Graph API took too long to respond. Please try again."
          : "Cannot reach the Linkwise-Graph API. Start it with: uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8003",
      },
      { status: timedOut ? 504 : 503 },
    );
  }

  const outHeaders = new Headers();
  res.headers.forEach((value, key) => {
    if (!SKIP_RESPONSE_HEADERS.has(key.toLowerCase())) outHeaders.append(key, value);
  });
  // Preserve Set-Cookie (HttpOnly session) exactly as the backend sent it.
  const setCookies = typeof res.headers.getSetCookie === "function" ? res.headers.getSetCookie() : [];
  if (setCookies.length) {
    outHeaders.delete("set-cookie");
    for (const cookie of setCookies) outHeaders.append("set-cookie", cookie);
  }

  return new NextResponse(res.body, { status: res.status, headers: outHeaders });
}

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxyRequest(req, ctx, "GET");
}

export async function POST(req: NextRequest, ctx: Ctx) {
  return proxyRequest(req, ctx, "POST");
}

export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxyRequest(req, ctx, "PUT");
}

export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxyRequest(req, ctx, "DELETE");
}
