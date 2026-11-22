import Link from "next/link";
import { gearQuizResults, HomeGear } from "./home-gear";
import { DemoStrip, FeatureGrid } from "./home-media";
import { HomeMotion } from "./home-motion";
import { MatchUpload } from "./match-upload";
import "./home.css";

const footerLinks = [
  ["/", "Home"], ["/coach", "Coach"], ["/breakdown", "Breakdown"], ["/match", "Pro Match"],
  ["/autocut", "Auto-Cut"], ["/rubbers", "Rubber Finder"], ["/pros", "Pro Setups"],
] as const;

export default function Home() {
  return (
    <div className="home-page" data-ball-space>
      <HomeMotion />
      <section aria-labelledby="match-title" className="home-hero" data-ball-space>
        <div className="home-hero-copy">
          <h1 id="match-title" className="headline">Highlights and coaching</h1>
          <p className="text-muted">Turn your match video into highlights and actionable coaching.</p>
        </div>
        <MatchUpload />
      </section>
      <HomeGear />
      <FeatureGrid equipment={{ spin: gearQuizResults.spin.intermediate, speed: gearQuizResults.speed.beginner }} />
      <DemoStrip />
      <footer className="home-footer" data-ball-space>
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
