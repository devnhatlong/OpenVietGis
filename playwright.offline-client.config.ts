import { defineConfig } from "@playwright/test";
import { execPath } from "node:process";

// Independent client test: all API responses are intercepted synthetic fixtures.
// No live DB, identity provider, production endpoint or customer data.
export default defineConfig({
  testDir: "./tests/offline-client",
  workers: 1,
  timeout: 60_000,
  reporter: [["list"], ["json", {outputFile:"dist/remediation-r013/offline-browser.json"}]],
  use: {baseURL:"http://127.0.0.1:5184", serviceWorkers:"allow", trace:"off"},
  webServer: {
    command: `"${execPath}" tests/offline-client/static-server.mjs`,
    url:"http://127.0.0.1:5184/index.html", reuseExistingServer:false, timeout:20_000
  }
});
