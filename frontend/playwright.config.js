import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 90000,
  expect: {
    timeout: 10000
  },
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    headless: true,
    trace: "off",
    screenshot: "only-on-failure",
    video: "off"
  },
  webServer: [
    {
      command: "python ..\\tests\\e2e_backend_server.py",
      url: "http://127.0.0.1:5000/",
      reuseExistingServer: false,
      timeout: 120000
    },
    {
      command: "npx.cmd vite --host 127.0.0.1 --port 4173",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: false,
      timeout: 120000
    }
  ]
});
