/** Which language a request gets: the NEXT_LOCALE cookie, then Accept-Language, then English.
 * Routes stay unprefixed, so the locale never appears in a URL. */
export const LOCALES = ["en", "vi"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_COOKIE = "NEXT_LOCALE";

export const isLocale = (value: unknown): value is Locale => LOCALES.includes(value as Locale);

/** The best supported language in an Accept-Language header ("vi-VN,vi;q=0.9,en;q=0.8" -> "vi"). */
export function fromAcceptLanguage(header: string | null | undefined): Locale | null {
  const wanted = (header ?? "").split(",").map((part, i) => {
    const [tag, ...rest] = part.trim().split(";");
    const q = rest.map((r) => r.trim()).find((r) => r.startsWith("q="));
    return { lang: tag.trim().toLowerCase().split("-")[0], q: q ? Number(q.slice(2)) : 1, i };
  }).filter((w) => w.lang && Number.isFinite(w.q) && w.q > 0);
  wanted.sort((a, b) => b.q - a.q || a.i - b.i);
  return wanted.map((w) => w.lang).find(isLocale) ?? null;
}

export function negotiate(cookie: string | null | undefined, acceptLanguage: string | null | undefined): Locale {
  return isLocale(cookie) ? cookie : fromAcceptLanguage(acceptLanguage) ?? DEFAULT_LOCALE;
}

/** The locale of an API request, from its own headers (route handlers answer in the page's language). */
export function requestLocale(req: Request): Locale {
  const cookie = req.headers.get("cookie")?.split(";").map((c) => c.trim().split("="))
    .find(([name]) => name === LOCALE_COOKIE)?.[1];
  return negotiate(cookie && decodeURIComponent(cookie), req.headers.get("accept-language"));
}
