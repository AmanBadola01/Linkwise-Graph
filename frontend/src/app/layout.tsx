import type { Metadata } from "next";
import "./globals.css";
import SiteNav from "@/components/site-nav";

export const metadata: Metadata = {
  title: "Linkwise-Graph",
  description: "Hybrid GraphRAG and vector retrieval",
  icons: {
    icon: [{ url: "/favicon.png", type: "image/png" }],
    apple: [{ url: "/favicon.png", type: "image/png" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        {/* Hero 44 fonts. Next drops the @import inside the section CSS, so they load here. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@125,700&family=Outfit:wght@400&family=Plus+Jakarta+Sans:wght@500&display=swap"
        />
      </head>
      <body>
        <SiteNav />
        {children}
      </body>
    </html>
  );
}
