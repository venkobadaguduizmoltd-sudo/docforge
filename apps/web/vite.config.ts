import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    // Cursor Try Live / VM proxy hostnames (*.cursorvm.com)
    allowedHosts: [".cursorvm.com", "localhost", "127.0.0.1"],
    // Same-origin API in browser: Try Live only exposes the Vite host publicly.
    proxy: {
      "/auth": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/admin": { target: "http://127.0.0.1:8000", changeOrigin: true },

      "/jobs": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/documents": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/templates": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/repos": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/docs": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/openapi.json": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
