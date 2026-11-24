/** Renders a component inside next-intl's provider, as the root layout does, in a given locale. */
import { NextIntlClientProvider } from "next-intl";
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MESSAGES } from "@/lib/messages";
import type { Locale } from "@/lib/locale";

export function renderIntl(node: ReactNode, locale: Locale = "en"): string {
  return renderToStaticMarkup(createElement(NextIntlClientProvider, { locale, messages: MESSAGES[locale], timeZone: "UTC", children: node }));
}
