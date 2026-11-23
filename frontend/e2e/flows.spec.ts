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
  await expect(page).toHaveURL(/\/rubbers\?style=speed&level=advanced$/);
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
