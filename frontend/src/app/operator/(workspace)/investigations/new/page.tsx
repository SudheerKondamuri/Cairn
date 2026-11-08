import { NewInvestigation } from "@/components/new-investigation";
import { localAccessEnabled } from "@/lib/auth";

export const metadata = { title: "New investigation · Cairn" };

export default async function Page() {
  const isLocal = await localAccessEnabled();
  return <NewInvestigation isLocal={isLocal} />;
}
