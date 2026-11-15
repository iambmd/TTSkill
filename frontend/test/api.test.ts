/**
 * Every Next.js API route under app/api/jobs: form validation, and lib/jobs.ts in its three
 * modes - stub (no BACKEND_URL), proxy to FastAPI (fetch mocked), and DEMO_MODE.
 * BACKEND_URL and DEMO_MODE are read when lib/jobs.ts loads, so each test re-imports.
 */
import { readdirSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Route = {
  POST?: (req: Request) => Promise<Response>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- each route has its own params shape
  GET?: (req: Request, ctx: { params: Promise<any> }) => Promise<Response>;
};

const ROUTES = {
  breakdown: "@/app/api/jobs/breakdown/route",
  autocut: "@/app/api/jobs/autocut/route",
  match: "@/app/api/jobs/match/route",
  coach: "@/app/api/jobs/coach/route",
  job: "@/app/api/jobs/[id]/route",
  result: "@/app/api/jobs/[id]/result/route",
  files: "@/app/api/jobs/[id]/files/[name]/route",
} as const;

const SHORT = "https://youtube.com/shorts/g3n9jVP0fMU";
const savedEnv = { ...process.env };

async function route(name: keyof typeof ROUTES, env: { BACKEND_URL?: string; DEMO_MODE?: string } = {}): Promise<Route> {
  vi.resetModules();
  delete process.env.BACKEND_URL;
  delete process.env.DEMO_MODE;
  Object.assign(process.env, env);
  const imports: Record<keyof typeof ROUTES, () => Promise<Route>> = {
    breakdown: () => import("@/app/api/jobs/breakdown/route"),
    autocut: () => import("@/app/api/jobs/autocut/route"),
    match: () => import("@/app/api/jobs/match/route"),
    coach: () => import("@/app/api/jobs/coach/route"),
    job: () => import("@/app/api/jobs/[id]/route"),
    result: () => import("@/app/api/jobs/[id]/result/route"),
    files: () => import("@/app/api/jobs/[id]/files/[name]/route"),
  };
  return imports[name]();
}

const video = () => new File([new Uint8Array([1, 2, 3])], "clip.mp4", { type: "video/mp4" });

function post(fields: Record<string, string | File>): Request {
  const form = new FormData();
  for (const [k, v] of Object.entries(fields)) form.append(k, v);
  return new Request("http://test/api", { method: "POST", body: form });
}

const get = (headers: Record<string, string> = {}) => new Request("http://test/api", { headers });
const ctx = <T extends Record<string, string>>(params: T) => ({ params: Promise.resolve(params) });

async function expectError(res: Response, status: number, text: string) {
  expect(res.status).toBe(status);
  expect((await res.json()).error).toContain(text);
}

beforeEach(() => {
  delete (globalThis as { __ttskillJobs?: unknown }).__ttskillJobs; // fresh stub store
});

afterEach(() => {
  process.env = { ...savedEnv };
  vi.unstubAllGlobals();
});

// ------------------------------------------------------------------ validation (stub mode)

describe("POST /api/jobs/breakdown", () => {
  it("needs a clip, a link or a description", async () => {
    const { POST } = await route("breakdown");
    await expectError(await POST!(post({})), 400, "Upload a clip, paste a YouTube link, or describe the training");
  });
  it("rejects links that are not YouTube", async () => {
    const { POST } = await route("breakdown");
    await expectError(await POST!(post({ url: "https://vimeo.com/1" })), 400, "youtube.com/watch, youtu.be or Shorts");
  });
  it("rejects unknown strokes and stroke types", async () => {
    const { POST } = await route("breakdown");
    await expectError(await POST!(post({ text: "x", stroke: "smash" })), 400, "Unknown stroke: smash");
    await expectError(await POST!(post({ text: "x", stroke_type: "tomahawk" })), 400, "Unknown stroke type");
  });
  it.each([
    ["text", { text: "Fan flicks early" }],
    ["a video", { video: video(), stroke_type: "backhand_flick" }],
    ["a link", { url: SHORT }],
  ])("creates a job from %s", async (_label, fields) => {
    const { POST } = await route("breakdown");
    const res = await POST!(post(fields as Record<string, string | File>));
    expect(res.status).toBe(201);
    const job = await res.json();
    expect(job).toMatchObject({ kind: "breakdown", status: "queued", progress: 0 });
  });
});

describe("POST /api/jobs/autocut", () => {
  it("validates the input", async () => {
    const { POST } = await route("autocut");
    await expectError(await POST!(post({ mode: "highlights" })), 400, "Upload a match video or paste a YouTube link");
    await expectError(await POST!(post({ video: video(), mode: "best" })), 400, "mode must be");
    await expectError(await POST!(post({ url: "not a link", mode: "full" })), 400, "youtube.com/watch");
  });
  it("creates a job from a video or a link", async () => {
    const { POST } = await route("autocut");
    expect((await POST!(post({ video: video(), mode: "full" }))).status).toBe(201);
    expect((await POST!(post({ url: SHORT, mode: "highlights" }))).status).toBe(201);
  });
});

describe("POST /api/jobs/match", () => {
  it("validates the input", async () => {
    const { POST } = await route("match");
    await expectError(await POST!(post({ stroke: "forehand" })), 400, "Upload a clip of yourself");
    await expectError(await POST!(post({ video: video(), stroke: "serve" })), 400, "Pick forehand or backhand");
    await expectError(await POST!(post({ video: video(), stroke: "forehand", height_cm: "40" })), 400, "between 100 and 230");
  });
  it("creates a job", async () => {
    const { POST } = await route("match");
    const res = await POST!(post({ video: video(), stroke: "backhand", height_cm: "172" }));
    expect(res.status).toBe(201);
    expect((await res.json()).kind).toBe("match");
  });
});

describe("POST /api/jobs/coach", () => {
  it("validates the input", async () => {
    const { POST } = await route("coach");
    await expectError(await POST!(post({ video: video() })), 400, "Tell the coach");
    await expectError(await POST!(post({ request: "fix my forehand" })), 400, "Add a video");
    await expectError(await POST!(post({ request: "fix it", url: "https://example.com" })), 400, "youtube.com/watch");
  });
  it("creates a job", async () => {
    const { POST } = await route("coach");
    const res = await POST!(post({ request: "show my best rallies", url: SHORT }));
    expect(res.status).toBe(201);
    expect((await res.json()).kind).toBe("coach");
  });
});

// ------------------------------------------------------------------ reading jobs (stub mode)

describe("GET /api/jobs/[id] and result in stub mode", () => {
  it("advances a stub job to done so the page can be tried without a backend", async () => {
    const create = await route("breakdown");
    const { id } = await (await create.POST!(post({ text: "loops" }))).json();
    const { GET } = await import("@/app/api/jobs/[id]/route");
    const seen: string[] = [];
    for (let i = 0; i < 5; i++) seen.push((await (await GET(get(), ctx({ id }))).json()).status);
    expect(seen.at(-1)).toBe("done");
  });
  it("is 404 for unknown jobs", async () => {
    const { GET } = await route("job");
    expect((await GET!(get(), ctx({ id: "nope" }))).status).toBe(404);
  });
  it("serves the cached demo jobs", async () => {
    const { GET } = await route("job");
    const job = await (await GET!(get(), ctx({ id: "demo-breakdown" }))).json();
    expect(job).toMatchObject({ id: "demo-breakdown", status: "done", resultUrl: "/demo/breakdown.mp4" });
  });
  it("has no result video in stub mode", async () => {
    const { GET } = await route("result");
    expect((await GET!(get(), ctx({ id: "x" }))).status).toBe(404);
  });
  it("only serves .mp4 coach files", async () => {
    const { GET } = await route("files", { BACKEND_URL: "http://backend" });
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    expect((await GET!(get(), ctx({ id: "x", name: "job.json" }))).status).toBe(404);
    expect((await GET!(get(), ctx({ id: "x", name: "../secret.mp4" }))).status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });
});

// ------------------------------------------------------------------ proxy mode (FastAPI mocked)

describe("proxy to the FastAPI backend", () => {
  const backend = { BACKEND_URL: "http://backend" };

  it("forwards the form and returns the backend's job", async () => {
    const fetch = vi.fn(async () => Response.json({ id: "abc", kind: "breakdown", status: "queued" }, { status: 201 }));
    vi.stubGlobal("fetch", fetch);
    const { POST } = await route("breakdown", backend);
    const res = await POST!(post({ text: "loops", player: "Ma Long" }));
    expect(res.status).toBe(201);
    expect((await res.json()).id).toBe("abc");
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://backend/jobs/breakdown");
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("player")).toBe("Ma Long");
  });

  it("turns FastAPI's {detail} into {error}", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ detail: "That video is private." }, { status: 400 })));
    const { POST } = await route("breakdown", backend);
    await expectError(await POST!(post({ url: SHORT })), 400, "That video is private.");
  });

  it("answers 502 with a readable error when the backend is down", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fetch failed"); }));
    const create = await route("breakdown", backend);
    await expectError(await create.POST!(post({ text: "loops" })), 502, "Can't reach the TTSkill backend");
    const read = await route("job", backend);
    await expectError(await read.GET!(get(), ctx({ id: "abc" })), 502, "Can't reach the TTSkill backend");
  });

  it("points result and coach file URLs at this app's routes", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({
      id: "abc", kind: "coach", status: "done", resultUrl: "/jobs/abc/result",
      outputs: [{ kind: "highlights", title: "Top 3", url: "/jobs/abc/files/highlights.mp4", summary: "" }],
    })));
    const { GET } = await route("job", backend);
    const job = await (await GET!(get(), ctx({ id: "abc" }))).json();
    expect(job.resultUrl).toBe("/api/jobs/abc/result");
    expect(job.outputs[0].url).toBe("/api/jobs/abc/files/highlights.mp4");
  });

  it("passes a backend 404 through", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ detail: "job not found" }, { status: 404 })));
    const { GET } = await route("job", backend);
    expect((await GET!(get(), ctx({ id: "gone" }))).status).toBe(404);
  });

  it("streams results with the range header so iOS can seek", async () => {
    const fetch = vi.fn(async () => new Response("2345", {
      status: 206, headers: { "content-type": "video/mp4", "content-range": "bytes 2-5/10", "x-internal": "no" },
    }));
    vi.stubGlobal("fetch", fetch);
    const { GET } = await route("result", backend);
    const res = await GET!(get({ range: "bytes=2-5" }), ctx({ id: "abc" }));
    expect(res.status).toBe(206);
    expect(await res.text()).toBe("2345");
    expect(res.headers.get("content-range")).toBe("bytes 2-5/10");
    expect(res.headers.get("x-internal")).toBeNull();
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://backend/jobs/abc/result");
    expect((init.headers as Record<string, string>).range).toBe("bytes=2-5");
  });

  it("fetches coach videos from /jobs/{id}/files/{name}", async () => {
    const fetch = vi.fn(async () => new Response("mp4", { headers: { "content-type": "video/mp4" } }));
    vi.stubGlobal("fetch", fetch);
    const { GET } = await route("files", backend);
    const res = await GET!(get(), ctx({ id: "abc", name: "breakdown.mp4" }));
    expect(await res.text()).toBe("mp4");
    expect((fetch.mock.calls[0] as unknown as [string])[0]).toBe("http://backend/jobs/abc/files/breakdown.mp4");
  });
});

// ------------------------------------------------------------------ demo mode

describe("DEMO_MODE", () => {
  it("answers submissions with the cached demo job", async () => {
    const { POST } = await route("breakdown", { DEMO_MODE: "1" });
    const res = await POST!(post({ text: "anything" }));
    expect(res.status).toBe(201);
    expect((await res.json()).id).toBe("demo-breakdown");
  });
  it("falls back to a normal job for kinds without a cached demo", async () => {
    const { POST } = await route("match", { DEMO_MODE: "1" });
    const job = await (await POST!(post({ video: video(), stroke: "forehand" }))).json();
    expect(job).toMatchObject({ kind: "match", status: "queued" });
  });
});

// A new route.ts under app/api must be added to ROUTES (and tested) or this fails.
it("covers every route file", () => {
  const files = readdirSync(join(__dirname, "..", "app", "api"), { recursive: true, encoding: "utf8" })
    .filter((f) => f.endsWith("route.ts"))
    .map((f) => `@/app/api/${f.replaceAll("\\", "/").replace(/\.ts$/, "")}`)
    .sort();
  expect(files).toEqual(Object.values(ROUTES).sort());
});
