import type { Metadata } from "next";
import "@fontsource-variable/schibsted-grotesk";
import "@fontsource-variable/manrope";
import "./globals.css";
import "./workspace.css";

export const metadata: Metadata = {
  title: "Cairn — Security Claim Verification",
  description:
    "Automated command-injection reproduction engine executing inside isolated Celesto sandboxes with independent proof-marker verification.",
  openGraph: {
    title: "Cairn — Security Claim Verification",
    description:
      "Automated command-injection reproduction engine executing inside isolated Celesto sandboxes with independent proof-marker verification.",
    type: "website",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "try{var t=localStorage.getItem('cairn-theme');var d=t?t==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;document.documentElement.dataset.theme=d?'dark':'light';}catch(e){}",
          }}
        />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
