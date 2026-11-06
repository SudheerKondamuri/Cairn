import { Google, GitHub } from "antarctic";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { appOrigin, cookieOptions, SESSION_COOKIE } from "@/lib/auth";
export const runtime = "nodejs";
export async function GET(
  request: Request,
  { params }: { params: Promise<{ provider: string }> },
) {
  const { provider } = await params;
  const jar = await cookies();
  const stored = jar.get("cairn_oauth")?.value;
  jar.set("cairn_oauth", "", { path: "/api/auth", maxAge: 0 });
  try {
    const saved = JSON.parse(stored || "{}");
    const url = new URL(request.url),
      code = url.searchParams.get("code"),
      state = url.searchParams.get("state");
    if (
      !code ||
      !state ||
      saved.state !== state ||
      saved.provider !== provider ||
      !["google", "github"].includes(provider)
    )
      throw new Error("Invalid callback");
    const redirect = `${appOrigin()}/api/auth/${provider}/callback`;
    const tokens =
      provider === "google"
        ? await new Google(
            process.env.GOOGLE_CLIENT_ID!,
            process.env.GOOGLE_CLIENT_SECRET!,
            redirect,
          ).validateAuthorizationCode(code, saved.verifier)
        : await new GitHub(
            process.env.GITHUB_CLIENT_ID!,
            process.env.GITHUB_CLIENT_SECRET!,
            redirect,
          ).validateAuthorizationCode(code);
    const profileResponse = await fetch(
      provider === "google"
        ? "https://openidconnect.googleapis.com/v1/userinfo"
        : "https://api.github.com/user",
      {
        headers: {
          Authorization: `Bearer ${tokens.accessToken()}`,
          "User-Agent": "Cairn",
          Accept: "application/json",
        },
        cache: "no-store",
        signal: AbortSignal.timeout(15000),
      },
    );
    if (!profileResponse.ok) throw new Error("Profile unavailable");
    const profile = await profileResponse.json();
    const subject = provider === "google" ? profile.sub : profile.id;
    if (
      (typeof subject !== "string" && typeof subject !== "number") ||
      !String(subject)
    )
      throw new Error("Invalid identity");
    const session = await fetch(
      new URL("/api/web/sessions", process.env.CAIRN_API_URL!),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Cairn-API-Key": process.env.CAIRN_API_KEY!,
        },
        body: JSON.stringify({ provider, subject: String(subject) }),
        cache: "no-store",
        signal: AbortSignal.timeout(15000),
      },
    );
    if (!session.ok) throw new Error("Account unavailable");
    const { token } = await session.json();
    const response = NextResponse.redirect(new URL("/operator", appOrigin()));
    response.cookies.set(SESSION_COOKIE, token, cookieOptions());
    response.headers.set("Cache-Control", "no-store");
    return response;
  } catch {
    return NextResponse.redirect(
      new URL("/operator/sign-in?error=signin", appOrigin()),
    );
  }
}
