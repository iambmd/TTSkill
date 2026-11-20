"use client";

import Link from "next/link";
import demoAssets from "@/lib/demo-assets.json";
import { useEffect, useRef, useState } from "react";
import { ArrowIcon, PauseIcon, PlayIcon } from "./ui";

/** Looping, muted demo clip for the landing page. Stays paused for reduced-motion users. */
export function HeroVideo() {
  const ref = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) ref.current?.play().catch(() => {});
  }, []);

  function toggle() {
    const v = ref.current;
    if (!v) return;
    if (v.paused) v.play().catch(() => {});
    else v.pause();
  }

  return (
    <figure className="mx-auto w-[min(100%,calc(62svh*9/16))] lg:w-[22rem]">
      <div className="video-frame relative overflow-hidden border">
        <video
          ref={ref} src={`${demoAssets.breakdown.url}#t=0.001`} muted loop playsInline preload="auto"
          onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
          className="block aspect-[9/16] w-full object-cover"
        />
        <button
          type="button" onClick={toggle} aria-label={playing ? "Pause demo" : "Play demo"}
          className="absolute right-3 bottom-3 grid size-11 place-items-center rounded-full bg-[var(--training-media)] text-[var(--training-on-action)] hover:text-ball"
        >
          {playing ? <PauseIcon /> : <PlayIcon />}
        </button>
      </div>
      <figcaption className="mt-3 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm">
        <span className="text-muted">Ma Long · forehand</span>
        <Link href="/jobs/demo-breakdown" className="inline-flex items-center gap-1 font-bold uppercase tracking-wide text-accent">
          Full breakdown <ArrowIcon className="size-4" />
        </Link>
      </figcaption>
    </figure>
  );
}
