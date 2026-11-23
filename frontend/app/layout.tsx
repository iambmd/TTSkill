import type { Metadata, Viewport } from "next";
import { Barlow, Barlow_Condensed } from "next/font/google";
import { SiteHeader } from "./site-header";

// Runs in <head> before paint so a saved light choice never flashes dark first. Key matches theme-toggle.tsx.
const themeScript = `try{if(localStorage.getItem("ttskill-theme")==="light")document.documentElement.dataset.theme="light"}catch(e){}`;
import "./globals.css";

const barlow = Barlow({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-barlow" });
const condensed = Barlow_Condensed({
  subsets: ["latin"], weight: ["700", "800"], style: ["normal", "italic"], variable: "--font-barlow-condensed",
});

export const metadata: Metadata = {
  title: "TTSkill",
  description: "AI technique breakdowns and automatic match highlights for table tennis.",
  icons: { icon: { url: "/paddle-cursor.svg", type: "image/svg+xml" } },
};

export const viewport: Viewport = {
  themeColor: "#07090d",
  colorScheme: "dark",
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // The theme script sets data-theme before React hydrates, hence suppressHydrationWarning.
    <html lang="en" className={`${barlow.variable} ${condensed.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-dvh font-sans antialiased">
        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-panel focus:px-4 focus:py-3 focus:font-semibold focus:text-fg">
          Skip to main content
        </a>
        <SiteHeader />
        <main id="main-content" tabIndex={-1} className="mx-auto max-w-5xl px-4 pt-6 pb-16 sm:pt-10">{children}</main>
      </body>
    </html>
  );
}
