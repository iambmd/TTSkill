import { expect, test, type Page } from "@playwright/test";

// Every page in Vietnamese: the heading, <html lang>, no raw message keys, no console errors
// (next-intl logs a missing key as an error) and no sideways scroll with the longer text.
const pages = [
  ["/", "Pha bóng hay và huấn luyện"],
  ["/autocut", "Cắt bỏ thời gian chết."],
  ["/breakdown", "Vung vợt như VĐV."],
  ["/coach", "Hỏi HLV của bạn."],
  ["/match", "Bạn đánh giống ai?"],
  ["/pros", "VĐV dùng gì"],
  ["/rubbers", "Chọn mặt vợt"],
  ["/jobs/demo-autocut", /pha bóng/i],
  ["/jobs/demo-breakdown", /backspin/i],   // a cached demo's headline stays English, marked as such
  ["/jobs/demo-coach", /fix my forehand/i],
  ["/jobs/demo-match", /Bạn đánh giống/],
] as const;

// "home.title", "job.titles.allDone": what next-intl prints for a key it can't find.
const RAW_KEY = /\b(?:metadata|layout|header|nav|theme|language|common|hands|grips|strokes|offline|errors|validation|home|demoDescriptions|examples|matchSource|submit|coach|breakdown|autocut|match|video|picker|job|autocutWaiting|rallies|coachView|steps|matches|analysedPlayer|gear|rubbers|pros|buy)\.[a-z][A-Za-z_]*(?:\.[A-Za-z_]+)*\b/;

async function inVietnamese(page: Page) {
  await page.context().addCookies([{ name: "NEXT_LOCALE", value: "vi", url: "http://127.0.0.1:3110" }]);
}

function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  return errors;
}

for (const viewport of [{ width: 1440, height: 900 }, { width: 375, height: 844 }]) {
  const mobile = viewport.width === 375;
  test.describe(`Vietnamese at ${viewport.width}px`, () => {
    test.use({ viewport, hasTouch: mobile, isMobile: mobile });
    test.beforeEach(async ({ page }) => {
      await inVietnamese(page);
      await page.route("https://**/*", (route) => route.request().resourceType() === "image"
        ? route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" />' })
        : route.fulfill({ json: {}, headers: { "access-control-allow-origin": "*" } }));
    });

    for (const [path, heading] of pages) {
      test(`${path} is in Vietnamese`, async ({ page }) => {
        const errors = watchErrors(page);
        expect((await page.goto(path))?.ok()).toBe(true);
        await expect(page.locator("html")).toHaveAttribute("lang", "vi");
        await expect(page.locator("main h1")).toHaveText(heading);
        await expect(page.getByRole("group", { name: "Ngôn ngữ" }).getByRole("button", { name: "Tiếng Việt" })).toHaveAttribute("aria-pressed", "true");
        if (path === "/rubbers") await expect(page.locator("main ol li").first()).toBeVisible();
        // The forms whose results the backend writes ask for them in Vietnamese.
        if (["/breakdown", "/coach", "/match"].includes(path)) await expect(page.locator('input[name="lang"]')).toHaveValue("vi");
        if (path.startsWith("/jobs/")) await expect(page.locator("main")).not.toContainText("Loading your result");
        const text = await page.locator("body").innerText();
        expect(text).not.toMatch(RAW_KEY);
        expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0);
        expect(errors.filter((e) => !/Failed to load resource|ERR_CONNECTION_REFUSED|502|503/.test(e))).toEqual([]);
      });
    }
  });
}

test("the EN / VI toggle switches the whole page and remembers the choice", async ({ page }) => {
  await page.goto("/coach");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const language = page.getByRole("group", { name: "Language" });
  await language.getByRole("button", { name: "Vietnamese" }).click();
  await expect(page.locator("main h1")).toHaveText("Hỏi HLV của bạn.");
  await expect(page.locator("html")).toHaveAttribute("lang", "vi");
  await expect(page.getByRole("navigation", { name: "Điều hướng trang" }).getByRole("link", { name: "Phân tích" })).toBeVisible();
  // The coach is asked to write in the page's language.
  await expect(page.locator('input[name="lang"]')).toHaveValue("vi");
  expect((await page.context().cookies()).find((c) => c.name === "NEXT_LOCALE")?.value).toBe("vi");

  await page.reload();
  await expect(page.locator("main h1")).toHaveText("Hỏi HLV của bạn.");
  await page.getByRole("group", { name: "Ngôn ngữ" }).getByRole("button", { name: "Tiếng Anh" }).click();
  await expect(page.locator("main h1")).toHaveText("Ask your coach.");
  await expect(page.locator('input[name="lang"]')).toHaveValue("en");
});

test.describe("a first visit from a Vietnamese browser", () => {
  test.use({ locale: "vi-VN" });
  test("gets Vietnamese without a cookie", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("lang", "vi");
    await expect(page.locator("main h1")).toHaveText("Pha bóng hay và huấn luyện");
  });
});

test("prices follow the locale and stay in US dollars", async ({ page }) => {
  await inVietnamese(page);
  await page.goto("/rubbers?style=spin&level=intermediate&budget=60");
  const price = page.locator("main ol li").first().locator(".stat").last();
  await expect(price).toHaveText(/^\d+\s?US\$$/);
  await expect(page.getByText("Độ dày mút")).toBeVisible();
});

test("the mobile header fits both toggles, the logo and the links", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 844 });
  await inVietnamese(page);
  await page.goto("/");
  const header = page.locator("header");
  const toggle = page.getByRole("group", { name: "Ngôn ngữ" });
  const logo = header.getByRole("link", { name: "TTSkill" });
  const box = async (l: ReturnType<Page["locator"]>) => (await l.boundingBox())!;
  const [t, g] = [await box(toggle), await box(logo)];
  expect(Math.abs(t.y - g.y)).toBeLessThan(16);   // the same row
  expect(t.height).toBeGreaterThanOrEqual(44);    // tap target
  expect(await header.evaluate((h) => h.scrollWidth - h.clientWidth)).toBe(0);
});
