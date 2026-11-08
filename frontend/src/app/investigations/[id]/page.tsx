import { notFound } from "next/navigation";
import { published } from "@/lib/reports";
import { WorkspaceShell } from "@/components/workspace-shell";
import { ReportView } from "@/components/report-view";
import { signedIn, localAccessEnabled } from "@/lib/auth";
export function generateStaticParams() {
  return published.map((item) => ({ id: item.slug }));
}
export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const item = published.find((item) => item.slug === id);
  return {
    title: item
      ? `${item.title} ${item.version} · Cairn`
      : "Investigation not found · Cairn",
  };
}
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const item = published.find((item) => item.slug === id);
  if (!item) notFound();
  const isAuth = await signedIn();
  const isLocal = await localAccessEnabled();
  return (
    <WorkspaceShell operator={isAuth} local={isLocal}>
      <ReportView
        report={item.report}
        title={`${item.title} / ${item.version}`}
        download={`/evidence/${item.slug}.json`}
      />
    </WorkspaceShell>
  );
}
