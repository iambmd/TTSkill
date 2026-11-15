import type { Metadata, Viewport } from "next";
import { Barlow, Barlow_Condensed } from "next/font/google";
import Link from "next/link";
import { Nav } from "./nav";
import { ThemeToggle } from "./theme-toggle";

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
};

export const viewport: Viewport = {
  themeColor: "#07090d",
  colorScheme: "dark light",
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
        <header className="sticky top-0 z-30 border-b border-line bg-ink/80 pt-[env(safe-area-inset-top)] backdrop-blur-md">
          <nav className="mx-auto flex h-14 max-w-5xl items-center gap-3 px-4">
            <ThemeToggle />
            <Link href="/" className="headline mr-auto flex shrink-0 items-center gap-2 text-2xl">
              <span aria-hidden className="size-3 rounded-full bg-accent shadow-[0_0_12px_2px_rgb(255_107_44/0.6)]" />
              <span>TT<span className="text-accent">Skill</span></span>
            </Link>
            <Nav />
          </nav>
        </header>
        <main className="mx-auto max-w-5xl px-4 pt-6 pb-16 sm:pt-10">{children}</main>
      </body>
    </html>
  );
}
