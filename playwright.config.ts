import { defineConfig } from "@playwright/test";
import { execPath } from "node:process";

export function makeConfig(bootstrap = false) {
  const apiPort = process.env.OVG_E2E_API_PORT ?? "8000";
  const webPort = process.env.OVG_E2E_WEB_PORT ?? "5178";
  const keycloakPort = process.env.OVG_E2E_KEYCLOAK_PORT ?? "18080";
  const apiUrl = "http://127.0.0.1:" + apiPort;
  const webUrl = "http://127.0.0.1:" + webPort;
  const keycloakUrl = "http://127.0.0.1:" + keycloakPort;

  return defineConfig({
    testDir: "./tests/e2e",
    ...(bootstrap
      ? { testMatch: "**/bootstrap-service-identity.spec.ts" }
      : { testIgnore: "**/bootstrap-service-identity.spec.ts" }),
    workers: 1,
    timeout: 45_000,
    reporter: [
      ["list"],
      [
        "json",
        {
          outputFile: bootstrap
            ? "dist/security-evidence/playwright-bootstrap.json"
            : "dist/security-evidence/playwright-p1.json"
        }
      ]
    ],
    use: {
      baseURL: webUrl,
      trace: "off"
    },
    webServer: [
      {
        command:
          "docker compose -f infra/dev/compose.yaml -f infra/dev/compose.identity.yaml up keycloak",
        url:
          keycloakUrl +
          "/realms/openvietgis/.well-known/openid-configuration",
        reuseExistingServer: true,
        timeout: 120_000
      },
      {
        command:
          "uv run --project apps/api python -m tools.seed_identity_e2e" +
          (bootstrap ? " --uninitialized" : "") +
          " && uv run --project apps/api uvicorn openvietgis_api.main:app " +
          "--app-dir apps/api --host 127.0.0.1 --port " +
          apiPort +
          " --no-access-log",
        url: apiUrl + "/api/v1/health/ready",
        reuseExistingServer: false,
        timeout: 60_000,
        env: {
          OPENVIETGIS_ENVIRONMENT: "test",
          OPENVIETGIS_DATABASE_URL:
            "postgresql+psycopg://openvietgis:openvietgis@127.0.0.1:54330/openvietgis_test",
          OPENVIETGIS_TEST_DATABASE_URL:
            "postgresql+psycopg://openvietgis:openvietgis@127.0.0.1:54330/openvietgis_test",
          OPENVIETGIS_MIGRATION_DATABASE_URL:
            "postgresql+psycopg://openvietgis:openvietgis@127.0.0.1:54330/openvietgis_test",
          OPENVIETGIS_RUNTIME_DATABASE_URL:
            "postgresql+psycopg://openvietgis_runtime:openvietgis-runtime-dev@127.0.0.1:54330/openvietgis_test",
          OPENVIETGIS_APPLICATION_SESSION_SECRET:
            "openvietgis-test-session-secret",
          OPENVIETGIS_CSRF_SECRET: "openvietgis-test-csrf-secret",
          OPENVIETGIS_BOOTSTRAP_SECRET: "openvietgis-test-bootstrap-secret",
          OPENVIETGIS_WEB_BASE_URL: webUrl,
          OPENVIETGIS_API_PUBLIC_BASE_URL: apiUrl,
          OPENVIETGIS_SESSION_COOKIE_SECURE: "false",
          OPENVIETGIS_OIDC_PROVIDERS: JSON.stringify({
            keycloak: {
              issuer: keycloakUrl + "/realms/openvietgis",
              client_id: "openvietgis-web",
              display_name: "OpenVietGIS Development"
            }
          })
        }
      },
      {
        command:
          `"${execPath}" node_modules/vite/bin/vite.js build && "${execPath}" node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port ${webPort} --strictPort`,
        cwd: "./apps/web",
        url: webUrl + "/api/v1/health/ready",
        reuseExistingServer: false,
        timeout: 60_000,
        env: {
          OPENVIETGIS_API_DEV_TARGET: apiUrl
        }
      }
    ]
  });
}

export default makeConfig();
