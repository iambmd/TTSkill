/** The breakdown steps shown on Breakdown and Coach results. */
import type { Breakdown } from "@/lib/submit";

/** A breakdown's cards, drill and details. Coach passes drill={false} when its notes already hold the drill. */
export function Steps({ b, drill = true }: { b: Breakdown; drill?: boolean }) {
  const facts: [string, string][] = [
    ["Grip", b.grip], ["Stance", b.stance], ["Swing path", b.swing_path],
    ["Contact point", b.contact_point], ["Follow-through", b.follow_through],
  ];
  return (
    <>
      <section className="space-y-3">
        <h2 className="eyebrow">Step by step</h2>
        <ol className="space-y-2">
          {b.steps.map((s, i) => (
            <li key={i} className="flex gap-4 rounded-2xl border border-line bg-panel p-4">
              <span className="headline text-4xl leading-none text-accent">{String(i + 1).padStart(2, "0")}</span>
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
        {b.recap && <p className="headline text-2xl text-muted">{b.recap}</p>}
      </section>
      {drill && b.drill && (
        <section className="rounded-2xl border border-accent/40 bg-accent/10 p-4">
          <h2 className="eyebrow">Try this</h2>
          <p className="mt-1 text-lg font-semibold">{b.drill}</p>
        </section>
      )}
      <section className="space-y-3">
        <h2 className="eyebrow">The details</h2>
        <dl className="divide-y divide-line rounded-2xl border border-line bg-panel">
          {facts.map(([k, v]) => (
            <div key={k} className="grid gap-1 px-4 py-3 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-4">
              <dt className="text-xs font-bold uppercase tracking-widest text-muted sm:pt-0.5">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </section>
    </>
  );
}
