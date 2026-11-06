import { login } from "./support/login";
import { expect, test } from "@playwright/test";
import { mkdir } from "node:fs/promises";
test("capture the finished surfaces at desktop, tablet, and phone sizes", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "desktop");
  test.setTimeout(90_000);
  await mkdir("../.impeccable/review/workspace", { recursive: true });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  for (const width of [1440, 768, 390]) {
    await page.context().clearCookies();
    await page.setViewportSize({ width, height: 1000 });
    for (const [name, url] of [
      ["landing", "/"],
      ["catalog", "/investigations"],
      ["report", "/investigations/northstar-vulnerable"],
      ["guide", "/guide"],
      ["signin", "/operator/sign-in"],
    ]) {
      await page.goto(url);
      await page.evaluate(() => document.fonts.ready);
      if (name === "landing")
        await page
          .locator(".sculpture")
          .evaluate((n) => (n as HTMLImageElement).decode());
      await page.screenshot({
        path: `../.impeccable/review/workspace/${name}-${width}.png`,
        fullPage: true,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        JSON.stringify(
          await page
            .locator(
              ".workspace-body,.workspace-main,.workspace-footer,.table-scroll,.filter-bar,.lookup-panel",
            )
            .evaluateAll((nodes) =>
              nodes.map((n) => ({
                cls: n.className,
                width: n.getBoundingClientRect().width,
                scroll: n.scrollWidth,
                right: n.getBoundingClientRect().right,
              })),
            ),
        ),
      ).toBe(true);
    }
    await login(page);
    for (const [name, url] of [
      ["operator", "/operator"],
      ["submission", "/operator/investigations/new"],
    ]) {
      await page.goto(url);
      if (name === "operator")
        await expect(page.getByRole("heading", {name:"Your investigations"})).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      if (name === "landing")
        await page
          .locator(".sculpture")
          .evaluate((n) => (n as HTMLImageElement).decode());
      await page.screenshot({
        path: `../.impeccable/review/workspace/${name}-${width}.png`,
        fullPage: true,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        JSON.stringify(
          await page
            .locator(
              ".workspace-body,.workspace-main,.workspace-footer,.table-scroll,.filter-bar,.lookup-panel",
            )
            .evaluateAll((nodes) =>
              nodes.map((n) => ({
                cls: n.className,
                width: n.getBoundingClientRect().width,
                scroll: n.scrollWidth,
                right: n.getBoundingClientRect().right,
              })),
            ),
        ),
      ).toBe(true);
    }
  }
  expect(errors).toEqual([]);
});
