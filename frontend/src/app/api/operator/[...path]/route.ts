import { NextResponse } from "next/server";
import { boundedBody, sameOrigin, signedIn } from "@/lib/auth";
import { upstream, UpstreamError } from "@/lib/upstream";
import { isReport } from "@/lib/reports";
import { reportMarkdown, reportPdf } from "@/lib/export-report";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const id = /^inv-[a-zA-Z0-9-]{1,100}$/;
function failure(error: unknown) {
  return NextResponse.json(
    {
      error:
        error instanceof UpstreamError
          ? error.message
          : "The request could not be completed.",
    },
    {
      status: error instanceof UpstreamError ? error.status : 502,
      headers: { "Cache-Control": "no-store" },
    },
  );
}
export async function GET(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  if (!(await signedIn()))
    return NextResponse.json(
      { error: "Sign in to continue." },
      { status: 401 },
    );
  const { path } = await params;
  let target = "";
  if (path.length === 1 && ["me", "admin"].includes(path[0]))
    target = `/api/web/${path[0]}`;
  else if (path.length === 1 && path[0] === "ready") target = "/ready";
  else if (path.length === 1 && path[0] === "investigations") {
    const incoming = new URL(request.url).searchParams,
      query = new URLSearchParams();
    for (const key of ["q", "status", "cursor"])
      query.set(key, (incoming.get(key) || "").slice(0, 100));
    target = `/api/web/investigations?${query}`;
  } else if (
    path[0] === "investigations" &&
    id.test(path[1] || "") &&
    (path.length === 2 ||
      (path.length === 3 && ["report", "markdown", "pdf"].includes(path[2])))
  )
    target = `/api/web/investigations/${path[1]}`;
  if (!target)
    return NextResponse.json({ error: "Not found." }, { status: 404 });
  try {
    const response = await upstream(target),
      data = await response.json();
    if (path.length === 3) {
      if (!isReport(data.result))
        return NextResponse.json(
          { error: "Report is not available yet." },
          { status: 409 },
        );
      const format = path[2],
        extension =
          format === "report" ? "json" : format === "markdown" ? "md" : "pdf";
      const body =
        format === "report"
          ? JSON.stringify(data.result, null, 2)
          : format === "markdown"
            ? reportMarkdown(data.result)
            : new Uint8Array(await reportPdf(data.result));
      return new NextResponse(body, {
        headers: {
          "Content-Type":
            format === "pdf"
              ? "application/pdf"
              : format === "report"
                ? "application/json"
                : "text/markdown; charset=utf-8",
          "Content-Disposition": `attachment; filename="${path[1]}.${extension}"`,
          "Cache-Control": "no-store",
        },
      });
    }
    return NextResponse.json(data, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    return failure(error);
  }
}
export async function POST(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  if (!(await signedIn()))
    return NextResponse.json(
      { error: "Sign in to continue." },
      { status: 401 },
    );
  if (!sameOrigin(request))
    return NextResponse.json(
      { error: "Request origin is not allowed." },
      { status: 403 },
    );
  const { path } = await params;
  const submission = path.length === 1 && path[0] === "investigations";
  const accountAction =
    path.length === 1 && ["admin", "allowance-request"].includes(path[0]);
  const jobAction =
    path.length === 3 &&
    path[0] === "investigations" &&
    id.test(path[1]) &&
    ["cancel", "delete", "share", "revoke"].includes(path[2]);
  if (!submission && !accountAction && !jobAction)
    return NextResponse.json({ error: "Not found." }, { status: 404 });
  try {
    const bytes = await boundedBody(
      request,
      submission ? 11 * 1024 * 1024 : 4096,
    );
    const type = request.headers.get("content-type") || "application/json";
    if (submission && !type.startsWith("multipart/form-data"))
      return NextResponse.json(
        { error: "Use the investigation form." },
        { status: 400 },
      );
    const response = await upstream(`/api/web/${path.join("/")}`, {
      method: "POST",
      headers: {
        "Content-Type": type,
        "Idempotency-Key": request.headers.get("Idempotency-Key") || "",
      },
      body: bytes,
    });
    return NextResponse.json(await response.json(), {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    if (error instanceof Error && error.message === "BODY_LIMIT")
      return NextResponse.json(
        { error: "The submitted data exceeds the size limit." },
        { status: 413 },
      );
    return failure(error);
  }
}
