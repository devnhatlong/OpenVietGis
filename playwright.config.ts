import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:5178",
    trace: "retain-on-failure"
  },
  webServer: [
    {
      command:
        "uv run --project apps/api uvicorn openvietgis_api.main:app --app-dir apps/api --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/v1/health/live",
      reuseExistingServer: false,
      timeout: 60_000
    },
    {
      command:
        "pnpm --filter @openvietgis/web exec vite --host 127.0.0.1 --port 5178",
      url: "http://127.0.0.1:5178",
      reuseExistingServer: false,
      timeout: 60_000
    }
  ]
});