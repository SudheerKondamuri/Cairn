import { accountHeaders } from "./auth";
export class UpstreamError extends Error {
  constructor(
    public status: number,
    message: string,
    public retryAfter?: string,
  ) {
    super(message);
  }
}
export function upstreamConfigured() {
  if (!process.env.CAIRN_API_URL) return false;
  if (process.env.CAIRN_ACCESS_MODE === "local") return true;
  return (
    !!process.env.CAIRN_API_KEY &&
    process.env.CAIRN_API_KEY !== "replace-me"
  );
}
export async function upstream(path: string, init: RequestInit = {}) {
  if (!upstreamConfigured())
    throw new UpstreamError(
      503,
      "The investigation service has not been connected. Configure the server API URL and service key.",
    );
  const base = new URL(process.env.CAIRN_API_URL!);
  if (!["http:", "https:"].includes(base.protocol))
    throw new UpstreamError(503, "The investigation service URL is invalid.");
  try {
    const response = await fetch(new URL(path, base), {
      ...init,
      redirect: "error",
      cache: "no-store",
      headers: {
        ...init.headers,
        ...(process.env.CAIRN_API_KEY ? { "X-Cairn-API-Key": process.env.CAIRN_API_KEY } : {}),
        ...(await accountHeaders()),
      },
      signal: AbortSignal.timeout(init.method === "POST" ? 60_000 : 12_000),
    });
    if (!response.ok) {
      let message =
        "The investigation service could not complete this request.";
      if (response.status === 404)
        message = "This investigation was not found.";
      if (response.status === 429)
        message = "The service is busy. Wait before trying again.";
      if ([400, 409, 403, 503].includes(response.status)) {
        const data = await response.json().catch(() => null);
        if (
          typeof data?.message === "string" ||
          typeof data?.error === "string"
        )
          message = (data.message || data.error).slice(0, 1000);
      }
      throw new UpstreamError(
        response.status === 401 || response.status === 403
          ? 502
          : response.status,
        message,
        response.headers.get("retry-after") || undefined,
      );
    }
    return response;
  } catch (error) {
    if (error instanceof UpstreamError) throw error;
    throw new UpstreamError(
      503,
      init.method === "POST"
        ? "The submission outcome is unknown. Check the investigation list before submitting again."
        : "The investigation service is unreachable. Your last result has been kept.",
    );
  }
}
