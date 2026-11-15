import Link from "next/link";
import { HeroVideo } from "./hero-video";
import { ArrowIcon } from "./ui";

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
    <div className="space-y-12">
      <section className="grid items-center gap-8 lg:grid-cols-[1fr_auto] lg:gap-16">
        <div className="space-y-4">
          <p className="eyebrow">AI coaching for table tennis</p>
          <h1 className="headline text-[3.4rem] sm:text-8xl">
            Learn the stroke.<br /><span className="text-accent">Keep the rally.</span>
          </h1>
          <p className="max-w-md text-lg text-muted">
            Break down how the pros swing, and turn your own matches into highlight reels. Straight from your phone.
          </p>
        </div>
        <HeroVideo />
      </section>
      <section className="grid gap-3 sm:grid-cols-2">
        {tools.map((t, i) => (
          <Link
            key={t.href} href={t.href}
            className="group relative flex flex-col gap-3 overflow-hidden rounded-3xl border border-line bg-panel p-6 transition hover:border-accent/60 active:scale-[.99]"
          >
            <span aria-hidden className="headline pointer-events-none absolute -top-3 -right-1 text-[7rem] text-white/[0.04]">
              0{i + 1}
            </span>
            <span className="eyebrow">{t.tag}</span>
            <span className="headline text-4xl">{t.title}</span>
            <span className="text-muted">{t.body}</span>
            <span className="mt-auto inline-flex items-center gap-2 pt-2 font-bold uppercase tracking-wide text-accent">
              {t.cta} <ArrowIcon className="size-5 transition group-hover:translate-x-1" />
            </span>
          </Link>
        ))}
      </section>
      <section className="flex flex-wrap items-center gap-2 text-sm">
        <span className="mr-1 text-muted">See it on a real match:</span>
        <Link href="/jobs/demo-breakdown" className="rounded-full border border-line px-4 py-2 font-semibold hover:border-accent">
          Forehand breakdown
        </Link>
        <Link href="/jobs/demo-autocut" className="rounded-full border border-line px-4 py-2 font-semibold hover:border-accent">
          Highlight reel
        </Link>
      </section>
    </div>
  );
}
