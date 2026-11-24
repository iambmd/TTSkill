import Link from "next/link";
import { useTranslations } from "next-intl";
import { LanguageToggle } from "./language-toggle";
import { Nav } from "./nav";
import { ThemeToggle } from "./theme-toggle";

export function SiteHeader() {
  const t = useTranslations("header");
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-ink pt-[env(safe-area-inset-top)] backdrop-blur-md">
      <nav aria-label={t("siteNav")} className="site-nav mx-auto flex h-14 max-w-5xl items-center gap-2 px-4 sm:gap-3">
        <ThemeToggle />
        <LanguageToggle />
        <Link href="/" className="headline mr-auto flex min-h-11 shrink-0 items-center gap-2 text-2xl">
          <span aria-hidden className="size-3 rounded-full bg-ball shadow-[0_0_12px_2px_color-mix(in_srgb,var(--color-ball)_60%,transparent)]" />
          <span>TT<span className="text-accent">Skill</span></span>
        </Link>
        <Nav />
      </nav>
    </header>
  );
}
