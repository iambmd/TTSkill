"use client";

/** EN / VI beside the theme toggle. The choice lives in the NEXT_LOCALE cookie (no locale in
 * the URL), and a refresh re-renders the server parts in the new language. */
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useTransition } from "react";
import { LOCALE_COOKIE, LOCALES, type Locale } from "@/lib/locale";

export function LanguageToggle() {
  const t = useTranslations("language");
  const locale = useLocale();
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  function choose(next: Locale) {
    if (next === locale) return;
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
    document.documentElement.lang = next;
    startTransition(() => router.refresh());
  }

  return (
    <div role="group" aria-label={t("label")} aria-busy={pending}
      className="flex h-11 shrink-0 items-center rounded-full border border-line p-0.5 text-xs font-bold">
      {LOCALES.map((l) => (
        <button
          key={l} type="button" lang={l} aria-pressed={locale === l} aria-label={t(l)} onClick={() => choose(l)}
          className={`grid h-full min-w-9 place-items-center rounded-full px-2 uppercase tracking-wide transition ${locale === l ? "action-fill" : "text-muted hover:text-fg"}`}
        >
          {l}
        </button>
      ))}
    </div>
  );
}
