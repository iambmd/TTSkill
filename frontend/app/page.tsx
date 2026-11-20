import Link from "next/link";
import { HeroVideo } from "./hero-video";
import { ArrowIcon, secondaryButtonClass } from "./ui";

const tools = [
  {
    href: "/coach",
    tag: "TT Coach",
    title: "Just ask",
    body: "One request, one video: \"show my best rallies and fix my forehand\". The coach plans it, runs the tools and shows its work.",
    cta: "Ask the coach",
  },
  {
    href: "/breakdown",
    tag: "Technique Breakdown",
    title: "Copy the pros",
    body: "Upload a clip of your favorite player, pick a stroke, and get a step-by-step coaching video.",
    cta: "Break down a stroke",
  },
  {
    href: "/match",
    tag: "Find my pro match",
    title: "Who do you play like?",
    body: "Film your swing. We match your height, build and stroke to the closest pros and show where your form differs.",
    cta: "Find my match",
  },
  {
    href: "/autocut",
    tag: "Match Auto-Cut",
    title: "Keep every rally",
    body: "Upload your match. We hear every ball contact and cut out the dead time, or keep just your best rallies.",
    cta: "Cut my match",
  },
];

export default function Home() {
  return (
    <div className="training-page space-y-12">
      <section className="grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)] lg:gap-12">
        <div className="page-intro space-y-3">
          <p className="eyebrow">AI coaching for table tennis</p>
          <h1 className="headline text-[3.4rem] sm:text-8xl">
            Learn the stroke.<br />Keep the rally.
          </h1>
          <p className="text-muted">
            Break down how the pros swing, and turn your own matches into highlight reels. Straight from your phone.
          </p>
        </div>
        <HeroVideo />
      </section>
      <section className="grid gap-4 border-t border-line pt-8 sm:grid-cols-2">
        {tools.map((t) => (
          <Link
            key={t.href} href={t.href}
            className="surface-card group flex min-w-0 flex-col gap-2.5 p-5 transition hover:border-accent motion-safe:active:scale-[.99]"
          >
            <span className="eyebrow">{t.tag}</span>
            <span className="section-title text-2xl">{t.title}</span>
            <span className="text-muted">{t.body}</span>
            <span className="mt-auto inline-flex items-center gap-2 pt-2 font-bold uppercase tracking-wide text-accent">
              {t.cta} <ArrowIcon className="size-5 transition group-hover:translate-x-1" />
            </span>
          </Link>
        ))}
      </section>
      <section className="flex flex-wrap items-center gap-2 text-sm">
        <span className="mr-1 text-muted">See it on a real match:</span>
        <Link href="/jobs/demo-breakdown" className={secondaryButtonClass}>
          Forehand breakdown
        </Link>
        <Link href="/jobs/demo-autocut" className={secondaryButtonClass}>
          Highlight reel
        </Link>
      </section>
    </div>
  );
}
