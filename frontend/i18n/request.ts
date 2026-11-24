/** next-intl without locale routes: the locale comes from the cookie or the browser's languages. */
import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { LOCALE_COOKIE, negotiate } from "@/lib/locale";
import { MESSAGES } from "@/lib/messages";

export default getRequestConfig(async () => {
  const locale = negotiate((await cookies()).get(LOCALE_COOKIE)?.value, (await headers()).get("accept-language"));
  return { locale, messages: MESSAGES[locale] };
});
