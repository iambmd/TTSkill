/** Pro-match results: the best match comes first, in the cards and in the demo data. */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import demoJobs from "@/lib/demo-jobs.json";
import type { ProMatch } from "@/lib/submit";
import { Matches } from "@/app/jobs/[id]/matches";

const demo = demoJobs["demo-match"] as unknown as { message: string; matches: ProMatch[] };
const render = (matches: ProMatch[], stroke = "forehand") => renderToStaticMarkup(createElement(Matches, { matches, stroke }));

describe("pro match cards", () => {
  it("cached demo lists the matches best first, and the headline names the first", () => {
    const scores = demo.matches.map((m) => m.score);
    expect(scores).toEqual([...scores].sort((a, b) => b - a));
    expect(demo.message).toContain(demo.matches[0].name);
  });

  it("renders the top match first, numbered 01", () => {
    const html = render(demo.matches);
    const positions = demo.matches.map((m) => html.indexOf(m.name));
    expect(positions.every((p) => p >= 0)).toBe(true);
    expect(positions).toEqual([...positions].sort((a, b) => a - b));
    expect(html.indexOf(">01<")).toBeLessThan(positions[0]);
  });

  it("says when the top match has no clip of the stroke instead of an empty card", () => {
    const [first, ...rest] = demo.matches;
    const html = render([{ ...first, name: "Dimitrij Ovtcharov", breakdown: null, form_score: null, differences: [] }, ...rest]);
    expect(html).toContain("No forehand clip of Ovtcharov yet");
    expect(html.indexOf("Ovtcharov")).toBeLessThan(html.indexOf(rest[0].name));
  });
});
