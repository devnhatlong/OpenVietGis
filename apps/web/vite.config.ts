import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const nodeProcess = (globalThis as typeof globalThis & {
  process?: { env?: Record<string, string | undefined> };
}).process;
const apiTarget = nodeProcess?.env?.OPENVIETGIS_VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: false
      }
    }
  },
  preview: {
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: false
      }
    }
  },
  test: {
    environment: "node"
  }
});
