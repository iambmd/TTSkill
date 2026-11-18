/** "Which one is you?": auto first, ask only when the choice is unclear. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CANT_READ, CHOOSE, FRAMES, NOBODY_CHOOSE, pickerView, LINK_TIMEOUT_MS, LOOKUP_TIMEOUT_MS, PICK_PLAYER, TOO_LONG, lookupLog, needsChoice, nextEvent,
  pickerProblem, withTimeout, frameTimes, serverCanRead,
} from "@/app/player-picker";
import { withoutStagedFile } from "@/lib/submit";

const players = (n: number) => Array.from({ length: n }, (_, id) => ({ id }));
const base = { finding: false, failed: null, skipped: false, asking: false, chosen: false };

describe("player picker: what to show by how many players we found", () => {
  it("says so when nobody is found, and offers 'Analyse anyway'", () => {
    expect(pickerView({ candidates: [] }, false)).toBe("nobody");
    expect(pickerProblem({ ...base, nobody: true })).toBe(NOBODY_CHOOSE);
    expect(pickerProblem({ ...base, nobody: true, skipped: true })).toBeNull();
  });
  it("analyses the one player found without asking; Change player opens the picker", () => {
    expect(pickerView({ candidates: players(1) as never }, false)).toBe("one");
    expect(needsChoice({ candidates: players(1) as never }, false)).toBe(false);
    expect(pickerView({ candidates: players(1) as never }, true)).toBe("pick");
  });
  it("always asks when there are two or more, even when one is nearest the camera", () => {
    expect(pickerView({ candidates: players(2), decisive: true } as never, false)).toBe("pick");
    expect(pickerView({ candidates: players(3) as never }, false)).toBe("pick");
  });
  it("counts only real players; background people are one tap away", () => {
    const bench = [{ id: 1, background: "still" }] as never;
    expect(pickerView({ candidates: players(1) as never, others: bench }, false)).toBe("one");
    expect(pickerView({ candidates: [], others: bench }, false)).toBe("nobody");
    expect(pickerView({ candidates: [], others: bench }, true)).toBe("pick");   // "Show everyone we saw"
  });
  it("stays out of the way when nothing could look (stub or demo mode)", () => {
    expect(pickerView(null, false)).toBe("hidden");
    expect(pickerView({ candidates: [], available: false }, false)).toBe("hidden");
  });
});

describe("the picker can't hang", () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it("gives up on a video that never fires seeked (Chrome with an iPhone HEVC file)", async () => {
    const video = new EventTarget();   // never dispatches anything
    const waiting = nextEvent(video, "seeked", 6000, CANT_READ);
    const result = expect(waiting).rejects.toThrow(CANT_READ);
    await vi.advanceTimersByTimeAsync(6000);
    await result;
  });

  it("goes on when the event arrives, and fails at once on a decode error", async () => {
    const video = new EventTarget();
    const loaded = nextEvent(video, "loadeddata", 10000, CANT_READ);
    video.dispatchEvent(new Event("loadeddata"));
    await expect(loaded).resolves.toBeUndefined();
    const broken = nextEvent(video, "seeked", 6000, CANT_READ);
    video.dispatchEvent(new Event("error"));
    await expect(broken).rejects.toThrow(CANT_READ);
  });

  it("stops waiting for a lookup that never answers after 30 s", async () => {
    expect(LOOKUP_TIMEOUT_MS).toBe(30_000);
    const never = new Promise<never>(() => {});
    const result = expect(withTimeout(never, LOOKUP_TIMEOUT_MS, TOO_LONG)).rejects.toThrow(TOO_LONG);
    await vi.advanceTimersByTimeAsync(LOOKUP_TIMEOUT_MS);
    await result;
    await expect(withTimeout(Promise.resolve(7), 1000, TOO_LONG)).resolves.toBe(7);
  });
});

describe("what blocks the submit button", () => {
  it("waits while looking, asks after a failure, and never blocks after 'Analyse anyway'", () => {
    expect(pickerProblem({ ...base, finding: true })).toContain("Finding the players");
    expect(pickerProblem({ ...base, failed: TOO_LONG })).toBe(CHOOSE);
    expect(pickerProblem({ ...base, finding: true, skipped: true })).toBeNull();
    expect(pickerProblem({ ...base, failed: CANT_READ, skipped: true })).toBeNull();
  });
  it("asks for a tap only when the choice is unclear", () => {
    expect(pickerProblem({ ...base, asking: true })).toBe(PICK_PLAYER);
    expect(pickerProblem({ ...base, asking: true, chosen: true })).toBeNull();
    expect(pickerProblem(base)).toBeNull();
  });
});

describe("where a lookup's time went", () => {
  it("logs the frame grab, the request and the backend's part in the console", () => {
    const found = { candidates: [{}, {}] as never, frames: [{ time: 11.7, people: 2 }, { time: 35.1, people: 1 }], timing: { next_s: 1.2, total_s: 1.19, seconds: 1.16 } };
    expect(lookupLog({ grabMs: 470, frames: 2, bytes: 2048, requestMs: 1450, found })).toBe(
      "[players] drew 2 frames (2 KB) in 0.47 s, answer in 1.45 s (Next.js 1.2 s, backend 1.19 s, detect 1.16 s); people per frame 11.7s:2 35.1s:1; 2 players");
  });
  it("gives a link time to download: a 3-minute video took longer than the 30 s limit", () => {
    expect(LINK_TIMEOUT_MS).toBeGreaterThanOrEqual(90_000);
    expect(LOOKUP_TIMEOUT_MS).toBe(30_000);
  });
});

describe("which frames the browser draws", () => {
  it("spreads 12 over the whole video, so a player who walks in late is in several", () => {
    const times = frameTimes(215);   // IMG_8782, 3:35
    expect(times).toHaveLength(FRAMES);
    expect(FRAMES).toBe(12);
    expect(times[0]).toBeLessThan(215 * 0.05);
    expect(times.at(-1)!).toBeGreaterThan(215 * 0.95);
    expect(times.filter((t) => t >= 215 * 0.75)).toHaveLength(3);   // in the last quarter alone
  });
});

describe("a video the browser can't read (iPhone HEVC in Chrome)", () => {
  it("is sent to the server instead of failing", () => {
    expect(serverCanRead(new Error(CANT_READ))).toBe(true);
    expect(serverCanRead(new Error(TOO_LONG))).toBe(false);
  });
  it("goes up once: the job takes the kept upload by its token", () => {
    const form = new FormData();
    form.append("video", new File([new Uint8Array(10)], "IMG_0001.MOV", { type: "video/quicktime" }));
    form.append("staged", "0123456789abcdef0123456789abcdef.mov");
    const sent = withoutStagedFile(form);
    expect(sent.get("video")).toBeNull();
    expect(sent.get("staged")).toBe("0123456789abcdef0123456789abcdef.mov");
    const plain = new FormData();
    plain.append("video", new File([new Uint8Array(10)], "a.mp4", { type: "video/mp4" }));
    expect(withoutStagedFile(plain).get("video")).toBeInstanceOf(File);
  });
});
