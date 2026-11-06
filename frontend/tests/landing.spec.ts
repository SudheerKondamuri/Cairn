import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import vulnerable from "../public/evidence/northstar-vulnerable.json";
import patched from "../public/evidence/northstar-patched.json";

test("recorded comparison preserves each report's evidence and downloads", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Security claims.Meet reality.",
  );
  await page.getByRole("link", { name: "See it investigate" }).click();
  await expect(page).toHaveURL(/#investigation$/);
  await expect(
    page.getByRole("heading", { name: "Command injection verified" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "View provenance" }).click();
  await expect(page.locator(".provenance")).toContainText(
    vulnerable.evidence.source_hash,
  );
  await page.getByRole("tab", { name: "Patched" }).click();
  await expect(
    page.getByRole("heading", { name: "Claim not reproduced" }),
  ).toBeVisible();
  await expect(page.locator(".provenance")).toContainText(
    patched.evidence.source_hash,
  );
  await expect(page.locator(".observations")).toContainText("Not triggered");
  await expect(page.locator(".source-code")).toContainText("shell=False");
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download the evidence" }).click();
  expect((await download).suggestedFilename()).toBe("northstar-patched.json");
  await page.getByRole("tab", { name: "Patched" }).focus();
  await page.keyboard.press("ArrowLeft");
  await expect(page.getByRole("tab", { name: "Vulnerable" })).toBeFocused();
  await expect(
    page.getByRole("heading", { name: "Command injection verified" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("page has no horizontal overflow or automated accessibility violations", async ({
  page,
}) => {
  await page.goto("/");
  await page.evaluate(() => document.fonts.ready);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
  await page.getByRole("tab", { name: "Patched" }).click();
  const patchedResults = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(patchedResults.violations).toEqual([]);
});

test("navigation and reduced-motion content remain usable", async ({
  page,
}, info) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  if (info.project.name === "mobile") {
    await page.getByRole("button", { name: "Open navigation" }).click();
    await expect(
      page.getByRole("navigation", { name: "Mobile navigation" }),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Open navigation" }),
    ).toBeFocused();
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page
      .getByRole("navigation", { name: "Mobile navigation" })
      .getByRole("link", { name: "How it works" })
      .click();
    await expect(
      page.getByRole("navigation", { name: "Mobile navigation" }),
    ).toBeHidden();
  } else {
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "How it works" })
      .click();
  }
  await expect(page).toHaveURL(/#how-it-works$/);
  await expect(
    page.getByRole("heading", { name: "Curiosity, with boundaries." }),
  ).toBeVisible();
});

test("hero typography and artwork remain separate between breakpoints", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "desktop");
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const width of [320, 390, 600, 650, 768, 820, 1024, 1280, 1440, 1920]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    await page.evaluate(() => document.fonts.ready);
    await expect(page.locator(".hero h1")).toBeVisible();
    await expect
      .poll(() =>
        page
          .locator(".hero h1")
          .evaluate(
            (n) =>
              n.getBoundingClientRect().height /
              parseFloat(getComputedStyle(n).lineHeight),
          ),
      )
      .toBeCloseTo(2, 1);
    const layout = await page.evaluate(() => {
      const heading = document.querySelector(".hero h1")!;
      const description = document
        .querySelector(".hero-description")!
        .getBoundingClientRect();
      const art = document.querySelector(".hero-art")!.getBoundingClientRect();
      const sculpture = document
        .querySelector(".sculpture-wrap")!
        .getBoundingClientRect();
      const lineHeight = parseFloat(getComputedStyle(heading).lineHeight);
      return {
        width: innerWidth,
        scroll: document.documentElement.scrollWidth,
        lines: heading.getBoundingClientRect().height / lineHeight,
        textRight: description.right,
        artLeft: art.left,
        artTop: art.top,
        textBottom: description.bottom,
        sculptureLeft: sculpture.left,
      };
    });
    expect(layout.scroll, `overflow at ${width}`).toBeLessThanOrEqual(width);
    expect(
      layout.lines,
      `headline should occupy two lines at ${width}`,
    ).toBeCloseTo(2, 1);
    if (width > 600) {
      expect(
        layout.textRight,
        `text enters artwork at ${width}`,
      ).toBeLessThanOrEqual(layout.artLeft);
      expect(layout.sculptureLeft).toBeGreaterThanOrEqual(layout.artLeft);
    } else expect(layout.textBottom).toBeLessThan(layout.artTop);
    if (width <= 900) {
      await page.getByRole("button", { name: "Open navigation" }).click();
      await expect(
        page
          .getByRole("navigation", { name: "Mobile navigation" })
          .getByRole("link", { name: "Open workspace" }),
      ).toHaveAttribute("href", "/operator");
    }
  }
});
