/**
 * Every Next.js API route under app/api/jobs: form validation (422s, limits from shared/limits.json),
 * and lib/jobs.ts in its three
 * modes - stub (no BACKEND_URL), proxy to FastAPI (fetch mocked), and DEMO_MODE - plus a public
 * NEXT_PUBLIC_API_URL (Vercel + tunnel), where uploads and videos skip our routes.
 * The env is read when lib/jobs.ts and lib/submit.ts load, so each test re-imports.
 */
import demoJobs from "@/lib/demo-jobs.json";
import { readdirSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Route = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- each route has its own params shape
  POST?: (...args: any[]) => Promise<Response>;
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
  rubbers: "@/app/api/rubbers/route",
  players: "@/app/api/players/detect/route",
  rerun: "@/app/api/jobs/[id]/rerun/route",
} as const;

const SHORT = "https://youtube.com/shorts/g3n9jVP0fMU";
const savedEnv = { ...process.env };

type Env = { BACKEND_URL?: string; DEMO_MODE?: string; NEXT_PUBLIC_API_URL?: string };

function setEnv(env: Env) {
  vi.resetModules();
  delete process.env.BACKEND_URL;
  delete process.env.DEMO_MODE;
  delete process.env.NEXT_PUBLIC_API_URL;
  Object.assign(process.env, env);
}

async function route(name: keyof typeof ROUTES, env: Env = {}): Promise<Route> {
  setEnv(env);
  const imports: Record<keyof typeof ROUTES, () => Promise<Route>> = {
    breakdown: () => import("@/app/api/jobs/breakdown/route"),
    autocut: () => import("@/app/api/jobs/autocut/route"),
    match: () => import("@/app/api/jobs/match/route"),
    coach: () => import("@/app/api/jobs/coach/route"),
    job: () => import("@/app/api/jobs/[id]/route"),
    result: () => import("@/app/api/jobs/[id]/result/route"),
    files: () => import("@/app/api/jobs/[id]/files/[name]/route"),
    rubbers: () => import("@/app/api/rubbers/route"),
    players: () => import("@/app/api/players/detect/route"),
    rerun: () => import("@/app/api/jobs/[id]/rerun/route"),
  };
  return imports[name]();
}

const video = (name = "clip.mp4") => new File([new Uint8Array([1, 2, 3])], name, { type: "video/mp4" });

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

// ------------------------------------------------------------------ validation (stub mode): 422 before the backend

describe("POST /api/jobs/breakdown", () => {
  it("needs a clip, a link or a description", async () => {
    const { POST } = await route("breakdown");
    await expectError(await POST!(post({})), 422, "Upload a clip, paste a YouTube link, or describe the training");
    await expectError(await POST!(post({ text: "  \n " })), 422, "Upload a clip");
  });
  it("rejects links that are not YouTube videos", async () => {
    const { POST } = await route("breakdown");
    await expectError(await POST!(post({ url: "https://vimeo.com/1" })), 422, "Only YouTube links work here");
    await expectError(await POST!(post({ url: "https://www.youtube.com/playlist?list=PL1" })), 422, "That's a playlist");
    await expectError(await POST!(post({ url: "https://www.youtube.com/@pingskills" })), 422, "That's a channel link");
    // a bad link fails even when there's a description too
    await expectError(await POST!(post({ url: "https://vimeo.com/1", text: "loops" })), 422, "Only YouTube links");
  });
  it("rejects unknown strokes, stroke types and hands", async () => {
    const { POST } = await route("breakdown");
    await expectError(await POST!(post({ text: "x", stroke: "smash" })), 422, "Unknown stroke: smash");
    await expectError(await POST!(post({ text: "x", stroke_type: "tomahawk" })), 422, "Unknown stroke type");
    await expectError(await POST!(post({ text: "x", hand: "both" })), 422, "Bat hand must be auto, left or right");
    await expectError(await POST!(post({ text: "x", hand: "" })), 422, "Bat hand must be");
  });
  it("rejects files that aren't MP4, MOV, WebM or MKV, and text over the limits", async () => {
    const { POST } = await route("breakdown");
    await expectError(await POST!(post({ video: video("clip.avi") })), 422, "Upload a video file: MP4, MOV, WebM or MKV");
    await expectError(await POST!(post({ text: "x".repeat(5001) })), 422, "up to 5000 characters (it has 5001)");
    await expectError(await POST!(post({ text: "x", player: "M".repeat(81) })), 422, "The player's name can be up to 80");
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
    await expectError(await POST!(post({ mode: "highlights" })), 422, "Upload a match video or paste a YouTube link");
    await expectError(await POST!(post({ video: video(), mode: "best" })), 422, "Mode must be highlights or full");
    await expectError(await POST!(post({ url: "not a link", mode: "full" })), 422, "youtube.com/watch");
  });
  it.each([
    [{ top_n: "0" }, "Rallies in the reel must be between 1 and 20"],
    [{ top_n: "2.5" }, "Rallies in the reel must be a whole number"],
    [{ threshold: "abc" }, "Hit threshold must be a number"],
    [{ threshold: "11" }, "Hit threshold must be between 1.5 and 10"],
    [{ gap: "-1" }, "Max gap must be between 0.5 and 5"],
    [{ min_hits: "1" }, "Min hits must be between 2 and 20"],
  ])("rejects detection settings out of range: %o", async (fields, text) => {
    const { POST } = await route("autocut");
    await expectError(await POST!(post({ video: video(), mode: "highlights", ...fields })), 422, text);
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
    await expectError(await POST!(post({ stroke: "forehand" })), 422, "Upload a clip of yourself");
    await expectError(await POST!(post({ video: video(), stroke: "serve" })), 422, "Stroke must be forehand or backhand");
    await expectError(await POST!(post({ video: video(), grip: "seemiller" })), 422, "Grip must be shakehand or penhold");
    await expectError(await POST!(post({ video: video(), hand: "both" })), 422, "Bat hand must be auto, left or right");
  });
  it.each(["40", "0", "250", "230.5", "-170", "abc", "1e2", "0x64", "NaN"])("rejects height %s", async (h) => {
    const { POST } = await route("match");
    const res = await POST!(post({ video: video(), stroke: "forehand", height_cm: h }));
    expect(res.status).toBe(422);
    expect((await res.json()).error).toMatch(/between 100 and 230|as a number in cm/);
  });
  it("creates a job", async () => {
    const { POST } = await route("match");
    const res = await POST!(post({ video: video(), stroke: "backhand", height_cm: "172", grip: "penhold" }));
    expect(res.status).toBe(201);
    expect((await res.json()).kind).toBe("match");
  });
});

describe("POST /api/jobs/coach", () => {
  it("validates the input", async () => {
    const { POST } = await route("coach");
    await expectError(await POST!(post({ video: video() })), 422, "Tell the coach");
    await expectError(await POST!(post({ video: video(), request: " \t\n " })), 422, "Tell the coach");
    await expectError(await POST!(post({ request: "fix my forehand" })), 422, "Add a video");
    await expectError(await POST!(post({ request: "fix it", url: "https://example.com" })), 422, "youtube.com/watch");
  });
  it("takes 1 to 1000 characters, counted after trimming", async () => {
    const { POST } = await route("coach");
    await expectError(await POST!(post({ video: video(), request: "a".repeat(1001) })), 422, "up to 1000 characters (it has 1001)");
    const res = await POST!(post({ video: video(), request: `  ${"a".repeat(1000)}  ` }));
    expect(res.status).toBe(201);
    expect((await res.json()).params.request).toBe("a".repeat(1000));
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
    expect(job).toMatchObject({ id: "demo-breakdown", status: "done", resultUrl: demoJobs["demo-breakdown"].resultUrl });
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

  it("never calls the backend for invalid input", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const { POST } = await route("match", backend);
    await expectError(await POST!(post({ video: video(), height_cm: "250" })), 422, "between 100 and 230");
    expect(fetch).not.toHaveBeenCalled();
  });

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
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ detail: "That video is private." }, { status: 422 })));
    const { POST } = await route("breakdown", backend);
    await expectError(await POST!(post({ url: SHORT })), 422, "That video is private.");
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

// ------------------------------------------------------------------ public backend (Vercel + Cloudflare tunnel)

describe("NEXT_PUBLIC_API_URL", () => {
  const tunnel = { NEXT_PUBLIC_API_URL: "https://shy-river-1234.trycloudflare.com/" };

  it("sends the browser's uploads straight to it, past Vercel's 4.5 MB body limit", async () => {
    setEnv(tunnel);
    expect((await import("@/lib/submit")).jobEndpoint("autocut")).toBe("https://shy-river-1234.trycloudflare.com/jobs/autocut");
    setEnv({ BACKEND_URL: "http://backend" });
    expect((await import("@/lib/submit")).jobEndpoint("autocut")).toBe("/api/jobs/autocut");
  });

  it("stands in for BACKEND_URL and serves result and coach videos straight from the backend", async () => {
    const fetch = vi.fn(async () => Response.json({
      id: "abc", kind: "coach", status: "done", resultUrl: "/jobs/abc/result",
      outputs: [{ kind: "highlights", title: "Top 3", url: "/jobs/abc/files/highlights.mp4", summary: "" }],
    }));
    vi.stubGlobal("fetch", fetch);
    const { GET } = await route("job", tunnel);
    const job = await (await GET!(get(), ctx({ id: "abc" }))).json();
    expect((fetch.mock.calls[0] as unknown as [string])[0]).toBe("https://shy-river-1234.trycloudflare.com/jobs/abc");
    expect(job.resultUrl).toBe("https://shy-river-1234.trycloudflare.com/jobs/abc/result");
    expect(job.outputs[0].url).toBe("https://shy-river-1234.trycloudflare.com/jobs/abc/files/highlights.mp4");
  });

  it("still serves the cached demo jobs", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const { GET } = await route("job", tunnel);
    expect((await (await GET!(get(), ctx({ id: "demo-breakdown" }))).json()).resultUrl).toBe(demoJobs["demo-breakdown"].resultUrl);
  });
});

// ------------------------------------------------------------------ demo mode

describe("DEMO_MODE", () => {
  it.each(["breakdown", "autocut", "match", "coach"] as const)("returns the refreshed %s result", async (kind) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const { POST } = await route(kind, { DEMO_MODE: "1", BACKEND_URL: "http://backend" });
    const res = await POST!(post({ video: video(), stroke: "forehand", request: "Fix my forehand" }));
    expect(res.status).toBe(201);
    expect(await res.json()).toEqual(demoJobs[`demo-${kind}`]);
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe("GET /api/rubbers", () => {
  const url = (q: string) => new Request(`http://test/api/rubbers?${q}`);
  it("rejects unknown options", async () => {
    const { GET } = await route("rubbers");
    await expectError(await GET!(url("style=loop"), ctx({})), 400, "spin or speed");
    await expectError(await GET!(url("rubber_type=x"), ctx({})), 400, "rubber type");
    await expectError(await GET!(url("level=pro"), ctx({})), 400, "level");
    await expectError(await GET!(url("budget=0"), ctx({})), 400, "budget");
  });
  it("ranks locally without a backend: within budget, $10 bands down from it, then user score", async () => {
    const { GET } = await route("rubbers");
    const body = await (await GET!(url("style=spin&rubber_type=inverted&level=beginner&budget=45"), ctx({}))).json();
    expect(body.thickness).toBe("1.5-1.8 mm");
    expect(body.results.length).toBe(8);
    expect(body.results.every((r: { price: number }) => r.price <= 45)).toBe(true);
    expect(body.results[0].price).toBeGreaterThan(35);
    const keys = body.results.map((r: { price: number; overall: number }) => [Math.floor((45 - r.price) / 10 + 1e-9), -r.overall]);
    expect(keys).toEqual([...keys].sort((a: number[], b: number[]) => a[0] - b[0] || a[1] - b[1]));
  });
  it("uses the backend when it is set", async () => {
    const fetchMock = vi.fn(async () => Response.json({ thickness: "from backend", results: [] }));
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await route("rubbers", { BACKEND_URL: "http://backend" });
    const body = await (await GET!(url("style=speed&rubber_type=anti_spin&level=advanced&budget=40"), ctx({}))).json();
    expect(body.thickness).toBe("from backend");
    expect(String((fetchMock.mock.calls[0] as unknown[])[0])).toContain("/equipment/rubbers?style=speed&rubber_type=anti_spin&level=advanced&budget=40");
  });
});

// ------------------------------------------------------------------ players

describe("POST /api/players/detect", () => {
  const frame = (type = "image/jpeg", bytes = 3) => new File([new Uint8Array(bytes)], "f.jpg", { type });
  const frames = (n: number, times: string) => {
    const form = new FormData();
    for (let i = 0; i < n; i++) form.append("frames", frame());
    form.append("times", times);
    return new Request("http://test/api", { method: "POST", body: form });
  };

  it("checks the frames like the backend", async () => {
    const { POST } = await route("players");
    await expectError(await POST!(post({})), 422, "at least one frame");
    await expectError(await POST!(frames(9, "1,2,3,4,5,6,7,8,9")), 422, "at most 8 frames");
    await expectError(await POST!(frames(2, "1")), 422, "its time");
    await expectError(await POST!(post({ frames: frame("text/plain"), times: "1" })), 422, "JPEG or PNG");
    await expectError(await POST!(post({ url: "https://example.com/v" })), 422, "YouTube");
  });

  it("skips the picker without a backend", async () => {
    const { POST } = await route("players");
    const res = await POST!(frames(2, "1.5,30"));
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ candidates: [], decisive: true });
  });

  it("passes the frames to the backend and its errors back as {error}", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(Response.json({ candidates: [{ id: 0 }], frame: null, suggested: 0, decisive: false }))
      .mockResolvedValueOnce(Response.json({ detail: "A frame couldn't be read as an image." }, { status: 422 }));
    vi.stubGlobal("fetch", fetch);
    const { POST } = await route("players", { BACKEND_URL: "http://backend" });
    expect(await (await POST!(frames(2, "1.5,30"))).json()).toMatchObject({ decisive: false, suggested: 0 });
    expect(fetch.mock.calls[0][0]).toBe("http://backend/players/detect");
    expect(fetch.mock.calls[0][1].signal).toBeInstanceOf(AbortSignal);   // a page that leaves stops the backend
    await expectError(await POST!(frames(1, "2")), 422, "couldn't be read");
  });
});

describe("POST /api/jobs/[id]/rerun (Change player)", () => {
  const ID = "0123456789abcdef0123456789abcdef";
  it("needs a complete pick", async () => {
    const { POST } = await route("rerun", { BACKEND_URL: "http://backend" });
    await expectError(await POST!(post({}), ctx({ id: ID })), 422, "Pick the player again");
    await expectError(await POST!(post({ player_time: "1", player_box: "0.5,0,0.4,1" }), ctx({ id: ID })), 422, "Pick the player again");
  });
  it("can't re-run a demo job or without a backend", async () => {
    const pick = { player_time: "1", player_box: "0.1,0.1,0.5,0.9" };
    const { POST } = await route("rerun");
    await expectError(await POST!(post(pick), ctx({ id: ID })), 422, "needs the TTSkill backend");
    const demo = await route("rerun", { BACKEND_URL: "http://backend" });
    await expectError(await demo.POST!(post(pick), ctx({ id: "demo-match" })), 422, "needs the TTSkill backend");
  });
  it("forwards the pick to the backend and returns the new job", async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ id: "new", kind: "match", status: "queued" }, { status: 201 }));
    vi.stubGlobal("fetch", fetch);
    const { POST } = await route("rerun", { BACKEND_URL: "http://backend" });
    const res = await POST!(post({ player_time: "1", player_box: "0.1,0.1,0.5,0.9" }), ctx({ id: ID }));
    expect(res.status).toBe(201);
    expect((await res.json()).id).toBe("new");
    expect(fetch.mock.calls[0][0]).toBe(`http://backend/jobs/${ID}/rerun`);
  });
});

describe("POST /api/players/detect for a past job", () => {
  it("accepts a job id instead of frames", async () => {
    const { POST } = await route("players");
    expect((await POST!(post({ job: "0123456789abcdef0123456789abcdef", kind: "coach" }))).status).toBe(200);
    await expectError(await POST!(post({ job: "../etc" })), 422, "Unknown job");
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
