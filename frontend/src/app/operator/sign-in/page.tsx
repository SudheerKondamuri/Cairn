import { redirect } from "next/navigation";
export const metadata = {
  title: "Workspace · Cairn",
  robots: { index: false, follow: false },
};
export default function Page() {
  redirect("/operator");
}
