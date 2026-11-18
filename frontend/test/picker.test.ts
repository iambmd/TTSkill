/** "Which one is you?": auto first, ask only when the choice is unclear. */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CANT_READ, CHOOSE, LOOKUP_TIMEOUT_MS, PICK_PLAYER, TOO_LONG, needsChoice, nextEvent, pickerProblem, withTimeout,
} from "@/app/player-picker";

const players = (n: number) => Array.from({ length: n }, (_, id) => ({ id }));

describe("player picker", () => {
  it("doesn't ask when nobody or one player is found", () => {
    expect(needsChoice(null, false)).toBe(false);
    expect(needsChoice({ candidates: [], decisive: true } as never, false)).toBe(false);
    expect(needsChoice({ candidates: players(1), decisive: true } as never, true)).toBe(false);
  });
  it("doesn't ask when one player is clearly nearest, unless you tap Change", () => {
    const found = { candidates: players(2), decisive: true } as never;
    expect(needsChoice(found, false)).toBe(false);
    expect(needsChoice(found, true)).toBe(true);
  });
  it("asks when two players take turns being nearest", () => {
    expect(needsChoice({ candidates: players(2), decisive: false } as never, false)).toBe(true);
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
  const base = { finding: false, failed: null, skipped: false, asking: false, chosen: false };
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
