/** The pro-match cards, best match first, in the order the backend ranked them. */
import type { ProMatch } from "@/lib/submit";
import { Warning } from "../../ui";

export function Matches({ matches, stroke }: { matches: ProMatch[]; stroke?: string }) {
  return (
    <section className="space-y-3">
      <h2 className="eyebrow">Your closest pros</h2>
      <ol className="space-y-2">
        {matches.map((m, i) => (
          <li key={m.id} className="rounded-2xl border border-line bg-panel p-4">
            <div className="flex items-start gap-4">
              <span className="headline text-4xl leading-none text-accent">{String(i + 1).padStart(2, "0")}</span>
              <div className="min-w-0 flex-1">
                <p className="text-lg font-bold">{m.name}</p>
                <p className="text-sm text-muted">
                  {[m.country, `${m.height_cm} cm`, `${m.bat_hand}-handed`, m.grip].filter(Boolean).join(" · ")}
                </p>
              </div>
              <div className="text-right">
                <p className="headline text-4xl tabular-nums text-accent">{m.score}%</p>
                <p className="text-[0.65rem] font-bold uppercase tracking-widest text-muted">body match</p>
              </div>
            </div>
            {m.form_score !== null && (
              <div className="mt-3">
                <div className="flex justify-between text-xs font-bold uppercase tracking-widest text-muted">
                  <span>Swing match</span><span className="tabular-nums">{m.form_score}%</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-accent" style={{ width: `${m.form_score}%` }} />
                </div>
              </div>
            )}
            {m.differences.length > 0 && (
              <ul className="mt-3 space-y-1 text-sm">
                {m.differences.map((d) => <li key={d} className="flex gap-2"><span aria-hidden className="text-accent">→</span>{d}</li>)}
              </ul>
            )}
            {!m.breakdown && m.form_score === null && (
              <p className="mt-3 text-sm text-muted">
                No {stroke ?? "matching"} clip of {m.name.split(" ").at(-1)} yet, so there&apos;s no swing comparison.
              </p>
            )}
            {m.warnings?.map((w) => <Warning key={w} className="mt-3">{w}</Warning>)}
          </li>
        ))}
      </ol>
    </section>
  );
}
