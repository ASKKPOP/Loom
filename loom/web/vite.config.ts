/// <reference types="node" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server proxies /v1/* to loom-gateway (which proxies to vMLX).
// LOOM_GATEWAY_URL env var overrides the default for cross-host setups.
const gateway = process.env.LOOM_GATEWAY_URL || "http://127.0.0.1:8080";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/v1": { target: gateway, changeOrigin: true },
      "/health": { target: gateway, changeOrigin: true },
      "/api": { target: gateway, changeOrigin: true },
    },
  },
});
