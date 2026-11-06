import { NextResponse } from "next/server";
import {
  currentAccount,
  cookieOptions,
  sameOrigin,
  SESSION_COOKIE,
  configuredProviders,
  localAccessEnabled,
} from "@/lib/auth";
import { upstream } from "@/lib/upstream";
export const runtime = "nodejs";
export async function GET() {
  const account = await currentAccount();
  return NextResponse.json(
    { authenticated: !!account, account, providers: configuredProviders() },
    { headers: { "Cache-Control": "no-store" } },
  );
}
export async function DELETE(request: Request) {
  if (!sameOrigin(request))
    return NextResponse.json(
      { error: "Request origin is not allowed." },
      { status: 403 },
    );
  if (await localAccessEnabled()) return NextResponse.json({error:"Local access does not require a session."},{status:409});
  try {
    await upstream("/api/web/sessions", { method: "DELETE" });
  } catch {
    return NextResponse.json(
      { error: "Sign-out could not be confirmed. Please try again." },
      { status: 503 },
    );
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.set(SESSION_COOKIE, "", { ...cookieOptions(), maxAge: 0 });
  return response;
}
