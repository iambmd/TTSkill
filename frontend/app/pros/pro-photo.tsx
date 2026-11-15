"use client";

import { useEffect, useState } from "react";

type Photo = { src: string; page: string };

// Wikipedia's REST summary sends CORS headers, so the browser fetches the lead photo (hosted on
// Wikimedia Commons) directly. Only accept pages that describe a table tennis player, so a
// disambiguation page or a namesake never shows the wrong face.
async function findPhoto(titles: string[]): Promise<Photo | null> {
  for (const t of titles) {
    try {
      const res = await fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(t.replaceAll(" ", "_"))}`);
      if (!res.ok) continue;
      const s = await res.json();
      const text = `${s.description ?? ""} ${s.extract ?? ""}`.toLowerCase();
      if (s.type === "standard" && s.thumbnail?.source && text.includes("table tennis")) {
        return { src: s.thumbnail.source, page: s.content_urls?.desktop?.page ?? `https://en.wikipedia.org/wiki/${t}` };
      }
    } catch {
      // offline or blocked: fall back to initials
    }
  }
  return null;
}

const initials = (name: string) => name.split(" ").map((w) => w[0]).slice(0, 2).join("");

export function ProPhoto({ name, wiki }: { name: string; wiki: string[] }) {
  const [photo, setPhoto] = useState<Photo | null>(null);
  useEffect(() => {
    let live = true;
    findPhoto(wiki).then((p) => live && setPhoto(p));
    return () => { live = false; };
  }, [wiki]);

  return (
    <figure className="shrink-0 text-center">
      <div className="grid size-20 place-items-center overflow-hidden rounded-2xl border border-line bg-white/[0.04]">
        {photo
          // eslint-disable-next-line @next/next/no-img-element -- remote Commons thumbnail, no need for next/image here
          ? <img src={photo.src} alt={name} className="size-full object-cover object-top" loading="lazy" />
          : <span className="headline text-3xl text-white/40">{initials(name)}</span>}
      </div>
      {photo && (
        <figcaption className="mt-1 text-[0.6rem] text-muted">
          <a href={photo.page} target="_blank" rel="noreferrer" className="underline">Wikipedia</a>
        </figcaption>
      )}
    </figure>
  );
}

export type ProductImage = { src: string; page: string };

const kindOf = (r: string) => (/pips/i.test(r) ? "pips" : /anti/i.test(r) ? "anti" : "inverted");

/** Drawn fallback for when there is no product photo or it fails to load. */
function Drawn({ part, name }: { part: "blade" | "fh" | "bh"; name: string }) {
  if (part === "blade") {
    return (
      <svg viewBox="0 0 60 80" className="h-20" aria-hidden>
        <ellipse cx="30" cy="30" rx="26" ry="28" fill="#c9965b" />
        <ellipse cx="30" cy="30" rx="20" ry="22" fill="none" stroke="#a87943" strokeWidth="1.5" />
        <rect x="24" y="54" width="12" height="24" rx="4" fill="#8a5a2b" />
      </svg>
    );
  }
  const kind = kindOf(name);
  return (
    <svg viewBox="0 0 60 80" className="h-20" aria-hidden>
      <ellipse cx="30" cy="30" rx="26" ry="28" fill={part === "fh" ? "#d6322f" : "#16181d"} stroke="rgb(255 255 255 / .25)" strokeWidth="1.5" />
      {kind === "pips" && Array.from({ length: 30 }, (_, i) => (
        <circle key={i} cx={10 + (i % 6) * 8} cy={10 + Math.floor(i / 6) * 9} r="1.6" fill="rgb(255 255 255 / .35)" />
      ))}
    </svg>
  );
}

function Item({ part, label, name, img }: { part: "blade" | "fh" | "bh"; label: string; name: string; img?: ProductImage }) {
  const [failed, setFailed] = useState(false);
  const photo = img && !failed;
  return (
    <figure className="flex min-w-0 flex-1 flex-col items-center gap-1.5">
      <div className="grid h-24 w-full place-items-center overflow-hidden rounded-xl bg-neutral-50 p-1">
        {photo
          // eslint-disable-next-line @next/next/no-img-element -- hotlinked retailer image
          ? <img src={img.src} alt={name} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} className="max-h-full max-w-full object-contain" />
          : <div className="grid size-full place-items-center rounded-lg bg-ink"><Drawn part={part} name={name} /></div>}
      </div>
      <figcaption className="text-[0.65rem] font-bold uppercase tracking-wide text-muted">
        {photo ? <a href={img.page} target="_blank" rel="noreferrer" className="underline decoration-white/30 hover:text-fg">{label}</a> : label}
      </figcaption>
    </figure>
  );
}

/** Blade, forehand, backhand in that order: the product photo, linked to its page, or a drawing. */
export function SetupStrip({ blade, fh, bh, images }: {
  blade: string; fh: string; bh: string; images: { blade?: ProductImage; fh?: ProductImage; bh?: ProductImage };
}) {
  return (
    <div className="flex items-center gap-1.5 rounded-2xl bg-white/[0.03] p-3">
      <Item part="blade" label="Blade" name={blade} img={images.blade} />
      <span aria-hidden className="text-muted">→</span>
      <Item part="fh" label="Forehand" name={fh} img={images.fh} />
      <span aria-hidden className="text-muted">→</span>
      <Item part="bh" label="Backhand" name={bh} img={images.bh} />
    </div>
  );
}
