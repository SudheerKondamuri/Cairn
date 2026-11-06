import { expect, type Page } from "@playwright/test";
export const serviceKey = "cairn-e2e-service-key-local-tests-only";
export async function login(
  page: Page,
  subject = `test-${crypto.randomUUID()}`,
) {
  const r = await page.request.post("http://127.0.0.1:8181/api/web/sessions", {
    headers: { "X-Cairn-API-Key": serviceKey },
    data: { provider: "github", subject },
  });
  expect(r.status()).toBe(201);
  const { token } = await r.json();
  await page
    .context()
    .addCookies([
      {
        name: "cairn_session",
        value: token,
        domain: "127.0.0.1",
        path: "/",
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);
  return token;
}
