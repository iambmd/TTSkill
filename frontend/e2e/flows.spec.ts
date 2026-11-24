import { expect, test, type Locator } from "@playwright/test";

test.use({ viewport: { width: 375, height: 844 }, hasTouch: true, isMobile: true });

async function expectBuyLinks(links: Locator) {
  expect(await links.count()).toBeGreaterThan(0);
  for (const link of await links.all()) {
    const url = new URL((await link.getAttribute("href"))!);
    expect(url.protocol).toBe("https:");
    expect(url.pathname).not.toBe("/");
    await expect(link).toHaveAttribute("target", "_blank");
    if (url.hostname === "www.amazon.com") expect(url.pathname).toMatch(/^\/dp\/[A-Z0-9]{10}$/);
  }
}

test("Home stays useful offline and Retry restores the keyboard upload target", async ({ page }) => {
  await page.goto("/");
  const notice = page.locator("main").getByRole("alert");
  await expect(notice).toContainText("Live analysis is offline");
  const retry = page.getByRole("button", { name: "Retry", exact: true });
  await retry.click();
  await expect(retry).toBeEnabled();

  await page.route("**/api/health", route => route.fulfill({ json: { ok: true } }));
  await retry.click();
  const upload = page.getByLabel("Upload your match", { exact: true });
  await expect(upload).toBeFocused();
  const dataTransfer = await page.evaluateHandle(() => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(["notes"], "notes.txt", { type: "text/plain" }));
    return transfer;
  });
  await page.locator("label").filter({ has: upload }).dispatchEvent("drop", { dataTransfer });
  await expect(notice).toContainText("Choose an MP4 or MOV video");
});

test("the quiz opens Rubber Finder and both gear pages expose clean purchase links", async ({ page }) => {
  await page.goto("/");
  const gear = page.getByRole("region", { name: "Gear picks" });
  const featured = gear.getByRole("list", { name: "Featured rubbers" });
  await expectBuyLinks(featured.getByRole("link", { name: /^Buy in the US:/ }));
  const secondary = featured.getByRole("group", { name: "US stores for Butterfly Tenergy 05" });
  await expect(secondary.getByText("Also at")).toBeVisible();
  await expectBuyLinks(secondary.getByRole("link"));

  const quiz = page.getByRole("region", { name: "Find your rubber" });
  await quiz.getByRole("button", { name: /^speed$/i }).click();
  await quiz.getByRole("button", { name: /^advanced$/i }).click();
  await expect(quiz.getByRole("status")).toContainText("Your pick");
  await quiz.getByRole("link", { name: "Open Rubber Finder" }).click();
  await expect(page).toHaveURL(/\/rubbers\?style=speed&level=advanced&budget=60$/);
  await expect(page.getByRole("radio", { name: /^Speed/ })).toBeChecked();
  await expect(page.getByRole("radio", { name: /^Advanced/ })).toBeChecked();
  const finderLinks = page.locator("main").getByRole("link", { name: /^Buy in the US:/ });
  await expect(finderLinks.first()).toBeVisible();
  await expectBuyLinks(finderLinks);
  await page.getByLabel("Budget per sheet").fill("85");
  const finderStores = page.getByRole("group", { name: "US stores for Butterfly Tenergy 05", exact: true });
  await expect(finderStores.getByText("Also at")).toBeVisible();
  await expectBuyLinks(finderStores.getByRole("link"));

  await page.route("https://**/*", route => route.fulfill({ json: {}, headers: { "access-control-allow-origin": "*" } }));
  await page.getByRole("link", { name: "Pro setups", exact: true }).click();
  await page.getByRole("searchbox", { name: "Player" }).fill("wang chuqin");
  const pro = page.getByRole("article");
  await expect(pro).toHaveCount(1);
  await expect(pro.getByRole("heading", { name: "Wang Chuqin" })).toBeVisible();
  await expectBuyLinks(pro.getByRole("link", { name: /^Buy in the US:/ }));
  await expectBuyLinks(pro.getByRole("link", { name: "Amazon (other seller)", exact: true }));
});

test("the offline Home quiz updates the top pick and carries the budget to Rubber Finder", async ({ page }) => {
  await page.goto("/");
  const quiz = page.getByRole("region", { name: "Find your rubber" });
  const budget = quiz.getByRole("group", { name: "Budget per sheet" });
  const result = quiz.getByRole("status");
  const finder = quiz.getByRole("link", { name: "Open Rubber Finder" });
  await expect(budget.getByRole("button", { name: "$60", exact: true })).toHaveAttribute("aria-pressed", "true");
  await quiz.getByRole("button", { name: /^spin$/i }).click();
  await quiz.getByRole("button", { name: /^intermediate$/i }).click();
  await expect(result).toContainText("Your pick");
  const defaultPick = await result.getByText(/\$\d+\.\d{2}/).textContent();
  await expectBuyLinks(quiz.getByRole("link", { name: /^Buy in the US:/ }));

  await budget.getByRole("button", { name: "$100+", exact: true }).click();
  await expect(finder).toHaveAttribute("href", "/rubbers?style=spin&level=intermediate&budget=500");
  await budget.getByRole("button", { name: "$40", exact: true }).click();
  const price = await result.getByText(/\$\d+\.\d{2}/).textContent();
  expect(price).not.toBe(defaultPick);
  expect(Number(price?.slice(1))).toBeLessThanOrEqual(40);
  const pick = (await result.locator("strong").textContent())!;
  await expectBuyLinks(quiz.getByRole("link", { name: /^Buy in the US:/ }));

  await finder.click();
  await expect(page).toHaveURL(/\/rubbers\?style=spin&level=intermediate&budget=40$/);
  await expect(page.getByRole("radio", { name: /^Spin/ })).toBeChecked();
  await expect(page.getByRole("radio", { name: /^Intermediate/ })).toBeChecked();
  await expect(page.getByRole("spinbutton", { name: "Budget per sheet" })).toHaveValue("40");
  await expect(page.locator("main ol").getByRole("listitem").first()).toContainText(pick);
});

test("the Home quiz suggests a higher budget when nothing fits", async ({ page }) => {
  await page.route("**/api/rubbers?*budget=40&rubber_type=inverted&demo=1", route => route.fulfill({ json: { results: [] } }));
  await page.goto("/");
  const quiz = page.getByRole("region", { name: "Find your rubber" });
  await quiz.getByRole("button", { name: "$40", exact: true }).click();
  await quiz.getByRole("button", { name: /^spin$/i }).click();
  await quiz.getByRole("button", { name: /^intermediate$/i }).click();
  await expect(quiz.getByRole("status")).toHaveText("Nothing under $40 yet. Try a higher budget.");
});

test("mobile navigation keeps the selected theme and the cached demo plays", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Switch to light mode" }).click();
  const nav = page.getByRole("navigation", { name: "Site navigation" });
  for (const name of ["Coach", "Breakdown", "Pro match", "Auto-Cut", "Gear", "Home"]) {
    const link = nav.getByRole("link", { name, exact: true });
    await link.click();
    await expect(link).toHaveAttribute("aria-current", "page");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  }

  await page.getByRole("button", { name: "Play match highlights after" }).click();
  const clip = page.locator('video[aria-label="Match highlights, after"]');
  await expect.poll(() => clip.evaluate(video => (video as HTMLVideoElement).currentTime)).toBeGreaterThan(0.2);
  await page.getByRole("link", { name: "Try it: Coach" }).click();
  await expect(page).toHaveURL(/\/jobs\/demo-coach$/);
  await expect(page.getByRole("heading", { name: "Your coaching" })).toBeVisible();
});

test("a live result shows a retry when analysis is offline", async ({ page }) => {
  await page.goto("/jobs/sample-live-job");
  await expect(page.locator("main").getByRole("alert")).toContainText("analysis server is offline");
  const retry = page.getByRole("button", { name: "Retry", exact: true });
  const checked = page.waitForResponse(response => response.url().endsWith("/api/jobs/sample-live-job"));
  await retry.click();
  await checked;
  await expect(retry).toBeEnabled();
});

test("a broken Wikipedia thumbnail falls back to the player's initials", async ({ page }) => {
  await page.route("https://**/*", route => route.fulfill({ json: {}, headers: { "access-control-allow-origin": "*" } }));
  await page.route("**/page/summary/Chen_Meng", route => route.fulfill({
    json: { type: "standard", description: "A table tennis player", thumbnail: { source: "/missing-portrait.png" } },
    headers: { "access-control-allow-origin": "*" },
  }));
  await page.route("**/missing-portrait.png", route => route.fulfill({ contentType: "image/png", body: "invalid png" }));
  const portrait = page.waitForResponse(response => response.url().endsWith("/missing-portrait.png"));
  await page.goto("/pros");
  await page.getByRole("searchbox", { name: "Player" }).fill("Chen Meng");
  await portrait;
  await expect(page.getByRole("article").getByText("CM", { exact: true })).toBeVisible();
});

test("Blade Finder: filters narrow the list, each blade credits RevSpin and pairs with a rubber", async ({ page }) => {
  await page.goto("/blades?style=speed&level=advanced&budget=300");
  const cards = page.locator("main ol > li");
  await expect(cards.first()).toBeVisible();
  const first = cards.first();
  await expect(first.getByRole("link", { name: "RevSpin" })).toHaveAttribute("href", /^https:\/\/revspin\.net\/blade\/[a-z0-9-]+\.html$/);
  await expect(first).toContainText("Source:");
  await expect(first).toContainText("Rubber to pair with it");
  // A blade with no verified store says so; the ones with links (and the paired rubbers) use the shared buy menu.
  await expect(page.getByRole("group", { name: /^US stores for / }).first()).toBeVisible();

  const before = await cards.allInnerTexts();
  await page.getByRole("radio", { name: "More control" }).check({ force: true });
  await expect.poll(async () => (await cards.allInnerTexts()).join()).not.toBe(before.join());

  await page.getByRole("radio", { name: "Flared (FL)" }).check({ force: true });
  await expect.poll(async () => {
    const texts = await cards.allInnerTexts();
    return texts.length > 0 && texts.every((text) => /Handles: .*Flared \(FL\)/.test(text));
  }).toBe(true);

  await page.getByLabel("Budget for the blade and one rubber").fill("20");
  await expect(page.getByText("Nothing matches yet.")).toBeVisible();
});

test("Blade Finder steers a beginner away from fast carbon blades", async ({ page }) => {
  await page.goto("/blades?style=speed&level=advanced&budget=500");
  const cards = page.locator("main ol > li");
  await expect(cards.first()).toBeVisible();
  await page.getByRole("radio", { name: "Beginner" }).check({ force: true });
  // Wait for the beginner list to replace the advanced one, then check every card against the rule.
  await expect.poll(async () => {
    const texts = await cards.allInnerTexts();
    return texts.length > 0 && texts.every((text) => Number(/Speed (\d+\.\d)/.exec(text)?.[1] ?? 99) <= 8.8);
  }).toBe(true);
  for (const text of await cards.allInnerTexts()) {
    const speed = Number(/Speed (\d+\.\d)/.exec(text)![1]);
    // A blade whose layers are carbon or fibre (stated, or hinted by its name) is never a fast one for a beginner.
    if (/Carbon or fiber layers|Fiber layers|Inner |Outer /.test(text)) expect(speed).toBeLessThan(8.5);
  }
});

test("Pro setups link a pro's blade to its blade entry only when the exact blade exists", async ({ page }) => {
  await page.goto("/pros");
  await page.getByRole("searchbox", { name: "Player" }).fill("Timo Boll");
  const card = page.getByRole("article").first();
  await card.getByRole("link", { name: "Ratings and buy links" }).click();
  await expect(page).toHaveURL(/\/blades\/butterfly-timo-boll-alc$/);
  await expect(page.locator("main h1")).toHaveText("Butterfly Timo Boll ALC");
  await expect(page.locator("main")).toContainText("Source:");

  await page.goto("/pros");
  await page.getByRole("searchbox", { name: "Player" }).fill("Kuai Man");
  await expect(page.getByRole("article").first()).toBeVisible();
  await expect(page.getByRole("article").first().getByRole("link", { name: "Ratings and buy links" })).toHaveCount(0);
});
