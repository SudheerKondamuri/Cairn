// Operator sessions and server configuration are evaluated for every request.
export const dynamic = "force-dynamic";
export const metadata = { robots: { index: false, follow: false } };
export default function OperatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
