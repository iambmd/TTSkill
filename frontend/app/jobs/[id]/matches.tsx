/** The pro-match cards, best match first, in the order the backend ranked them. */
import { useFormatter, useTranslations } from "next-intl";
import type { ProMatch } from "@/lib/submit";
import { EnglishOnly, useEnglishBlock } from "../../english-only";
import { Warning, strokeName } from "../../ui";

/** cached: a saved demo, whose notes are English whatever the page's language. */
export function Matches({ matches, stroke, cached = false }: { matches: ProMatch[]; stroke?: string; cached?: boolean }) {
  const t = useTranslations();
  const format = useFormatter();
  const english = useEnglishBlock(cached);
  const pct = (n: number) => format.number(n / 100, { style: "percent" });
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="eyebrow">{t("matches.title")}</h2>
        {cached && matches.some((m) => m.differences.length) && <EnglishOnly />}
      </div>
      <ol className="space-y-2">
        {matches.map((m, i) => (
          <li key={m.id} className="surface-card p-4">
            <div className="flex items-start gap-4">
              <span className="stat text-3xl leading-none text-accent">{String(i + 1).padStart(2, "0")}</span>
              <div className="min-w-0 flex-1">
                <p className="text-lg font-bold">{m.name}</p>
                <p className="text-sm text-muted">
                  {[m.country, t("common.cm", { value: m.height_cm }),
                    m.bat_hand === "left" || m.bat_hand === "right" ? t(`hands.${m.bat_hand}Handed`) : m.bat_hand,
                    m.grip && (m.grip === "shakehand" || m.grip === "penhold" ? t(`grips.${m.grip}`) : m.grip)].filter(Boolean).join(" · ")}
                </p>
              </div>
              <div className="text-right">
                <p className="stat text-3xl text-accent">{pct(m.score)}</p>
                <p className="text-[0.65rem] font-bold uppercase tracking-widest text-muted">{t("matches.bodyMatch")}</p>
              </div>
            </div>
            {m.form_score !== null && (
              <div className="mt-3">
                <div className="flex justify-between text-xs font-bold uppercase tracking-widest text-muted">
                  <span>{t("matches.swingMatch")}</span><span className="tabular-nums">{pct(m.form_score)}</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${m.form_score}%` }} />
                </div>
              </div>
            )}
            {m.differences.length > 0 && (
              <ul className="mt-3 space-y-1 text-sm" {...english}>
                {m.differences.map((d) => <li key={d} className="flex gap-2"><span aria-hidden className="text-accent">→</span>{d}</li>)}
              </ul>
            )}
            {!m.breakdown && m.form_score === null && (
              <p className="mt-3 text-sm text-muted">
                {stroke
                  ? t("matches.noClip", { stroke: strokeName(t, stroke).toLowerCase(), name: m.name.split(" ").at(-1)! })
                  : t("matches.noMatchingClip", { name: m.name.split(" ").at(-1)! })}
              </p>
            )}
            {m.warnings?.map((w) => <Warning key={w} className="mt-3"><span {...english}>{w}</span></Warning>)}
          </li>
        ))}
      </ol>
    </section>
  );
}
