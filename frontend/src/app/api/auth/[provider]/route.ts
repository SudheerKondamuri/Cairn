import { Google, GitHub, generateState, generateCodeVerifier } from "antarctic";
import { NextResponse } from "next/server";
import { appOrigin, configuredProviders } from "@/lib/auth";
export const runtime = "nodejs";
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ provider: string }> },
) {
  const { provider } = await params;
  const configured = configuredProviders();
  if ((provider !== "google" && provider !== "github") || !configured[provider])
    return NextResponse.json(
      { error: "This sign-in method is not configured." },
      { status: 503 },
    );
  const state = generateState(),
    verifier = generateCodeVerifier(),
    redirect = `${appOrigin()}/api/auth/${provider}/callback`;
  const url =
    provider === "google"
      ? await new Google(
          process.env.GOOGLE_CLIENT_ID!,
          process.env.GOOGLE_CLIENT_SECRET!,
          redirect,
        ).createAuthorizationURL(state, verifier, ["openid", "profile"])
      : new GitHub(
          process.env.GITHUB_CLIENT_ID!,
          process.env.GITHUB_CLIENT_SECRET!,
          redirect,
        ).createAuthorizationURL(state, []);
  const response = NextResponse.redirect(url);
  response.cookies.set(
    "cairn_oauth",
    JSON.stringify({ provider, state, verifier }),
    {
      httpOnly: true,
      secure: appOrigin().startsWith("https:"),
      sameSite: "lax",
      path: "/api/auth",
      maxAge: 600,
    },
  );
  response.headers.set("Cache-Control", "no-store");
  return response;
}
