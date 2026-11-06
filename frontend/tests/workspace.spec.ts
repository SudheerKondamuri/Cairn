import { login, serviceKey } from "./support/login";
import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
async function accessible(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}
for (const path of [
  "/investigations",
  "/investigations/northstar-vulnerable",
  "/guide",
  "/operator/sign-in",
]) {
  test(`public screen is readable and keyboard discoverable: ${path}`, async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(path);
    await accessible(page);
    expect(errors).toEqual([]);
  });
}
test("published cases filter, recover an empty search, and expose real requests", async ({
  page,
}) => {
  await page.goto("/investigations");
  await page
    .getByRole("textbox", { name: "Search published investigations" })
    .fill("absent-case");
  await expect(
    page.getByRole("heading", { name: "No matching investigations" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await page
    .getByRole("combobox", { name: "Filter verdict" })
    .selectOption("not_reproduced");
  await expect(page.locator(".case-row")).toHaveCount(1);
  await page.locator(".case-row").click();
  await expect(
    page.getByRole("heading", { name: "Not reproduced", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Requests (4)" }).click();
  await page.getByRole("button", { name: "Request 2 No marker" }).click();
  await expect(page.locator(".attempt-detail")).toContainText(
    "/api/v1/diagnostics/resolve",
  );
  await page.getByRole("button", { name: "Source & provenance" }).click();
  await expect(
    page.getByText("No independent positive recheck is recorded.", {
      exact: false,
    }),
  ).toBeVisible();
  await accessible(page);
});

test("account session protects private routes and sign-out revokes it", async ({
  page,
}) => {
  expect(
    (await page.request.get("/api/operator/investigations")).status(),
  ).toBe(401);
  await page.goto("/operator");
  await expect(page).toHaveURL(/sign-in/);
  await login(page);
  await page.goto("/operator");
  await expect(page.getByText("3 of 3 investigations available")).toBeVisible();
  expect(
    (
      await page.request.post("/api/operator/allowance-request", {
        headers: { Origin: "https://untrusted.example" },
      })
    ).status(),
  ).toBe(403);
  if (!(await page.getByRole("button", {name:"Sign out",exact:true}).isVisible())) await page.getByRole("button", {name:"Open workspace navigation"}).click();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/sign-in/);
  expect(
    (await page.request.get("/api/operator/investigations")).status(),
  ).toBe(401);
});
test("guided owned example queues, reports activity, cancels and refunds before execution", async ({
  page,
}) => {
  await login(page);
  await page.goto("/operator/investigations/new");
  await page
    .getByRole("button", { name: "Use the owned Northstar example" })
    .click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page
    .getByRole("checkbox", {
      name: "I own this source or have permission to investigate it.",
    })
    .check();
  await page.getByRole("button", { name: "Start investigation" }).click();
  await expect(page).toHaveURL(/operator\/investigations\/inv-/);
  await expect(
    page.getByText(
      "Accepted and queued for an isolated Celesto investigation.",
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Cancel investigation", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Investigation cancelled" }),
  ).toBeVisible();
  await page.goto("/operator");
  await expect(page.getByText("3 of 3 investigations available")).toBeVisible();
  await accessible(page);
});
test("completed report exports, shares, revokes, and remains isolated", async ({
  page,
}) => {
  await login(page);
  await page.goto("/operator/investigations/new");
  await page
    .getByRole("button", { name: "Use the owned Northstar example" })
    .click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page
    .getByRole("checkbox", {
      name: "I own this source or have permission to investigate it.",
    })
    .check();
  await page.getByRole("button", { name: "Start investigation" }).click();
  await expect(page).toHaveURL(/operator\/investigations\/inv-/);
  const id = page.url().split("/").pop()!;
  await page.request.post(`http://127.0.0.1:8181/api/test/complete/${id}`, {
    headers: { "X-Cairn-API-Key": serviceKey },
  });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Vulnerability verified", exact: true }),
  ).toBeVisible();
  const pdf = await page.request.get(`/api/operator/investigations/${id}/pdf`);
  expect(pdf.status()).toBe(200);
  expect((await pdf.body()).subarray(0, 4).toString()).toBe("%PDF");
  await page.getByRole("button", { name: "Share report", exact: true }).click();
  await page
    .getByRole("button", { name: "Create sharing link", exact: true })
    .click();
  const link = await page
    .getByLabel("Sharing link", { exact: true })
    .inputValue();
  await page
    .getByRole("button", { name: "Revoke sharing link", exact: true })
    .click();
  await expect(
    page.getByText("Sharing link revoked.", { exact: true }),
  ).toBeVisible();
  expect((await page.request.get(`${link}/download`)).status()).toBe(404);
  await page.goto(link);
  await expect(page.getByRole("heading",{name:/not found|missing|doesn.t exist|couldn.t find|path/i})).toBeVisible();
  await login(page);
  expect(
    (await page.request.get(`/api/operator/investigations/${id}`)).status(),
  ).toBe(404);
});
test("GitHub import fields, theme, and administrator controls are usable", async ({
  page,
}) => {
  await login(page, "browser-admin");
  await page.goto("/operator/investigations/new");
  await page.getByLabel("Source location").selectOption("github");
  await expect(page.getByLabel("Public repository URL")).toBeVisible();
  if (!(await page.getByRole("button",{name:"Use dark theme"}).isVisible())) await page.getByRole("button",{name:"Open workspace navigation"}).click();
  await page.getByRole("button", { name: "Use dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("link", { name: "Administration", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Trial operations." }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Pause submissions and queued work" }),
  ).toBeVisible();
});
