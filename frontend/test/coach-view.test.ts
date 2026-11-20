/** The Coach result page: the coaching notes are the main section (Markdown), the agent's working
 * files never reach players, the plan collapses when done, and nothing can widen the page. */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import demoJobs from "@/lib/demo-jobs.json";
import { coachingOf } from "@/lib/coaching";
import type { Job } from "@/lib/submit";
import { Markdown, parseBlocks } from "@/app/markdown";
import { CoachView } from "@/app/jobs/[id]/coach-view";

// AnalysedPlayer (inside the view) asks for the app router, which only exists inside Next.
vi.mock("next/navigation", () => ({ useRouter: () => ({ push() {} }) }));

// The coaching call's summary on coaching-demo (backend/eval/coach_speed/phase1-final-*), shortened.
const NOTES = `Your legs are too straight on the forehand, so your arm does the work instead of your body.

**What to work on first:**
1. **Bend your knees more.** At contact your knee angle is 157°. Ma Long's forehand is 126°.
2. **Keep your stance steady.** Hold it at about 1.8 to 2 shoulder widths.

**Drill:** Shadow-swing 20 forehands in front of a mirror.`;

const LABELS = ["Find the rallies", "Cut the best rallies", "Track you at your forehands", "Find the pros closest to you",
  "Write the coaching", "Render your forehand"];
const LONG_JSON = JSON.stringify({ at_contact: { knee_angle_deg: 157 }, curves: Array.from({ length: 200 }, (_, i) => i) });

function job(over: Partial<Job> = {}): Job {
  return {
    id: "0123456789abcdef0123456789abcdef", kind: "coach", status: "done", progress: 1, message: "Done.",
    params: { request: "Here's my match, show my best rallies and fix my forehand" },
    todos: LABELS.map((content) => ({ content, status: "completed" as const })),
    agentFiles: [{ name: "/facts.json", preview: LONG_JSON }, { name: "/rallies.json", preview: "[{\"start\": 1.0}]" }],
    outputs: [], engine: "pipeline", summary: NOTES,
    coaching: { markdown: NOTES, fix: "**Bend your knees more.** At contact your knee angle is 157°.", drill: "Shadow-swing 20 forehands." },
    breakdown: {
      player: "Player", stroke: "forehand", stroke_type: "forehand_topspin", handedness: "right", headline: "Sit lower",
      grip: "g", stance: "s", swing_path: "p", contact_point: "c", follow_through: "f",
      steps: [{ title: "LOAD LOW", lines: ["Knees bent", "Power"], highlight_words: [], key_time_s: 1.4, callouts: [] }],
      recap: "Load low.", drill: "Do 20 slow shadow forehands.", source: "coach",
    } as unknown as Job["breakdown"],
    ...over,
  };
}
const render = (j: Job, debug = false) => renderToStaticMarkup(createElement(CoachView, { job: j, debug }));

describe("coaching notes", () => {
  it("are the main section, rendered as Markdown", () => {
    const html = render(job());
    const main = html.indexOf("Your coaching");
    expect(main).toBeGreaterThan(-1);
    expect(main).toBeLessThan(html.indexOf("Step by step"));   // before the breakdown and the videos
    expect(html).toContain('<ol start="1"');
    expect(html).toContain("<strong class=\"font-bold text-fg\">Bend your knees more.</strong>");
    expect(html).toContain("Shadow-swing 20 forehands in front of a mirror.");
    expect(html).not.toContain("**");
  });

  it("never show the agent's internal files to players", () => {
    const html = render(job());
    expect(html).not.toContain("/facts.json");
    expect(html).not.toContain("/rallies.json");
    expect(html).not.toContain("knee_angle_deg");
    expect(html).not.toContain("Coach&#x27;s notes");
    expect(html).not.toContain("Debug");
  });

  it("show the raw files behind Debug in development only", () => {
    const html = render(job(), true);
    expect(html).toMatch(/<details[^>]*>(?:(?!<\/details>)[\s\S])*Debug: the coach&#x27;s working files \(2\)/);
    expect(html).toContain("/facts.json");
    // Wrapped, so a long JSON line can't widen the page.
    expect(html).toMatch(/<pre class="[^"]*whitespace-pre-wrap[^"]*break-all/);
  });

  it("aren't repeated: the breakdown leaves out the drill the notes already have", () => {
    const html = render(job());
    expect(html).not.toContain("Try this");
    expect(html).not.toContain("Do 20 slow shadow forehands.");
  });

  it("say clearly when there are none, with the reason", () => {
    const none = render(job({ coaching: null, breakdown: undefined, warning: "We couldn't see you hitting the ball clearly." }));
    expect(none).toContain("No coaching notes for this video.");
    expect(none).toContain("We couldn&#x27;t see you hitting the ball clearly.");
    expect(none).not.toContain("Your legs are too straight");   // `summary` doesn't stand in for new jobs
    const failed = render(job({ status: "failed", coaching: null, message: "Out of memory." }));
    expect(failed).toContain("The job stopped before the coach wrote them.");
    const running = render(job({ status: "running", coaching: null, progress: 0.4 }));
    expect(running).toContain("Your coaching notes appear here once the coach has written them.");
  });

  it("come from `coaching`, and from `summary` only for jobs made before that field", () => {
    expect(coachingOf(job())?.markdown).toBe(NOTES);
    expect(coachingOf(job({ coaching: null }))).toBeNull();
    const legacy = job();
    delete legacy.coaching;
    expect(coachingOf(legacy)).toEqual({ markdown: NOTES, fix: "", drill: "Do 20 slow shadow forehands." });
    expect(coachingOf({ ...legacy, status: "running" })).toBeNull();
    expect(coachingOf({ ...legacy, summary: "Done." })).toBeNull();
  });
});

describe("the plan", () => {
  it("is a compact checklist with a progress bar while the job runs", () => {
    const todos = LABELS.map((content, i) => ({ content, status: (i < 2 ? "completed" : i === 2 ? "in_progress" : "pending") as "completed" }));
    const html = render(job({ status: "running", progress: 0.43, todos, coaching: null }));
    for (const label of LABELS) expect(html).toContain(label);
    expect(html).toContain("2 of 6 · 43%");
    expect(html).toContain('role="progressbar"');
    expect(html).toContain('aria-valuenow="43"');
  });

  it("collapses to one line when done, and opens to the steps", () => {
    const html = render(job());
    const plan = /<details class="group coach-plan border">([\s\S]*?)<\/details>/.exec(html)?.[1] ?? "";
    expect(plan).toContain("All steps done");
    expect(plan).toContain("6 steps");
    for (const label of LABELS) expect(plan).toContain(label);
    expect(html).not.toContain("<details open");
    expect(html).not.toContain('role="progressbar"');
  });

  it("shows where a failed job stopped", () => {
    const todos = LABELS.map((content, i) => ({ content, status: (i < 3 ? "completed" : i === 3 ? "in_progress" : "pending") as "completed" }));
    const html = render(job({ status: "failed", todos, coaching: null }));
    expect(html).toContain("Stopped");
    expect(html).toMatch(/Find the pros closest to you<span[^>]*> \(stopped here\)/);
  });
});

describe("no horizontal scroll", () => {
  it("lets both columns shrink below their content", () => {
    const html = render(job(), true);
    expect(html).toContain("lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]");
    const grid = /<div class="coach-surface coach-result[^"]*">(<div class="([^"]*)">)/.exec(html);
    expect(grid?.[2]).toContain("min-w-0");
  });

  it("every grid track on the result pages can shrink (a bare 1fr can't go below its widest line)", () => {
    const dir = fileURLToPath(new URL("../app/jobs/[id]/", import.meta.url));
    let tracks = 0;
    for (const name of readdirSync(dir).filter((n) => n.endsWith(".tsx"))) {
      const src = readFileSync(join(dir, name), "utf8");
      for (const [cls] of src.matchAll(/grid-cols-\[[^\]]*\]/g)) {
        tracks += 1;
        expect(cls, `${name}: ${cls}`).not.toMatch(/(^|[[_])1fr/);
      }
    }
    expect(tracks).toBeGreaterThanOrEqual(3);   // coach view, the other results, the breakdown details
    expect("grid-cols-[minmax(0,22rem)_1fr]").toMatch(/(^|[[_])1fr/);   // the old layout fails this check
  });

  it("long unbroken text wraps in the notes", () => {
    const html = renderToStaticMarkup(createElement(Markdown, { text: `x${"a".repeat(300)}` }));
    expect(html).toContain("[overflow-wrap:anywhere]");
  });
});

describe("markdown", () => {
  it("parses paragraphs, headings and lists the way the coach writes them", () => {
    expect(parseBlocks(NOTES).map((b) => b.type)).toEqual(["p", "p", "ol", "p"]);
    expect(parseBlocks("## Fixes\n- one\n- two\n  still two\n\n3. three").map((b) => b)).toEqual([
      { type: "h", text: "Fixes" }, { type: "ul", items: ["one", "two still two"] }, { type: "ol", start: 3, items: ["three"] }]);
  });

  it("renders text only: no HTML, links as their text, underscores literal", () => {
    const html = renderToStaticMarkup(createElement(Markdown, {
      text: "<script>alert(1)</script> see [the reel](https://example.com) for forehand_topspin, *really*",
    }));
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script");
    expect(html).not.toContain("href");
    expect(html).toContain("the reel");
    expect(html).toContain("forehand_topspin");
    expect(html).toContain("<em>really</em>");
  });
});

describe("cached demo jobs (made before `coaching` existed)", () => {
  it("still render their notes and a done plan", () => {
    const demo = demoJobs["demo-coach"] as unknown as Job;
    expect("coaching" in demo).toBe(false);
    const html = render(demo);
    expect(html).toContain("Your coaching");
    expect(html).toContain("I found 17 rallies");
    expect(html).toContain("All steps done");
    expect(html).not.toContain("No coaching notes");
  });
});
