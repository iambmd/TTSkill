import { expect, test } from "@playwright/test";

const pages = [
  ["/", "Highlights and coaching"],
  ["/autocut", "Cut the dead time."],
  ["/breakdown", "Swing like the pros."],
  ["/coach", "Ask your coach."],
  ["/match", "Who do you play like?"],
  ["/pros", "What the pros use"],
  ["/rubbers", "Pick your rubber"],
  ["/jobs/demo-autocut", /rallies/i],
  ["/jobs/demo-breakdown", /backspin/i],
  ["/jobs/demo-coach", /fix my forehand/i],
  ["/jobs/demo-match", /you play like/i],
] as const;

for (const viewport of [{ width: 1440, height: 900 }, { width: 375, height: 844 }]) {
  const mobile = viewport.width === 375;
  for (const theme of ["dark", "light"] as const) {
    test.describe(`${viewport.width}px ${theme}`, () => {
      test.use({ viewport, hasTouch: mobile, isMobile: mobile, colorScheme: theme });

      test.beforeEach(async ({ page }) => {
        await page.addInitScript(theme => localStorage.setItem("ttskill-theme", theme), theme);
        // Shop and Wikipedia assets can be unavailable in CI. Serve deterministic third-party responses.
        await page.route("https://**/*", route => route.request().resourceType() === "image"
          ? route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" />' })
          : route.fulfill({ json: {}, headers: { "access-control-allow-origin": "*" } }));
      });

      for (const [path, heading] of pages) {
        test(`${path} works with analysis offline`, async ({ page }) => {
          const errors: string[] = [];
          page.on("pageerror", error => errors.push(error.message));
          page.on("console", message => {
            if (message.type() === "error" || message.type() === "warning") errors.push(message.text());
          });
          page.on("response", response => {
            if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`);
          });
          page.on("requestfailed", request => {
            const reason = request.failure()?.errorText;
            if (reason !== "net::ERR_ABORTED") errors.push(`${reason} ${request.url()}`);
          });

          expect((await page.goto(path))?.ok()).toBe(true);
          await expect(page.locator("main h1")).toHaveText(heading);
          await expect(page.getByRole("button", { name: `Switch to ${theme === "light" ? "dark" : "light"} mode` })).toBeVisible();
          if (path === "/") await expect(page.locator("main").getByRole("alert")).toContainText("Live analysis is offline");
          if (path === "/rubbers") await expect(page.locator("main ol li").first()).toBeVisible();

          await page.keyboard.press("Tab");
          const skip = page.getByRole("link", { name: "Skip to main content" });
          await expect(skip).toBeFocused();
          await expect(skip).toHaveCSS("outline-style", "solid");
          expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0);

          const cursor = mobile ? "auto" : /paddle-cursor\.svg.*12 11, auto/;
          await expect(page.locator("body")).toHaveCSS("cursor", cursor);
          if (!mobile && path === "/coach") {
            await expect(page.getByLabel("What do you want?")).toHaveCSS("cursor", "text");
            const coach = page.getByRole("navigation", { name: "Site navigation" }).getByRole("link", { name: "Coach" });
            await expect(coach).toHaveCSS("cursor", "pointer");
            await coach.focus();
            await expect(coach).toHaveCSS("outline-offset", "-2px");
          }
          expect(errors).toEqual([]);
        });
      }
    });
  }
}
