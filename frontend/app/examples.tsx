/** Before/after example videos and a "How it works" list, shown under each feature's form. */

import { useId, type ReactNode } from "react";

// #t=0.1 makes browsers paint the first frame instead of a black box before play.

type Clip = { src?: string; label: string; caption: string; vertical?: boolean; message?: string };

function ExampleVideo({ clip }: { clip: Clip }) {
  const captionId = useId();
  const frame = `mx-auto w-full overflow-hidden rounded-3xl border border-line bg-panel ${
    clip.vertical ? "aspect-[9/16] max-w-xs" : "aspect-video"
  }`;
  return (
    <figure className="space-y-2">
      <figcaption className="flex items-baseline justify-between gap-3">
        <span className="example-title headline text-2xl">{clip.label}</span>
        <span id={captionId} className="text-right text-sm text-muted">{clip.caption}</span>
      </figcaption>
      {clip.message && (
        <p className="action-fill ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 text-sm font-semibold shadow-[0_0_24px_color-mix(in_srgb,var(--accent-glow)_35%,transparent)]">
          {clip.message}
        </p>
      )}
      {clip.src ? (
        <video
          src={`${clip.src}#t=0.1`} controls muted playsInline preload="metadata"
          aria-label={`${clip.label} example video`} aria-describedby={captionId}
          className={`${frame} video-frame object-contain`}
        />
      ) : (
        <div className={`${frame} stripes grid place-items-center text-sm text-muted`}>Example video coming soon</div>
      )}
    </figure>
  );
}

export function ExampleSection({
  before, after, steps, stepsTitle = "What happens to your video.",
}: { before: Clip; after: Clip | ReactNode; steps: string[]; stepsTitle?: string }) {
  return (
    <section aria-labelledby="example-heading" className="example-section mx-auto mt-8 max-w-xl space-y-10 border-t border-line pt-10">
      <div className="example-comparison space-y-6">
        <div className="space-y-2">
          <p className="eyebrow">Example</p>
          <h2 id="example-heading" className="example-title headline text-4xl">See it on a real clip.</h2>
        </div>
        <ExampleVideo clip={before} />
        <div aria-hidden className="example-direction text-center text-2xl text-accent">↓</div>
        {isClip(after) ? <ExampleVideo clip={after} /> : after}
      </div>
      <div className="space-y-4">
        <div className="space-y-2">
          <p className="eyebrow">How it works</p>
          <h2 className="example-title headline text-4xl">{stepsTitle}</h2>
        </div>
        <ol className="space-y-3">
          {steps.map((s, i) => (
            <li key={i} className="surface-card flex gap-3 p-4 text-sm">
              <span className="example-title headline text-2xl leading-none text-accent">{i + 1}</span>
              <span className="text-fg/90">{s}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function isClip(x: Clip | ReactNode): x is Clip {
  return typeof x === "object" && x !== null && "label" in x && "caption" in x;
}
