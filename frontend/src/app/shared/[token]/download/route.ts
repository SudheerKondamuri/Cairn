import { NextResponse } from "next/server";
import { upstream, UpstreamError } from "@/lib/upstream";
export async function GET(
  _r: Request,
  { params }: { params: Promise<{ token: string }> },
) {
  const { token } = await params;
  if (!/^[A-Za-z0-9_-]{43}$/.test(token))
    return new NextResponse(null, { status: 404 });
  try {
    const data = await (await upstream(`/api/web/shared/${token}`)).json();
    return new NextResponse(JSON.stringify(data, null, 2), {
      headers: {
        "Content-Type": "application/json",
        "Content-Disposition": 'attachment; filename="cairn-report.json"',
        "Cache-Control": "no-store",
        "Referrer-Policy": "no-referrer",
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: "Report unavailable." },
      { status: e instanceof UpstreamError ? e.status : 503 },
    );
  }
}
