/** English and Vietnamese: the two catalogues match, every message formats, the locale is
 * picked from the cookie then the browser, and pages, checks and API errors follow it. */
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";
import demoJobs from "@/lib/demo-jobs.json";
import { fromAcceptLanguage, negotiate, requestLocale } from "@/lib/locale";
import { MESSAGES, translator } from "@/lib/messages";
import type { Job } from "@/lib/submit";
import { fileProblem, heightProblem, langProblem, mediaProblem, minutes } from "@/lib/validate";
import { linkProblem } from "@/lib/youtube";
import { CoachView } from "@/app/jobs/[id]/coach-view";
import { Steps } from "@/app/jobs/[id]/steps";
import { renderIntl } from "./intl";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push() {} }) }));

type Tree = { [key: string]: string | Tree };
const flat = (tree: Tree, prefix = ""): Record<string, string> =>
  Object.fromEntries(Object.entries(tree).flatMap(([k, v]) =>
    typeof v === "string" ? [[`${prefix}${k}`, v]] : Object.entries(flat(v, `${prefix}${k}.`))));
const en = flat(MESSAGES.en as Tree);
const vn = flat(MESSAGES.vi as Tree);
// Top-level argument names only: "{n, plural, other {# phút}}" names n, not its branches.
const args = (m: string) => {
  const names = new Set<string>();
  let depth = 0;
  for (let i = 0; i < m.length; i++) {
    if (m[i] === "{") {
      if (depth === 0) names.add(/^\{\s*(\w+)/.exec(m.slice(i))?.[1] ?? "");
      depth++;
    } else if (m[i] === "}") depth--;
  }
  return [...names].sort();
};

describe("the catalogues", () => {
  it("have the same keys in English and Vietnamese, none empty", () => {
    expect(Object.keys(vn).sort()).toEqual(Object.keys(en).sort());
    for (const [k, v] of Object.entries({ ...en, ...vn })) expect(v.trim(), k).not.toBe("");
  });

  it("use the same placeholders in both languages", () => {
    for (const key of Object.keys(en)) expect(args(vn[key]), key).toEqual(args(en[key]));
  });

  it("format every message in both languages (no raw key names, no ICU errors)", () => {
    for (const locale of ["en", "vi"] as const) {
      const t = translator(locale, "");
      for (const [key, message] of Object.entries(locale === "en" ? en : vn)) {
        const values = Object.fromEntries(args(message).map((a) => [a, a === "n" ? 2 : "x"]));
        const out = (t as unknown as (k: string, v: object) => string)(key, values);
        expect(out, key).not.toBe(key);
        expect(out, key).not.toMatch(/[{}]/);
      }
    }
  });

  it("use the Vietnamese terms players use", () => {
    expect(vn["strokes.forehand"]).toBe("Thuận tay");
    expect(vn["strokes.backhand"]).toBe("Trái tay");
    expect(vn["pros.blade"]).toBe("Cốt vợt");
    expect(vn["strokes.serve"]).toBe("Giao bóng");
    expect(vn["strokes.forehand_topspin"]).toContain("Giật");
    expect(vn["job.rally"]).toContain("Pha bóng");
    expect(vn["gear.rubbers"]).toContain("mặt vợt");
  });
});

describe("the locale", () => {
  it("comes from the cookie first, then Accept-Language, then English", () => {
    expect(negotiate("vi", "en-US,en")).toBe("vi");
    expect(negotiate("en", "vi-VN")).toBe("en");
    expect(negotiate(undefined, "vi-VN,vi;q=0.9,en;q=0.8")).toBe("vi");
    expect(negotiate("fr", "fr-FR,de;q=0.9")).toBe("en");   // unknown cookie and languages
    expect(negotiate(null, null)).toBe("en");
  });

  it("follows the weights in Accept-Language", () => {
    expect(fromAcceptLanguage("en;q=0.5,vi;q=0.9")).toBe("vi");
    expect(fromAcceptLanguage("fr, vi;q=0.2, en;q=0.1")).toBe("vi");
    expect(fromAcceptLanguage("vi;q=0")).toBeNull();
  });

  it("of an API request is read from its own headers", () => {
    const req = (headers: Record<string, string>) => new Request("http://test", { headers });
    expect(requestLocale(req({ cookie: "theme=x; NEXT_LOCALE=vi" }))).toBe("vi");
    expect(requestLocale(req({ "accept-language": "vi" }))).toBe("vi");
    expect(requestLocale(req({}))).toBe("en");
  });
});

describe("checks in Vietnamese", () => {
  const t = translator("vi", "validation");
  const common = translator("vi", "common");

  it("say what to do next in Vietnamese, with the same limits", () => {
    expect(fileProblem({ name: "a.txt", size: 1 }, t)).toBe("Hãy tải lên một tệp video: MP4, MOV, WebM hoặc MKV.");
    expect(fileProblem({ name: "a.txt", size: 1 })).toBe("Upload a video file: MP4, MOV, WebM or MKV.");
    expect(heightProblem("300", t)).toContain("từ 100 đến 230 cm");
    expect(mediaProblem({ duration: 1, width: 1280, height: 720 }, t, common)).toContain("giây");
    expect(minutes(600, common)).toBe("10 phút");
    expect(minutes(60)).toBe("1 minute");
    expect(linkProblem("https://youtube.com/playlist?list=x", t)).toContain("danh sách phát");
  });

  it("accept only en and vi as the AI's language", () => {
    const form = (lang?: string) => { const f = new FormData(); if (lang !== undefined) f.set("lang", lang); return f; };
    expect(langProblem(form())).toBeNull();
    expect(langProblem(form("vi"))).toBeNull();
    expect(langProblem(form("fr"))).toBe("Language must be en or vi.");
    expect(langProblem(form("fr"), t)).toBe("Ngôn ngữ phải là en hoặc vi.");
  });
});

describe("API routes", () => {
  const post = (fields: Record<string, string>, headers: Record<string, string> = {}) => {
    const form = new FormData();
    for (const [k, v] of Object.entries(fields)) form.set(k, v);
    return new Request("http://test/api", { method: "POST", body: form, headers });
  };

  it("answer in the language of the page that called them", async () => {
    const { POST } = await import("@/app/api/jobs/coach/route");
    const inVi = await POST(post({ request: "" }, { cookie: "NEXT_LOCALE=vi" }));
    expect((await inVi.json()).error).toContain("Hãy cho HLV biết");
    const en = await POST(post({ request: "" }));
    expect((await en.json()).error).toContain("Tell the coach what you want");
  });

  it("refuse an unknown lang on breakdown and coach", async () => {
    for (const name of ["breakdown", "coach"] as const) {
      const { POST } = await import(`@/app/api/jobs/${name}/route`);
      const res = await POST(post({ request: "fix my forehand", text: "loops", lang: "fr" }));
      expect(res.status, name).toBe(422);
      expect((await res.json()).error, name).toBe("Language must be en or vi.");
    }
  });
});

describe("pages in Vietnamese", () => {
  const coach = (demoJobs as Record<string, Job>)["demo-coach"];

  it("translate the result page and mark the cached demo's AI text as English only", () => {
    const html = renderIntl(createElement(CoachView, { job: coach, debug: false }), "vi");
    expect(html).toContain("Nhận xét cho bạn");
    expect(html).toContain("Chỉ có tiếng Anh");
    expect(html).toContain('lang="en"');
    expect(html).not.toContain("Your coaching");
  });

  it("show no badge in English, and none on a live job's text", () => {
    expect(renderIntl(createElement(CoachView, { job: coach, debug: false }))).not.toContain("English only");
    const live = renderIntl(createElement(Steps, { b: coach.breakdown! }), "vi");
    expect(live).toContain("Từng bước");
    expect(live).not.toContain("Chỉ có tiếng Anh");
  });
});

describe("numbers", () => {
  it("format with the locale, prices always in US dollars", async () => {
    const { thicknessText } = await import("@/app/rubbers/rubber-finder");
    const { createFormatter } = await import("next-intl");
    const { usd, usdSymbol } = await import("@/lib/format");
    const format = (locale: string) => createFormatter({ locale, timeZone: "UTC" });
    expect(usd(format("en") as never, 59.9)).toBe("$59.90");
    expect(usd(format("vi") as never, 59.9)).toMatch(/^59,90\s?US\$$/);
    expect(usdSymbol("vi")).toBe("US$");
    const t = translator("vi", "rubbers") as never;
    expect(thicknessText("1.8-2.0 mm", t, format("vi") as never)).toBe("1,8-2,0 mm");
    expect(thicknessText("2.1 mm or max", t, format("vi") as never)).toBe("2,1 mm hoặc max");
    expect(thicknessText("OX (no sponge) to 0.5 mm", t, format("vi") as never)).toBe("OX (không mút) đến 0,5 mm");
  });
});
