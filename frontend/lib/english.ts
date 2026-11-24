/** English messages for lib code called without a translator (API routes' defaults, tests).
 * Only en.json is imported, so client bundles don't carry the other locales. */
import { createTranslator } from "next-intl";
import en from "../messages/en.json";
import type { Tr } from "./messages";

export const english = (namespace: string): Tr =>
  createTranslator({ locale: "en", messages: en as Record<string, unknown>, namespace: namespace as never }) as unknown as Tr;
