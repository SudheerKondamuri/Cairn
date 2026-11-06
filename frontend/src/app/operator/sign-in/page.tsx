import { redirect } from "next/navigation";
import { configuredProviders, signedIn, localAccessEnabled } from "@/lib/auth";
import { SignIn } from "@/components/sign-in";
export const metadata = {
  title: "Sign in · Cairn",
  robots: { index: false, follow: false },
};
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  if ((await signedIn()) || (await localAccessEnabled())) redirect("/operator");
  return (
    <SignIn
      providers={configuredProviders()}
      error={!!(await searchParams).error}
    />
  );
}
