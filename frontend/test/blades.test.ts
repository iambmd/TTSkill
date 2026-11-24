import { createElement } from "react";
import { describe, expect, it } from "vitest";
import { buyMenu } from "@/config/affiliates";
import BladesPage from "@/app/blades/page";
import { BladeCard } from "@/app/blades/blade-card";
import { allBlades, band, bladeAllowance, bladeBySlug, combo, handleFilters, hasHandle, layers, recommend, BAND, BLADE_SHARE, RUBBER_RESERVE, FEELS, type Blade, type Handle } from "@/lib/blades";
import { bladeBuyLinks, withBladeBuyLinks } from "@/lib/buy-links";
import proBlades from "@/lib/pro-blades.json";
import pros from "@/lib/pros.json";
import { recommend as recommendRubbers } from "@/lib/rubbers";
import { renderIntl } from "./intl";

const ALL = allBlades();
const BIG = 500;
const names = (rows: { name: string }[]) => rows.map((r) => r.name);
const compact = (s: string) => s.normalize("NFKD").toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]/g, "");

describe("the bundled blade data", () => {
  it("is RevSpin ratings (numbers) with a source link on every blade, and only specs a page stated", () => {
    expect(ALL.length).toBeGreaterThan(400);
    for (const b of ALL) {
      expect(b.url, b.name).toBe(`https://revspin.net/blade/${b.slug}.html`);
      expect(b.ratings, b.name).toBeGreaterThanOrEqual(10);
      for (const k of ["speed", "control", "stiffness", "overall"] as const) expect(b[k], `${b.name} ${k}`).toBeGreaterThan(0);
      if (b.plies !== null || b.weight !== null || b.composition || b.handles.length) expect(b.specSources.length, b.name).toBeGreaterThan(0);
      expect(Object.keys(b).sort(), b.name).toEqual(
        ["brand", "buyLinks", "composition", "control", "fiber", "handles", "hardness", "name", "overall", "plies", "price", "ratings", "slug", "specSources", "speed", "stiffness", "url", "weight"],
      );
    }
  });
  it("finds a blade by slug", () => {
    expect(bladeBySlug("butterfly-viscaria")?.name).toBe("Butterfly Viscaria");
    expect(bladeBySlug("nope")).toBeUndefined();
  });
});

describe("recommend (same logic as the rubbers: drop over budget, rank in steps, best rated first)", () => {
  it("plans a share of the budget for the blade and keeps the rest for one rubber", () => {
    expect([bladeAllowance(150), bladeAllowance(500), bladeAllowance(40), bladeAllowance(20), bladeAllowance(1)]).toEqual([90, 300, 20, 0, 0]);
    for (const budget of [100, 150, 300]) {
      const { results } = recommend("speed", "advanced", budget);
      expect(results.length).toBeGreaterThan(0);
      for (const r of results) {
        expect(r.price, r.name).toBeLessThanOrEqual(bladeAllowance(budget));
        expect(r.combo.budget, r.name).toBeGreaterThanOrEqual(Math.min(RUBBER_RESERVE, budget - r.price));
      }
    }
    expect(BLADE_SHARE).toBe(0.6);
    expect(recommend("spin", "advanced", RUBBER_RESERVE).results).toEqual([]);
  });

  it("ranks by $20 step down from the allowance, then user score", () => {
    const budget = 400;
    const { results } = recommend("spin", "intermediate", budget, "any", "any", 30);
    expect(results.length).toBeGreaterThan(5);
    const keys = results.map((r) => [band(r.price, bladeAllowance(budget)), -r.overall]);
    expect(keys).toEqual([...keys].sort((a, b) => a[0] - b[0] || a[1] - b[1]));
    expect(BAND).toBe(20);
  });

  it("applies the level rules: speed range, control floor, and the 8.0 overall floor", () => {
    for (const r of recommend("speed", "beginner", BIG, "any", "any", 500).results) {
      expect(r.speed).toBeLessThanOrEqual(8.8);
      expect(r.control).toBeGreaterThanOrEqual(8.5);
      expect(r.overall).toBeGreaterThanOrEqual(8.0);
    }
    for (const r of recommend("speed", "advanced", BIG, "any", "any", 500).results) expect(r.speed).toBeGreaterThanOrEqual(8.8);
  });

  it("follows the style: spin is the flexible side, speed the stiff side", () => {
    for (const r of recommend("spin", "intermediate", BIG, "any", "any", 500).results) expect(r.stiffness).toBeLessThanOrEqual(5.8);
    for (const r of recommend("speed", "intermediate", BIG, "any", "any", 500).results) expect(r.stiffness).toBeGreaterThanOrEqual(4.8);
  });

  it("follows the feel: speed against control", () => {
    for (const r of recommend("speed", "intermediate", BIG, "any", "control", 500).results) expect(r.speed - r.control).toBeLessThanOrEqual(-0.4);
    for (const r of recommend("speed", "intermediate", BIG, "any", "speed", 500).results) expect(r.speed - r.control).toBeGreaterThanOrEqual(0.4);
    for (const r of recommend("speed", "intermediate", BIG, "any", "balanced", 500).results) expect(Math.abs(r.speed - r.control)).toBeLessThan(0.4);
    expect(FEELS).toEqual(["any", "control", "balanced", "speed"]);
  });

  it("steers beginners away from fast carbon blades, whether the data or only the name says carbon", () => {
    const results = recommend("speed", "beginner", BIG, "any", "any", 1000).results;
    expect(results.length).toBeGreaterThan(5);
    for (const r of results) expect(r.composite && r.speed >= 8.5, r.name).toBeFalsy();
    // They are not hidden for everyone: the same blades show up for an advanced player.
    const fastCarbon = ALL.filter((b) => layers(b).composite && b.speed >= 8.9 && b.control >= 8.5);
    expect(fastCarbon.length).toBeGreaterThan(0);
    const advanced = names(recommend("speed", "advanced", BIG, "any", "any", 1000).results);
    expect(fastCarbon.some((b) => advanced.includes(b.name))).toBe(true);
    expect(names(results)).not.toContain("Butterfly Viscaria");
  });

  it("says when the carbon comes from the name, and never invents a composition", () => {
    const inferred = ALL.filter((b) => b.composition === null && layers(b).inferred);
    expect(inferred.length).toBeGreaterThan(0);
    for (const b of inferred) expect(layers(b)).toEqual({ composite: true, inferred: true });
    const known = ALL.find((b) => b.composition === "wood")!;
    expect(layers(known)).toEqual({ composite: false, inferred: false });
    expect(layers({ name: "Stiga Allround Classic", composition: null })).toEqual({ composite: null, inferred: false });
  });
});

describe("the handle filter", () => {
  it("offers only handles at least one blade is known to have", () => {
    const offered = handleFilters();
    expect(offered[0]).toBe("any");
    const have = new Set(ALL.flatMap((b) => b.handles));
    for (const h of offered.slice(1)) expect(h === "penhold" ? have.has("CS") || have.has("JP") || have.has("PH") : have.has(h as Handle)).toBe(true);
    for (const h of ["FL", "ST", "AN"] as const) expect(offered.includes(h)).toBe(have.has(h));
  });

  it("matches only blades a source says have that handle, and counts the ones with no handle information", () => {
    const any = recommend("speed", "advanced", BIG, "any", "any", 1000);
    expect(any.noHandleInfo).toBe(0);
    const fl = recommend("speed", "advanced", BIG, "FL", "any", 1000);
    expect(fl.results.length).toBeGreaterThan(0);
    for (const r of fl.results) expect(r.handles).toContain("FL");
    expect(fl.noHandleInfo).toBe(any.results.filter((r) => r.handles.length === 0).length);
    const penhold = recommend("speed", "advanced", BIG, "penhold", "any", 1000).results;
    for (const r of penhold) expect(r.handles.some((h) => ["CS", "JP", "PH"].includes(h))).toBe(true);
    expect(hasHandle({ handles: [] } as unknown as Blade, "FL")).toBe(false);
    expect(hasHandle({ handles: [] } as unknown as Blade, "any")).toBe(true);
  });
});

describe("the matching rubber", () => {
  it("is the rubber recommender's pick for the same style and level with what is left after the blade", () => {
    const { results } = recommend("spin", "intermediate", 150);
    for (const r of results) {
      expect(r.combo.budget).toBe(Math.floor(150 - r.price));
      const [pick] = recommendRubbers("spin", "inverted", "intermediate", r.combo.budget, 1).results;
      expect(r.combo.rubber?.name).toBe(pick?.name);
      if (r.combo.rubber?.price != null) expect(r.combo.rubber.price).toBeLessThanOrEqual(r.combo.budget);
    }
    expect(results.some((r) => r.combo.rubber)).toBe(true);
  });
  it("is empty, not made up, when nothing is left", () => {
    expect(combo(ALL[0], "spin", "advanced", 0)).toEqual({ budget: 0, rubber: null });
  });
});

describe("buy links", () => {
  it("come from the blade catalogue: US product pages, no Amazon until a person has checked them", () => {
    const linked = ALL.filter((b) => b.buyLinks?.length);
    expect(linked.length).toBeGreaterThan(80);
    for (const b of linked) for (const l of b.buyLinks!) {
      expect(["official", "retailer"]).toContain(l.type);
      expect(l.url.startsWith("https://")).toBe(true);
      expect(l.url).not.toMatch(/amazon\./);
    }
    expect(bladeBuyLinks("No such blade")).toEqual([]);
    expect(withBladeBuyLinks({ name: "Butterfly Viscaria" }).buyLinks).toEqual(bladeBuyLinks("Butterfly Viscaria"));
  });

  it("use the shared menu: a tagged store is pinned first, the rest keep their order", () => {
    const links = bladeBuyLinks("Butterfly Viscaria");
    expect(links.map((l) => l.store)).toEqual(expect.arrayContaining(["Paddle Palace", "TableTennisStore"]));
    const plain = buyMenu({ buyLinks: links }, {});
    expect(plain.disclosure).toBe(false);
    const tagged = buyMenu({ buyLinks: links }, { "Paddle Palace": { host: "paddlepalace.com", param: "ref", tag: "ttskill" } });
    expect(tagged.links[0].store).toBe("Paddle Palace");
    expect(tagged.links[0].url).toContain("ref=ttskill");
    expect(tagged.disclosure).toBe(true);
    expect(links.every((l) => !l.url.includes("ref="))).toBe(true);   // the catalogue stays clean
  });
});

describe("pro setups link to blade entries only where the exact blade exists", () => {
  it("points each linked pro blade at a blade with that name", () => {
    const labels = new Set(pros.players.map((p) => p.blade));
    const map = proBlades as Record<string, string>;
    expect(Object.keys(map).length).toBeGreaterThan(0);
    for (const [label, slug] of Object.entries(map)) {
      expect(labels.has(label), label).toBe(true);
      const blade = bladeBySlug(slug);
      expect(blade, slug).toBeDefined();
      expect(compact(label.replace(/\s*\((?:FL|ST|AN|CS|JS)\)\s*$/i, "")), label).toBe(compact(blade!.name));
    }
    expect(map["Butterfly Viscaria Golden (FL)"]).toBeUndefined();   // a different blade: no entry, no link
  });
});

describe("the blade card", () => {
  const viscaria = ALL.find((b) => b.slug === "butterfly-viscaria")!;
  const card = (locale: "en" | "vi", withCombo = true) =>
    renderIntl(createElement(BladeCard, { blade: { ...viscaria, ...layers(viscaria) }, rank: 1, combo: withCombo ? combo(viscaria, "spin", "advanced", 300) : undefined }), locale);

  it("says Source: RevSpin, links to the blade's RevSpin page, and shows our own summary and the confirmed specs", () => {
    const html = card("en");
    expect(html).toContain("Source:");
    expect(html).toMatch(/<a href="https:\/\/revspin\.net\/blade\/butterfly-viscaria\.html"[^>]*>RevSpin<\/a>/);
    expect(html).toContain("179 ratings");
    expect(html).toContain("A fast blade with good control and a medium-flex feel.");
    expect(html).toContain("7 plies");
    expect(html).toContain("86 g");
    expect(html).toContain("Rubber to pair with it");
    expect(html).not.toMatch(/\b(?:blades|buy|rubbers)\.[a-z]\w+/);
  });

  it("is in Vietnamese with the settled terms, and still credits RevSpin", () => {
    const html = card("vi");
    expect(html).toContain("Nguồn:");
    expect(html).toContain(">RevSpin</a>");
    expect(html).toContain("Cốt vợt");
    expect(html).toContain("Mặt vợt đi kèm");
    expect(html).not.toMatch(/\b(?:blades|buy|rubbers)\.[a-z]\w+/);
  });

  it("leaves out a spec nobody states and says when a blade has no verified link", () => {
    const bare = ALL.find((b) => b.plies === null && b.weight === null && !b.composition && b.handles.length === 0 && !layers(b).inferred && !b.buyLinks?.length)!;
    const html = renderIntl(createElement(BladeCard, { blade: { ...bare, ...layers(bare) } }), "en");
    expect(html).toContain("Specs not confirmed yet.");
    expect(html).toContain("No verified US store link yet");
    expect(html).not.toMatch(/ plies|\d g<|Handles:/);
  });
});

describe("the Blade Finder page", () => {
  it.each([
    { budget: "40", expected: 40 }, { budget: undefined, expected: 150 }, { budget: "0.5", expected: 150 },
    { budget: "501", expected: 150 }, { budget: ["40", "80"], expected: 150 },
  ])("sets the budget to $expected for query value $budget", async ({ budget, expected }) => {
    const html = renderIntl(await BladesPage({ searchParams: Promise.resolve({ budget }) }));
    expect(html).toMatch(new RegExp(`<input[^>]+id="budget"[^>]+value="${expected}"`));
  });

  it("offers only handle filters that have blades, in both languages", async () => {
    for (const locale of ["en", "vi"] as const) {
      const html = renderIntl(await BladesPage({ searchParams: Promise.resolve({}) }), locale);
      expect(html).not.toMatch(/\b(?:blades|gear)\.[a-z]\w+/);
      for (const h of handleFilters().slice(1)) expect(html).toContain(`value="${h}"`);
    }
    // a handle nobody sells in the data is not offered, even if the URL asks for it
    const have = new Set(ALL.flatMap((b) => b.handles));
    const missing = (["FL", "ST", "AN"] as const).find((h) => !have.has(h));
    if (missing) expect(renderIntl(await BladesPage({ searchParams: Promise.resolve({ handle: missing }) }))).not.toContain(`value="${missing}"`);
  });
});
