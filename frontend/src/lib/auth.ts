import { cookies, headers } from "next/headers";
import { cache } from "react";
export const SESSION_COOKIE = "cairn_session";
export const SESSION_SECONDS = 8 * 60 * 60;
export type Account = {
  account_id: string;
  admin: boolean;
  local?: boolean;
  identities: string[];
  allowance: {
    limit: number | null;
    used: number;
    remaining: number | null;
    trial_remaining: number | null;
    paused: boolean;
    request_pending: boolean;
    unlimited?: boolean;
  };
};
export function configuredProviders() {
  return {
    google:
      !!process.env.GOOGLE_CLIENT_ID && !!process.env.GOOGLE_CLIENT_SECRET,
    github:
      !!process.env.GITHUB_CLIENT_ID && !!process.env.GITHUB_CLIENT_SECRET,
  };
}
export function authConfigured() {
  const p = configuredProviders();
  return p.google || p.github;
}
export async function localAccessEnabled() {
  return process.env.CAIRN_ACCESS_MODE !== "restricted";
}
export async function accountHeaders(): Promise<Record<string,string>> {
  const token = await sessionToken();
  const isLocal = await localAccessEnabled();
  return {
    ...(token ? { "X-Cairn-Session": token } : {}),
    ...(isLocal ? { "X-Cairn-Local": "true" } : {}),
  };
}
export async function sessionToken() {
  return (await cookies()).get(SESSION_COOKIE)?.value || "";
}
export const currentAccount = cache(async (): Promise<Account | null> => {
  const isLocal = await localAccessEnabled();
  const token = await sessionToken();
  if (!token && !isLocal) return null;

  const fallbackLocalAccount: Account = {
    account_id: "acct-local",
    admin: true,
    local: true,
    identities: ["local-operator"],
    allowance: {
      limit: null,
      used: 0,
      remaining: null,
      trial_remaining: null,
      paused: false,
      request_pending: false,
      unlimited: true,
    },
  };

  if (
    !process.env.CAIRN_API_URL ||
    (!isLocal && (!process.env.CAIRN_API_KEY || process.env.CAIRN_API_KEY === "replace-me"))
  ) {
    return isLocal ? fallbackLocalAccount : null;
  }

  try {
    const headers: Record<string, string> = {
      ...(await accountHeaders()),
    };
    if (process.env.CAIRN_API_KEY) {
      headers["X-Cairn-API-Key"] = process.env.CAIRN_API_KEY;
    }
    const response = await fetch(
      new URL("/api/web/me", process.env.CAIRN_API_URL),
      {
        headers,
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      },
    );
    if (response.ok) {
      return await response.json();
    }
  } catch {
    // API server may be offline or booting
  }

  return isLocal ? fallbackLocalAccount : null;
});
export async function signedIn() {
  return true;
}
export function appOrigin() {
  const url = new URL(process.env.CAIRN_APP_ORIGIN || "http://localhost:3000");
  if (
    process.env.CAIRN_ACCESS_MODE !== "restricted" ||
    url.protocol === "https:" ||
    (
      url.protocol === "http:" &&
      ["localhost", "127.0.0.1"].includes(url.hostname)
    )
  )
    return url.origin;
  throw new Error("Public origin requires HTTPS");
}
export function sameOrigin(request: Request) {
  try {
    const origin = request.headers.get("origin");
    if (!origin) return true;
    const host = request.headers.get("host");
    const originUrl = new URL(origin);
    if (host && originUrl.host === host) return true;
    return origin === appOrigin();
  } catch {
    return process.env.CAIRN_ACCESS_MODE !== "restricted";
  }
}
export function cookieOptions() {
  return {
    httpOnly: true,
    secure: appOrigin().startsWith("https:"),
    sameSite: "lax" as const,
    path: "/",
    maxAge: SESSION_SECONDS,
  };
}
export async function boundedBody(request: Request, max: number) {
  if (Number(request.headers.get("content-length")) > max)
    throw new Error("BODY_LIMIT");
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > max) {
        await reader.cancel();
        throw new Error("BODY_LIMIT");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const out = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.length;
  }
  return out;
}
