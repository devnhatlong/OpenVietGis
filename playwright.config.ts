import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 45_000,
  use: {
    baseURL: "http://127.0.0.1:5178",
    trace: "off"
  },
  webServer: [
    {
      command:
        "docker compose -f infra/dev/compose.yaml -f infra/dev/compose.identity.yaml up keycloak",
      url: "http://127.0.0.1:18080/realms/openvietgis/.well-known/openid-configuration",
      reuseExistingServer: true,
      timeout: 120_000
    },
    {
      command:
        "uv run --project apps/api python -m tools.seed_identity_e2e && " +
        "uv run --project apps/api uvicorn openvietgis_api.main:app " +
        "--app-dir apps/api --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/v1/health/live",
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        OPENVIETGIS_WEB_BASE_URL: "http://127.0.0.1:5178"
      }
    },
    {
      command:
        "corepack pnpm --filter @openvietgis/web exec vite --host 127.0.0.1 --port 5178",
      url: "http://127.0.0.1:5178",
      reuseExistingServer: false,
      timeout: 60_000
    }
  ]
});
