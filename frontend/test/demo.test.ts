/** Cached jobs, embedded examples and videos must come from the same refresh. */
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import demoJobs from "@/lib/demo-jobs.json";
import assets from "@/lib/demo-assets.json";
import coach from "@/lib/coach-example.json";
import type { Job } from "@/lib/submit";

const publicDir = join(__dirname, "..", "public");
const hash = (path: string) => createHash("sha256").update(readFileSync(path)).digest("hex");

function verifyVideo(src: string) {
  const url = new URL(src, "https://demo.test");
  expect(url.pathname).toMatch(/^\/examples\/[\w-]+\.mp4$/);
  expect(url.searchParams.get("v")).toBe(hash(join(publicDir, url.pathname)).slice(0, 12));
}

describe("refreshed demo artifacts", () => {
  it.each(["autocut", "breakdown", "match", "coach"] as const)("has a completed %s run on the displayed input", (kind) => {
    const job = demoJobs[`demo-${kind}`];
    expect(job.status).toBe("done");
    expect(job.kind).toBe(kind);
    expect(job.demoRefresh.source_sha256).toBe(hash(join(publicDir, `examples/${kind}-before.mp4`)));
    const result = job as Job;
    const urls = result.outputs?.map(o => o.url) ?? [result.resultUrl!];
    expect(urls.length).toBeGreaterThan(0);
    urls.forEach(verifyVideo);
  });

  it("uses the same results on example and job pages", () => {
    for (const kind of ["autocut", "breakdown", "match"] as const) {
      expect(demoJobs[`demo-${kind}`].resultUrl).toBe(assets[kind].url);
      expect(assets[kind].duration).toBeGreaterThan(0);
    }
    expect(coach.outputs).toEqual(demoJobs["demo-coach"].outputs);
    expect(coach.summary).toBe(demoJobs["demo-coach"].summary);
    expect(coach.outputs.map(o => o.kind).sort()).toEqual(["breakdown", "highlights"]);
    expect(coach.summary).not.toContain("Some steps failed:");
  });

  it("also refreshes the original bookmarked video URLs", () => {
    expect(hash(join(publicDir, "demo/breakdown.mp4"))).toBe(hash(join(publicDir, "examples/breakdown-after.mp4")));
    expect(hash(join(publicDir, "demo/highlights.mp4"))).toBe(hash(join(publicDir, "examples/autocut-after.mp4")));
  });
});
