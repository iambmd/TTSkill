"use client";

import Link from "next/link";
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
      <div className="relative overflow-hidden rounded-[2rem] border border-line bg-black shadow-[0_30px_80px_-30px_rgb(255_107_44/0.5)]">
        <video
          ref={ref} src="/demo/breakdown.mp4#t=0.001" muted loop playsInline preload="auto"
          onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
          className="block aspect-[9/16] w-full object-cover"
        />
        <button
          type="button" onClick={toggle} aria-label={playing ? "Pause demo" : "Play demo"}
          className="absolute right-3 bottom-3 grid size-11 place-items-center rounded-full bg-black/60 text-neutral-50 backdrop-blur hover:bg-black/80"
        >
          {playing ? <PauseIcon /> : <PlayIcon />}
        </button>
      </div>
      <figcaption className="mt-3 flex items-center justify-between gap-3 text-sm">
        <span className="text-muted">Ma Long · forehand</span>
        <Link href="/jobs/demo-breakdown" className="inline-flex items-center gap-1 font-bold uppercase tracking-wide text-accent">
          Full breakdown <ArrowIcon className="size-4" />
        </Link>
      </figcaption>
    </figure>
  );
}
