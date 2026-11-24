/** Saved demo results were written in English (they come from one refresh run and are never
 * hand-edited), so outside English they say so instead of passing for a translation. */
import { useLocale, useTranslations } from "next-intl";

/** "English only" next to a cached result's AI text; nothing in English. */
export function EnglishOnly({ className = "" }: { className?: string }) {
  const locale = useLocale();
  const t = useTranslations("language");
  if (locale === "en") return null;
  return (
    <span title={t("englishOnlyHint")}
      className={`inline-flex shrink-0 items-center rounded-full border border-line px-2 py-0.5 text-[0.65rem] font-bold uppercase tracking-wide text-muted ${className}`}>
      {t("englishOnly")}
    </span>
  );
}

/** lang="en" for a cached English block, so screen readers switch voice on a Vietnamese page. */
export function useEnglishBlock(cached: boolean): { lang?: string } {
  const locale = useLocale();
  return cached && locale !== "en" ? { lang: "en" } : {};
}
