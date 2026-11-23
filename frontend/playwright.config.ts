import { defineConfig } from "@playwright/test";

const baseURL = "http://127.0.0.1:3110";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL, browserName: "chromium", trace: "retain-on-failure" },
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3110",
    url: baseURL,
    env: { BACKEND_URL: "http://127.0.0.1:1", NEXT_PUBLIC_API_URL: "", DEMO_MODE: "0" },
    timeout: 120_000,
  },
});
