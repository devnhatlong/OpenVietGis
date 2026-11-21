import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const runtimeEnv = loadEnv(mode, ".", "");
  const apiTarget =
    runtimeEnv.OPENVIETGIS_API_DEV_TARGET ?? "http://127.0.0.1:8000";

  return {
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
  };
});
