/** Locale-aware number formats shared by the gear pages. Prices are always US dollars. */
import type { useFormatter } from "next-intl";

type Format = ReturnType<typeof useFormatter>;

export const usd = (format: Format, value: number, whole = false) =>
  format.number(value, { style: "currency", currency: "USD", ...(whole ? { maximumFractionDigits: 0, minimumFractionDigits: 0 } : {}) });

/** A 0-10 rating with one decimal ("8.5", "8,5"). */
export const rating = (format: Format, value: number) =>
  format.number(value, { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** "$" in English, "US$" in Vietnamese: the symbol the locale writes next to a USD amount. */
export function usdSymbol(locale: string) {
  return new Intl.NumberFormat(locale, { style: "currency", currency: "USD" }).formatToParts(0)
    .find((p) => p.type === "currency")?.value ?? "$";
}
