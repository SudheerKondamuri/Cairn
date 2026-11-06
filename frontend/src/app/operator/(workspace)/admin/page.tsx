import { notFound } from "next/navigation";
import { currentAccount } from "@/lib/auth";
import { AdminConsole } from "@/components/admin-console";
export default async function Page() {
  if (!(await currentAccount())?.admin) notFound();
  return <AdminConsole />;
}
