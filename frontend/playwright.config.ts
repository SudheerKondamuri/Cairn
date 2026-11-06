import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  fullyParallel: true,
  workers: 2,
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure" },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    command: "node tests/support/start-stack.mjs",
    url: "http://127.0.0.1:3100",
    reuseExistingServer: false,
    env: {
      CAIRN_APP_ORIGIN: "http://127.0.0.1:3100",
      CAIRN_API_URL: "http://127.0.0.1:8181",
      CAIRN_API_KEY: "cairn-e2e-service-key-local-tests-only",

    },
    timeout: 60_000,
  },
});
