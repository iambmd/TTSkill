import Link from "next/link";
import { Nav } from "./nav";
import { ThemeToggle } from "./theme-toggle";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-ink pt-[env(safe-area-inset-top)] backdrop-blur-md">
      <nav aria-label="Site navigation" className="site-nav mx-auto flex h-14 max-w-5xl items-center gap-3 px-4">
        <ThemeToggle />
        <Link href="/" className="headline mr-auto flex min-h-11 shrink-0 items-center gap-2 text-2xl">
          <span aria-hidden className="size-3 rounded-full bg-ball shadow-[0_0_12px_2px_color-mix(in_srgb,var(--color-ball)_60%,transparent)]" />
          <span>TT<span className="text-accent">Skill</span></span>
        </Link>
        <Nav />
      </nav>
    </header>
  );
}
