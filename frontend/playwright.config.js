import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60000,
  expect: {
    timeout: 10000
  },
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:5173",
    headless: true,
    trace: "off",
    screenshot: "only-on-failure",
    video: "off"
  },
  webServer: {
    command: "npm.cmd run dev",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 120000
  }
});
