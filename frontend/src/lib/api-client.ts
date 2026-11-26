export async function parseApiError(res: Response): Promise<string> {
  const fallback = `${res.status} ${res.statusText || "Request failed"}`.trim();
  try {
    const text = await res.text();
    if (!text) return fallback;
    try {
      const data = JSON.parse(text) as { detail?: unknown; message?: string };
      if (typeof data?.detail === "string") return data.detail;
      if (Array.isArray(data?.detail)) {
        return data.detail.map((d: { msg?: string }) => d.msg ?? String(d)).join(" ");
      }
      if (typeof data?.message === "string") return data.message;
    } catch {
      return text.length > 280 ? `${text.slice(0, 280)}…` : text;
    }
    return fallback;
  } catch {
    return fallback;
  }
}