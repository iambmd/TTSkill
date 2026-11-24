import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, Be_Vietnam_Pro } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getTranslations } from "next-intl/server";
import { ClickBall } from "./click-ball";
import { SiteHeader } from "./site-header";

// Runs in <head> before paint so a saved light choice never flashes dark first. Key matches theme-toggle.tsx.
const themeScript = `try{if(localStorage.getItem("ttskill-theme")==="light")document.documentElement.dataset.theme="light"}catch(e){}`;
import "./globals.css";

// The vietnamese subset carries the stacked diacritics (ệ, ữ, ở...). Be Vietnam Pro is drawn for them.
const body = Be_Vietnam_Pro({
  subsets: ["latin", "vietnamese"], weight: ["400", "500", "600", "700"], variable: "--font-be-vietnam",
});
const condensed = Barlow_Condensed({
  subsets: ["latin", "vietnamese"], weight: ["600", "700"], style: ["normal", "italic"], variable: "--font-barlow-condensed",
});

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("metadata");
  return {
    title: t("title"),
    description: t("description"),
    icons: { icon: { url: "/paddle.svg", type: "image/svg+xml" } },
  };
}

export const viewport: Viewport = {
  themeColor: "#07090d",
  colorScheme: "dark",
  viewportFit: "cover",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const t = await getTranslations("layout");
  return (
    // The theme script sets data-theme before React hydrates, hence suppressHydrationWarning.
    <html lang={locale} className={`${body.variable} ${condensed.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-dvh font-sans antialiased">
        <NextIntlClientProvider>
          <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-panel focus:px-4 focus:py-3 focus:font-semibold focus:text-fg">
            {t("skip")}
          </a>
          <SiteHeader />
          <main id="main-content" tabIndex={-1} className="mx-auto max-w-5xl px-4 pt-6 pb-16 sm:pt-10">{children}</main>
          <ClickBall />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
