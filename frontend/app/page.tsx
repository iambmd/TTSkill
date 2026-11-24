import Link from "next/link";
import { useTranslations } from "next-intl";
import { recommend, type Level, type Style } from "@/lib/rubbers";
import { HomeGear } from "./home-gear";
import { DemoStrip, FeatureGrid } from "./home-media";
import { HomeMotion } from "./home-motion";
import { MatchUpload } from "./match-upload";
import "./home.css";

const footerLinks = [
  ["/", "home"], ["/coach", "coach"], ["/breakdown", "breakdown"], ["/match", "match"],
  ["/autocut", "autocut"], ["/rubbers", "rubbers"], ["/pros", "pros"],
] as const;

function equipmentPreviewName(style: Style, level: Level) {
  const { results } = recommend(style, "inverted", level);
  return (results.find((rubber) => rubber.buyLinks?.length) ?? results[0])?.name;
}

const equipmentPreview = {
  spin: equipmentPreviewName("spin", "intermediate"),
  speed: equipmentPreviewName("speed", "beginner"),
};

export default function Home() {
  const t = useTranslations("home");
  return (
    <div className="home-page">
      <HomeMotion />
      <section aria-labelledby="match-title" className="home-hero">
        <div className="home-hero-copy">
          <h1 id="match-title" className="headline">{t("title")}</h1>
          <p className="text-muted">{t("intro")}</p>
        </div>
        <MatchUpload />
      </section>
      <HomeGear />
      <FeatureGrid equipment={equipmentPreview} />
      <DemoStrip />
      <footer className="home-footer">
        <Link href="/" prefetch={false} className="headline text-2xl">TT<span className="text-accent">Skill</span></Link>
        <nav aria-label={t("footer")} className="flex flex-wrap items-center gap-x-5 gap-y-1">
          {footerLinks.map(([href, label]) => (
            <Link key={href} href={href} prefetch={false} className="inline-flex min-h-11 items-center text-sm font-semibold hover:text-accent">{t(`footerLinks.${label}`)}</Link>
          ))}
        </nav>
      </footer>
    </div>
  );
}
