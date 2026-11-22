"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import demoAssets from "@/lib/demo-assets.json";
import { demoDescriptions } from "@/lib/demo-descriptions";
import { ChevronIcon, PauseIcon, PlayIcon } from "./ui";

const features = [
  { id: "autocut", title: "Auto-Cut", description: "Trim a match to its rallies.", demo: "/jobs/demo-autocut", clip: "autocut-after" },
  { id: "coach", title: "Coach", description: "Get feedback on your match.", demo: "/jobs/demo-coach", clip: "coach-after-breakdown" },
  { id: "breakdown", title: "Technique Breakdown", description: "See what makes a stroke work.", demo: "/jobs/demo-breakdown", clip: "breakdown-after" },
  { id: "equipment", title: "Equipment", description: "Find rubber for your game.", demo: "/rubbers?demo=1" },
  { id: "match", title: "Pro styles", description: "Compare your swing with the pros.", demo: "/jobs/demo-match", clip: "match-after" },
] as const;

const motionQuery = "(prefers-reduced-motion: reduce)";
function subscribeToMotion(onChange: () => void) {
  const query = window.matchMedia(motionQuery);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function Poster({ clip }: { clip: string }) {
  // Sized WebP frames come from the existing cached demos.
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={`/home/${clip}.webp`} alt="" loading="lazy" decoding="async" />;
}

type FeatureId = (typeof features)[number]["id"];

export function FeatureGrid({ equipment }: { equipment: { spin?: string; speed?: string } }) {
  const reduceMotion = useSyncExternalStore(subscribeToMotion, () => window.matchMedia(motionQuery).matches, () => false);
  const [active, setActive] = useState<{ id: FeatureId; hover: boolean }>();
  const gridRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    const grid = gridRef.current;
    if (!grid || !window.IntersectionObserver) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) setActive(undefined);
    });
    observer.observe(grid);
    return () => observer.disconnect();
  }, []);

  return (
    <section aria-labelledby="home-features-title" className="home-section" data-home-enter data-ball-space>
      <h2 id="home-features-title" className="section-title home-section-title">Explore TTSkill</h2>
      <ul ref={gridRef} className="home-features" data-ball-space>
        {features.map((feature) => {
          const playing = !reduceMotion && active?.id === feature.id;
          return (
            <li key={feature.id} className="home-feature surface-card home-lift"
              onPointerEnter={(event) => {
                if (event.pointerType === "mouse" && !window.matchMedia(motionQuery).matches) setActive({ id: feature.id, hover: true });
              }}
              onPointerLeave={() => setActive((current) => current?.id === feature.id && current.hover ? undefined : current)}>
              <div className="home-feature-media">
                {feature.id === "equipment" ? (
                  <div className="home-equipment-preview" aria-hidden>
                    <span className="home-rubber-sheet" />
                    <div className="home-equipment-picks" data-playing={playing}>
                      <div><span>Spin pick</span><strong>{equipment.spin}</strong></div>
                      <div><span>Speed pick</span><strong>{equipment.speed}</strong></div>
                    </div>
                  </div>
                ) : <>
                  <Poster clip={feature.clip} />
                  {playing && <video src={`/home/${feature.clip}.mp4`} autoPlay loop muted playsInline aria-hidden />}
                </>}
                <button type="button" className="home-feature-play" aria-label={`${feature.title} preview`} aria-pressed={playing}
                  onClick={() => {
                    if (!window.matchMedia(motionQuery).matches) setActive(playing ? undefined : { id: feature.id, hover: false });
                  }}>
                  <span>{playing ? <PauseIcon /> : <PlayIcon />}</span>
                </button>
              </div>
              <div className="home-feature-copy">
                <h3 className="section-title text-lg">{feature.title}</h3>
                <p className="text-sm text-muted">{feature.description}</p>
                <Link href={feature.demo} prefetch={false} className="home-text-link" aria-label={`Try it: ${feature.title}`}>
                  Try it <ChevronIcon className="size-4 -rotate-90" />
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

type DemoMode = "before" | "after";
const demos = [
  { id: "autocut", title: "Match highlights", before: "A phone recording of two players during points and the gaps between them." },
  { id: "breakdown", title: "Stroke breakdown", before: "Ma Long practices a forehand loop at full speed." },
] as const;

function DemoPlayer({ demo, mode }: { demo: (typeof demos)[number]; mode: DemoMode }) {
  const [started, setStarted] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const clip = `${demo.id}-${mode}`;
  const src = mode === "before" ? `/examples/${clip}.mp4` : demoAssets[demo.id].url;
  const description = mode === "before" ? demo.before : demoDescriptions[demo.id];

  function play() {
    const player = videoRef.current;
    if (!player) return;
    player.src = src;
    setStarted(true);
    void player.play().catch(() => player.focus());
    requestAnimationFrame(() => player.focus({ preventScroll: true }));
  }

  return (
    <figure className="home-demo surface-card">
      <figcaption className="home-demo-title section-title text-lg">{demo.title}</figcaption>
      <div className="home-demo-media">
        {!started && <button type="button" className="home-demo-start" aria-label={`Play ${demo.title.toLowerCase()} ${mode}`} onClick={play}>
          <Poster clip={clip} />
          <span><PlayIcon className="size-6" /></span>
        </button>}
        <video ref={videoRef} controls playsInline preload="none" hidden={!started} tabIndex={0}
          aria-label={`${demo.title}, ${mode}`} aria-describedby={`${clip}-description`} />
      </div>
      <p id={`${clip}-description`} className="sr-only">{description}</p>
    </figure>
  );
}

export function DemoStrip() {
  const [mode, setMode] = useState<DemoMode>("after");

  return (
    <section aria-labelledby="home-demos-title" className="home-section" data-home-enter data-ball-space>
      <div className="home-section-heading">
        <h2 id="home-demos-title" className="section-title">See it in action</h2>
        <div className="home-demo-toggle" role="group" aria-label="Demo version">
          {(["before", "after"] as const).map((option) => (
            <button key={option} type="button" aria-pressed={mode === option} onClick={() => setMode(option)}>{option}</button>
          ))}
        </div>
      </div>
      <div className="home-demos" data-ball-space>
        {demos.map((demo) => <DemoPlayer key={`${demo.id}-${mode}`} demo={demo} mode={mode} />)}
      </div>
    </section>
  );
}
