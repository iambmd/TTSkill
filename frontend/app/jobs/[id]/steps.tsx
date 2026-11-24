/** The breakdown steps shown on Breakdown and Coach results. */
import { useTranslations } from "next-intl";
import type { Breakdown } from "@/lib/submit";
import { EnglishOnly, useEnglishBlock } from "../../english-only";

/** A breakdown's cards, drill and details. Coach passes drill={false} when its notes already hold the drill.
 * cached: a saved demo, whose text is English whatever the page's language. */
export function Steps({ b, drill = true, cached = false }: { b: Breakdown; drill?: boolean; cached?: boolean }) {
  const t = useTranslations("steps");
  const english = useEnglishBlock(cached);
  const facts: [string, string][] = [
    [t("grip"), b.grip], [t("stance"), b.stance], [t("swingPath"), b.swing_path],
    [t("contactPoint"), b.contact_point], [t("followThrough"), b.follow_through],
  ];
  return (
    <>
      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="eyebrow">{t("stepByStep")}</h2>
          {cached && <EnglishOnly />}
        </div>
        <ol className="space-y-2" {...english}>
          {b.steps.map((s, i) => (
            <li key={i} className="flex gap-4 surface-card p-4">
              <span className="stat text-3xl leading-none text-accent">{String(i + 1).padStart(2, "0")}</span>
              <div className="min-w-0 space-y-1">
                <p className="text-lg font-bold">{s.title}</p>
                {s.lines.map((l) => <p key={l} className="text-muted">{l}</p>)}
                {s.callouts?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {s.callouts.map((c) => (
                      <span key={c} className="rounded-md bg-accent/15 px-2 py-0.5 text-xs font-bold uppercase tracking-wide text-accent">{c}</span>
                    ))}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
        {b.recap && <p className="section-title text-xl text-muted" {...english}>{b.recap}</p>}
      </section>
      {drill && b.drill && (
        <section className="rounded-2xl border border-accent/40 bg-accent/10 p-4">
          <h2 className="eyebrow">{t("tryThis")}</h2>
          <p className="mt-1 text-lg font-semibold" {...english}>{b.drill}</p>
        </section>
      )}
      <section className="space-y-3">
        <h2 className="eyebrow">{t("details")}</h2>
        <dl className="divide-y divide-line surface-card">
          {facts.map(([k, v]) => (
            <div key={k} className="grid gap-1 px-4 py-3 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-4">
              <dt className="text-xs font-bold uppercase tracking-widest text-muted sm:pt-0.5">{k}</dt>
              <dd {...english}>{v}</dd>
            </div>
          ))}
        </dl>
      </section>
    </>
  );
}
