/** The checks behind the forms' inline errors and the routes' 422s (limits from shared/limits.json). */
import { describe, expect, it } from "vitest";
import {
  HEIGHT_FT_RANGE, LIMITS, feetInches, fileProblem, heightProblem, mediaProblem, rangeProblem, textProblem,
} from "@/lib/validate";

describe("shared limits", () => {
  it("are the ones the backend reads", () => {
    expect(LIMITS.height_cm).toEqual({ min: 100, max: 230 });
    expect(LIMITS.upload).toMatchObject({ extensions: ["mp4", "mov", "webm", "mkv"], max_mb: 500, max_seconds: 600 });
    expect(LIMITS.link_max_seconds).toMatchObject({ breakdown: 180, autocut: 3600 });
  });
});

describe("heightProblem (cm)", () => {
  it.each(["", "  ", "100", "175", "182.5", "230"])("accepts %j", (h) => expect(heightProblem(h)).toBeNull());
  it.each(["250", "0", "99.9", "230.1"])("rejects %s as out of range", (h) => expect(heightProblem(h)).toContain("between 100 and 230 cm"));
  it.each(["-170", "abc", "5'10", "1e2", "0x64", "NaN", "Infinity", "175cm", "１７５"])("rejects %s as not a number", (h) =>
    expect(heightProblem(h)).toContain("as a number in cm"));
});

describe("feetInches", () => {
  it("converts to cm", () => {
    expect(feetInches("5", "10")).toEqual({ cm: 177.8, error: null });
    expect(feetInches("6", "")).toEqual({ cm: 182.9, error: null });
    expect(feetInches("", "")).toEqual({ cm: null, error: null });
  });
  it("uses the same 100-230 cm range", () => {
    expect(HEIGHT_FT_RANGE).toBe("3 ft 4 in and 7 ft 6 in");
    expect(feetInches("3", "4").cm).toBe(101.6);
    expect(feetInches("7", "6").cm).toBe(228.6);
    expect(feetInches("3", "3").error).toContain("between 3 ft 4 in and 7 ft 6 in");
    expect(feetInches("8", "2").error).toContain("between");
    expect(feetInches("0", "0").error).toContain("between");
  });
  it("rejects text, negatives and 12+ inches", () => {
    expect(feetInches("five", "10").error).toContain("as numbers");
    expect(feetInches("-5", "10").error).toContain("as numbers");
    expect(feetInches("5.5", "").error).toContain("as numbers");
    expect(feetInches("5", "12").error).toBe("Inches go from 0 to 11.");
  });
});

describe("files", () => {
  const file = (name: string, size = 1000) => ({ name, size });
  it.each(["clip.mp4", "IMG_8782.MOV", "rec.webm", "a.b.MKV"])("accepts %s", (n) => expect(fileProblem(file(n))).toBeNull());
  it.each(["clip.avi", "clip.m4v", "clip", "notes.txt", ".mp4x"])("rejects %s", (n) =>
    expect(fileProblem(file(n))).toBe("Upload a video file: MP4, MOV, WebM or MKV."));
  it("caps the size at 500 MB", () => {
    expect(fileProblem(file("a.mp4", 500e6))).toBeNull();
    expect(fileProblem(file("a.mp4", 501e6))).toContain("That file is 501 MB. Upload one under 500 MB");
  });
  it("checks length and resolution when the browser can read them", () => {
    const ok = { duration: 30, width: 1920, height: 1080 };
    expect(mediaProblem(ok)).toBeNull();
    expect(mediaProblem({ ...ok, duration: 1.5 })).toContain("only 1.5 s long. Upload at least 2 seconds");
    expect(mediaProblem({ ...ok, duration: 601 })).toContain("10:01 long. Uploads can be up to 10 minutes");
    expect(mediaProblem({ ...ok, width: 320, height: 180 })).toContain("Re-record it at 480p");
    expect(mediaProblem({ ...ok, width: 240, height: 426 })).toBeNull(); // 240p portrait
    // HEVC the browser can't decode reports 0x0: unknown, so the server decides
    expect(mediaProblem({ ...ok, width: 0, height: 0 })).toBeNull();
    expect(mediaProblem({ duration: NaN, width: 0, height: 0 })).toBeNull();
  });
});

describe("text and ranges", () => {
  it("counts trimmed characters", () => {
    expect(textProblem(`  ${"a".repeat(1000)}\n`, "coach_request", "Your request")).toBeNull();
    expect(textProblem("a".repeat(1001), "coach_request", "Your request")).toContain("up to 1000 characters (it has 1001)");
  });
  it("checks Auto-Cut settings", () => {
    expect(rangeProblem("", "threshold", "Hit threshold")).toBeNull(); // blank = default
    expect(rangeProblem("3.0", "threshold", "Hit threshold")).toBeNull();
    expect(rangeProblem("1", "threshold", "Hit threshold")).toBe("Hit threshold must be between 1.5 and 10.");
    expect(rangeProblem("4", "min_hits", "Min hits", true)).toBeNull();
    expect(rangeProblem("4.5", "min_hits", "Min hits", true)).toBe("Min hits must be a whole number.");
    expect(rangeProblem("1e1", "gap", "Max gap")).toBe("Max gap must be a number.");
  });
});
