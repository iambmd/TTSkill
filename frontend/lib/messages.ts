/** Every UI string, per locale (messages/*.json), and a translator for code outside React:
 * API routes and the server job client answer in the request's language. */
import { createTranslator } from "next-intl";
import en from "../messages/en.json";
import vi from "../messages/vi.json";
import { requestLocale, type Locale } from "./locale";

export const MESSAGES = { en, vi } as const;

/** Plain `(key, values) => string`, the shape lib code takes so it stays free of React. */
export type Tr = (key: string, values?: Record<string, string | number>) => string;

export function translator(locale: Locale, namespace: string): Tr {
  return createTranslator({ locale, messages: MESSAGES[locale] as Record<string, unknown>, namespace: namespace as never }) as unknown as Tr;
}

/** An API route's messages, in the language of the page that called it (cookie, then Accept-Language). */
export function routeMessages(req: Request) {
  const locale = requestLocale(req);
  return {
    locale,
    v: translator(locale, "validation"),
    e: translator(locale, "errors"),
    offline: translator(locale, "offline")("analysis"),
  };
}
