import Link from "next/link";
import { recommend, type Level, type Style } from "@/lib/rubbers";
import { HomeGear } from "./home-gear";
import { DemoStrip, FeatureGrid } from "./home-media";
import { HomeMotion } from "./home-motion";
import { MatchUpload } from "./match-upload";
import "./home.css";

const footerLinks = [
  ["/", "Home"], ["/coach", "Coach"], ["/breakdown", "Breakdown"], ["/match", "Pro Match"],
  ["/autocut", "Auto-Cut"], ["/rubbers", "Rubber Finder"], ["/pros", "Pro Setups"],
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
  return (
    <div className="home-page">
      <HomeMotion />
      <section aria-labelledby="match-title" className="home-hero">
        <div className="home-hero-copy">
          <h1 id="match-title" className="headline">Highlights and coaching</h1>
          <p className="text-muted">Turn your match video into highlights and actionable coaching.</p>
        </div>
        <MatchUpload />
      </section>
      <HomeGear />
      <FeatureGrid equipment={equipmentPreview} />
      <DemoStrip />
      <footer className="home-footer">
        <Link href="/" prefetch={false} className="headline text-2xl">TT<span className="text-accent">Skill</span></Link>
        <nav aria-label="Footer" className="flex flex-wrap items-center gap-x-5 gap-y-1">
          {footerLinks.map(([href, label]) => (
            <Link key={href} href={href} prefetch={false} className="inline-flex min-h-11 items-center text-sm font-semibold hover:text-accent">{label}</Link>
          ))}
        </nav>
      </footer>
    </div>
  );
}
