/** "Which one is you?": auto first, ask only when the choice is unclear. */
import { describe, expect, it } from "vitest";
import { needsChoice } from "@/app/player-picker";

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
