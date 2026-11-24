/** The Coach page's example: a real request and match, then the coach's saved plan, reply and videos. */

import { useTranslations } from "next-intl";
import type { Job } from "@/lib/submit";
import { EnglishOnly, useEnglishBlock } from "../english-only";
import { Markdown } from "../markdown";
import { CheckIcon } from "../ui";
import { ExampleSection } from "../examples";
// Same fields as a coach job record, so a finished job.json can be copied in. Empty means "coming soon".
import saved from "@/lib/coach-example.json";

const after = saved as Pick<Required<Job>, "todos" | "summary" | "outputs">;

const DEMO_OUTPUTS: Record<string, string> = { highlights: "coachHighlights", breakdown: "coachBreakdown" };

function After() {
  const t = useTranslations();
  const english = useEnglishBlock(true);
  const ready = after.todos.length > 0 || !!after.summary || after.outputs.length > 0;
  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <span className="headline text-2xl">{t("common.after")}</span>
        <span className="flex flex-wrap items-center justify-end gap-2 text-right text-xs text-muted">
          {saved.engine === "fallback" ? t("coach.example.localPlan") : t("coach.example.coachPlan")}
          {ready && <EnglishOnly />}
        </span>
      </div>
      {!ready ? (
        <div className="stripes grid aspect-video place-items-center rounded-3xl border border-line bg-panel text-sm text-muted">
          {t("coach.example.comingSoon")}
        </div>
      ) : (
        <>
          {after.todos.length > 0 && (
            <ol {...english} className="space-y-1.5 rounded-2xl border border-line bg-panel p-3">
              {after.todos.map((t, i) => (
                <li key={i} className="flex items-center gap-3 rounded-xl px-2 py-2 text-sm">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full action-fill"><CheckIcon className="size-3.5" /></span>
                  <span className="text-muted">{t.content}</span>
                </li>
              ))}
            </ol>
          )}
          {after.summary && (
            <section className="coach-notes min-w-0">
              <h3 className="headline">{t("coach.example.coachSays")}</h3>
              <div {...english}><Markdown text={after.summary} className="mt-1 text-base leading-snug" /></div>
            </section>
          )}
          {after.outputs.map((o) => (
            <figure key={o.url} className="space-y-2">
              <figcaption>
                <span id={`example-${o.kind}-title`} className="headline text-xl" {...english}>{o.title}</span>
                <span id={`example-${o.kind}-description`} className="block text-sm text-muted">
                  {DEMO_OUTPUTS[o.kind] ? t(`demoDescriptions.${DEMO_OUTPUTS[o.kind]}`) : o.summary}
                </span>
              </figcaption>
              <video
                src={`${o.url}#t=0.1`} controls muted playsInline preload="metadata"
                aria-labelledby={`example-${o.kind}-title`} aria-describedby={`example-${o.kind}-description`}
                className={`video-frame mx-auto block w-full overflow-hidden border object-contain ${
                  o.kind === "highlights" ? "aspect-video" : "aspect-[9/16] max-w-xs"
                }`}
              />
            </figure>
          ))}
        </>
      )}
    </div>
  );
}

const STEPS = ["one", "two", "three", "four", "five", "six"] as const;

export function CoachExample() {
  const t = useTranslations();
  return (
    <ExampleSection
      before={{
        src: "/examples/coach-before.mp4",
        label: t("common.before"),
        caption: t("coach.example.caption"),
        message: t("coach.example.message"),
      }}
      after={<After />}
      stepsTitle={t("coach.example.stepsTitle")}
      steps={STEPS.map((s) => t(`coach.example.steps.${s}`))}
    />
  );
}
