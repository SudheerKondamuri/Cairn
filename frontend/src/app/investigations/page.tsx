import { WorkspaceShell } from "@/components/workspace-shell";
import { Catalog } from "@/components/catalog";
import { signedIn, localAccessEnabled } from "@/lib/auth";

export const metadata = { title: "Investigations · Cairn" };

export default async function Page() {
  const isAuth = await signedIn();
  const isLocal = await localAccessEnabled();
  return (
    <WorkspaceShell operator={isAuth} local={isLocal}>
      <Catalog />
    </WorkspaceShell>
  );
}
