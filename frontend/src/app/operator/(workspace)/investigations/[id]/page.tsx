import { notFound } from "next/navigation";
import { OperatorDetail } from "@/components/operator-detail";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^inv-[a-zA-Z0-9-]{1,100}$/.test(id)) notFound();
  return <OperatorDetail id={id} />;
}
