import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "../tests/e2e/ui",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "uvicorn src.bff.app:app --port 8000",
      port: 8000,
      reuseExistingServer: !process.env.CI,
      cwd: "..",
    },
    {
      command: "npx vite --port 5173",
      port: 5173,
      reuseExistingServer: !process.env.CI,
    },
  ],
  globalSetup: "../tests/e2e/ui/e2e-global-setup.ts",
});
