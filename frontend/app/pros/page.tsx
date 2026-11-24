"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import Link from "next/link";
import { rubberBuyLinks } from "@/lib/buy-links";
import proBlades from "@/lib/pro-blades.json";
import data from "@/lib/pros.json";
import productData from "@/lib/product-images.json";
import { GearTabs } from "../gear-tabs";
import { BuyMenu } from "../buy-menu";
import { PageIntro, inputClass, labelClass, strokeFamily } from "../ui";
import { ProPhoto, SetupStrip, type ProductImage } from "./pro-photo";

type Pro = {
  name: string; country: string; grip: string; blade: string; fh: string; bh: string;
  sources: string[]; uncertain: boolean; note?: string; wiki: string[];
  img?: { blade?: string; fh?: string; bh?: string };
};
const PROS = data.players as Pro[];
const BLADE_ENTRIES = proBlades as Record<string, string>; // blade label -> slug, where /blades has that exact blade
const SOURCES = data.sources as Record<string, string>;
const PRODUCTS = productData.products as Record<string, ProductImage>;
const images = (p: Pro) => ({
  blade: p.img?.blade ? PRODUCTS[p.img.blade] : undefined,
  fh: p.img?.fh ? PRODUCTS[p.img.fh] : undefined,
  bh: p.img?.bh ? PRODUCTS[p.img.bh] : undefined,
});

// Accent-free lowercase so "szocs" finds Szőcs.
const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

type T = ReturnType<typeof useTranslations>;

/** "Shakehand (left-handed)" from the data, in the page's language. */
function gripText(grip: string, t: T) {
  const m = /^(Shakehand|Penhold)( \(left-handed\))?$/.exec(grip);
  if (!m) return grip;
  const name = t(`grips.${m[1].toLowerCase()}`);
  return m[2] ? t("pros.gripLeft", { grip: name }) : name;
}

const PARTS = [["blade", "blade"], ["forehand", "fh"], ["backhand", "bh"]] as const;

function ProCard({ p }: { p: Pro }) {
  const t = useTranslations();
  const note = p.note && (t.has(`pros.notes.${p.name}`) ? t(`pros.notes.${p.name}`) : p.note);
  return (
    <article className="surface-card min-w-0 space-y-4 p-5">
      <header className="flex items-start gap-4">
        <ProPhoto name={p.name} wiki={p.wiki} />
        <div className="min-w-0 flex-1">
          <h2 className="section-title text-2xl">{p.name}</h2>
          <p className="text-sm text-muted">{p.country} · {gripText(p.grip, t)}</p>
          {p.uncertain && (
            <span className="mt-2 inline-block rounded-full border border-accent/50 px-2.5 py-1 text-[0.65rem] font-bold uppercase tracking-wide text-accent">
              {t("pros.unconfirmed")}
            </span>
          )}
        </div>
      </header>
      <SetupStrip blade={p.blade} fh={p.fh} bh={p.bh} images={images(p)} />
      <dl className="grid gap-2 text-sm">
        {PARTS.map(([k, field]) => [k, p[field]] as const).map(([k, v]) => (
          <div key={k} className="flex gap-3 rounded-xl bg-white/[0.03] px-3 py-2.5">
            <dt className="w-20 shrink-0 text-xs font-bold uppercase tracking-wide text-muted">
              <span className={k === "blade" ? undefined : "stroke-label"} data-stroke={strokeFamily(k)}>{t(`pros.${k}`)}</span>
            </dt>
            <dd className="min-w-0 space-y-2 break-words">
              <p className="font-semibold">{v}</p>
              {k !== "blade" && <BuyMenu product={v} buyLinks={rubberBuyLinks(v)} />}
              {k === "blade" && Object.hasOwn(BLADE_ENTRIES, v) && (
                <Link href={`/blades/${BLADE_ENTRIES[v]}`} className="inline-block py-1 text-xs font-semibold text-accent underline underline-offset-2">{t("pros.bladeLink")}</Link>
              )}
            </dd>
          </div>
        ))}
      </dl>
      {note && <p className="text-xs text-muted">{note}</p>}
      <p className="text-xs text-muted">
        {t("pros.source")}{" "}
        {p.sources.map((s, i) => (
          <span key={s}>
            {i > 0 && ", "}
            {SOURCES[s].startsWith("http")
              ? <a href={SOURCES[s]} target="_blank" rel="noreferrer" className="underline hover:text-fg">{new URL(SOURCES[s]).hostname}</a>
              : s === "general" ? t("pros.sourceGeneral") : SOURCES[s]}
          </span>
        ))}
      </p>
    </article>
  );
}

export default function ProsPage() {
  const t = useTranslations("pros");
  const [q, setQ] = useState("");
  const query = norm(q);
  const hits = query ? PROS.filter((p) => norm(p.name).includes(query)) : PROS;

  return (
    <div className="space-y-7">
      <GearTabs active="pros" />
      <PageIntro
        eyebrow={t("eyebrow")}
        title={t("title")}
        body={t("body", { n: PROS.length })}
      />
      <div className="max-w-lg">
        <label htmlFor="pro-search" className={labelClass}>{t("player")}</label>
        <input
          id="pro-search" type="search" value={q} onChange={(e) => setQ(e.target.value)}
          placeholder={t("placeholder")} autoComplete="off" className={`${inputClass} h-12`}
        />
      </div>
      <section aria-live="polite" className="space-y-4">
        {hits.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-line p-8 text-center">
            <p className="section-title text-2xl">{t("notHere")}</p>
            <p className="mt-2 text-sm text-muted">{t("notHereHint", { n: PROS.length })}</p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">{hits.map((p) => <ProCard key={p.name} p={p} />)}</div>
        )}
      </section>
    </div>
  );
}
