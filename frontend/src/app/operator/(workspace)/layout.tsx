import { WorkspaceShell } from "@/components/workspace-shell";
export const metadata = {
  title: "Your workspace · Cairn",
  robots: { index: false, follow: false },
};
export default async function Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <WorkspaceShell operator local>{children}</WorkspaceShell>;
}
