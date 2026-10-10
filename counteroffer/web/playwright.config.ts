import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  timeout: 20_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    channel: "chrome",
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "node tests/mock_api.cjs",
      url: "http://127.0.0.1:8000/test-state",
      reuseExistingServer: !process.env.CI,
      timeout: 10_000,
    },
    {
      command: "npm run dev -- --strictPort",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 20_000,
    },
  ],
});
