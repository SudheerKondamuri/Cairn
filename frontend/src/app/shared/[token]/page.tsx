import { notFound } from "next/navigation";
import { upstream, UpstreamError } from "@/lib/upstream";
import { isReport } from "@/lib/reports";
import { ReportView } from "@/components/report-view";
import { WorkspaceShell } from "@/components/workspace-shell";
export const dynamic = "force-dynamic";
export const metadata = {
  title: "Shared investigation · Cairn",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export default async function Page({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  if (!/^[A-Za-z0-9_-]{43}$/.test(token)) notFound();
  let report;
  try {
    report = await (await upstream(`/api/web/shared/${token}`)).json();
  } catch (e) {
    if (e instanceof UpstreamError && e.status === 404) notFound();
    throw e;
  }
  if (!isReport(report)) notFound();
  return (
    <WorkspaceShell>
      <p className="notice">
        Shared by its owner. This link may be revoked and expires with the
        report.
      </p>
      <ReportView
        report={report}
        title="Shared investigation"
        recorded={false}
        download={`/shared/${token}/download`}
      />
    </WorkspaceShell>
  );
}
