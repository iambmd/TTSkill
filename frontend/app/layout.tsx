import type { Metadata, Viewport } from "next";
import { Barlow, Barlow_Condensed } from "next/font/google";
import Link from "next/link";
import { Nav } from "./nav";
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
  colorScheme: "dark",
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${barlow.variable} ${condensed.variable}`}>
      <body className="min-h-dvh font-sans antialiased">
        <header className="sticky top-0 z-30 border-b border-line bg-ink/80 pt-[env(safe-area-inset-top)] backdrop-blur-md">
          <nav className="mx-auto flex h-14 max-w-5xl items-center justify-between gap-4 px-4">
            <Link href="/" className="headline flex items-center gap-2 text-2xl">
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
