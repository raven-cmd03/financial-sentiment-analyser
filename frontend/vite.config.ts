/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig(({ mode }) => {
  // When running Vite on the Windows host, ``backend`` is not a resolvable
  // hostname — proxy requests must go to the published Docker port instead.
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget =
    env.VITE_DEV_API_PROXY || "http://127.0.0.1:8001";

  return {
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    // Bind-mounted source on Windows+Docker doesn't deliver inotify events,
    // so Vite misses every edit unless we fall back to polling. Without this,
    // the page silently runs stale code and "refresh" looks like it does
    // nothing. 1s interval is a fine tradeoff for a dev container.
    watch: {
      usePolling: true,
      interval: 1000,
    },
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
};
});
