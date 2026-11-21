import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  // Restrict preview proxy override to loopback. Test runners can isolate their
  // API port without accidentally targeting the live service on the default port.
  const environment = loadEnv(mode, ".", "");
  const rawApiPort = environment.OPENVIETGIS_API_PROXY_PORT ?? "8000";
  if (!/^\d{1,5}$/.test(rawApiPort) || Number(rawApiPort) < 1 || Number(rawApiPort) > 65535) {
    throw new Error("OPENVIETGIS_API_PROXY_PORT must be a valid loopback port");
  }
  const apiTarget = `http://127.0.0.1:${Number(rawApiPort)}`;
  return {
    plugins: [react()],
    server: { proxy: { "/api": { target: apiTarget, changeOrigin: false } } },
    preview: { proxy: { "/api": { target: apiTarget, changeOrigin: false } } },
    test: { environment: "node" }
  };
});
