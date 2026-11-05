import type { Metadata } from "next";
import "@fontsource-variable/schibsted-grotesk";
import "@fontsource-variable/manrope";
import "./globals.css";
import "./workspace.css";

export const metadata: Metadata = {
  title: "Cairn — Security claims. Meet reality.",
  description:
    "An AI investigator that tests command-injection reports inside Celesto sandboxes and returns independently rechecked evidence. Explore a real recorded investigation.",
  openGraph: {
    title: "Cairn — Security claims. Meet reality.",
    description:
      "A real investigation. An isolated computer. Evidence you can inspect.",
    type: "website",
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: "try{document.documentElement.dataset.theme=localStorage.getItem('cairn-theme')==='dark'?'dark':'light'}catch{}" }} />
        {children}
      </body>
    </html>
  );
}
