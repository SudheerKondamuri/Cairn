import { redirect } from "next/navigation";
import { signedIn, localAccessEnabled } from "@/lib/auth";
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
  if (!(await signedIn())) redirect("/operator/sign-in");
  return <WorkspaceShell operator local={await localAccessEnabled()}>{children}</WorkspaceShell>;
}
