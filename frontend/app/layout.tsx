import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "TTSkill",
  description: "AI technique breakdowns and automatic match highlights for table tennis.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <header className="border-b border-white/10">
          <nav className="mx-auto flex max-w-3xl items-center gap-6 px-4 py-4 text-sm">
            <Link href="/" className="text-lg font-bold tracking-tight">
              TT<span className="text-accent">Skill</span>
            </Link>
            <Link href="/breakdown" className="text-white/70 hover:text-white">Technique Breakdown</Link>
            <Link href="/autocut" className="text-white/70 hover:text-white">Match Auto-Cut</Link>
          </nav>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-10">{children}</main>
      </body>
    </html>
  );
}
