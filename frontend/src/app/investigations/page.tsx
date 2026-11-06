import { WorkspaceShell } from "@/components/workspace-shell";
import { Catalog } from "@/components/catalog";
export const metadata = { title: "Investigations · Cairn" };
export default function Page() {
  return (
    <WorkspaceShell>
      <Catalog />
    </WorkspaceShell>
  );
}
