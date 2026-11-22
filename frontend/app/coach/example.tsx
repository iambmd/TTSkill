/** The Coach page's example: a real request and match, then the coach's saved plan, reply and videos. */

import type { Job } from "@/lib/submit";
import { coachDemoDescriptions } from "@/lib/demo-descriptions";
import { Markdown } from "../markdown";
import { CheckIcon } from "../ui";
import { ExampleSection } from "../examples";
// Same fields as a coach job record, so a finished job.json can be copied in. Empty means "coming soon".
import saved from "@/lib/coach-example.json";

const after = saved as Pick<Required<Job>, "todos" | "summary" | "outputs">;

function After() {
  const ready = after.todos.length > 0 || !!after.summary || after.outputs.length > 0;
  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <span className="headline text-2xl">After</span>
        <span className="text-right text-xs text-muted">{saved.engine === "fallback" ? "Local coaching plan, reply and videos" : "The coach’s plan, reply and videos"}</span>
      </div>
      {!ready ? (
        <div className="stripes grid aspect-video place-items-center rounded-3xl border border-line bg-panel text-sm text-muted">
          Example result coming soon
        </div>
      ) : (
        <>
          {after.todos.length > 0 && (
            <ol className="space-y-1.5 rounded-2xl border border-line bg-panel p-3">
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
              <h3 className="headline">Coach says</h3>
              <Markdown text={after.summary} className="mt-1 text-base leading-snug" />
            </section>
          )}
          {after.outputs.map((o) => (
            <figure key={o.url} className="space-y-2">
              <figcaption>
                <span id={`example-${o.kind}-title`} className="headline text-xl">{o.title}</span>
                <span id={`example-${o.kind}-description`} className="block text-sm text-muted">{coachDemoDescriptions[o.kind] ?? o.summary}</span>
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

export function CoachExample() {
  return (
    <ExampleSection
      before={{
        src: "/examples/coach-before.mp4",
        label: "Before",
        caption: "A phone records a match, with the player in teal nearest the camera and their opponent across the table.",
        message: "Here's my match, show my best rallies and fix my forehand",
      }}
      after={<After />}
      stepsTitle="What the coach does."
      steps={[
        "A LangChain deepagents agent running Claude reads your request and the video you sent.",
        "It writes a to-do list for the job, and you watch it tick off live.",
        "It calls its tools: Auto-Cut finds your best rallies by sound, and Technique Breakdown tracks your pose to check your forehand.",
        "It only coaches a real stroke: one inside a rally, right on a ball-contact sound, from your playing stance. Swings after the point ends don't count.",
        "Helper agents split the work: a clip analyst, a pro matcher and a coach writer, each with its own notes.",
        "Claude writes your reply: what went well, the fix to work on, and a drill, with the videos it made.",
      ]}
    />
  );
}
