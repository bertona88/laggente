import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxy = {
    target: env.API_PROXY_TARGET || "http://127.0.0.1:8000",
    changeOrigin: false,
  };
  return {
    plugins: [react()],
    resolve: { alias: { "@": path.resolve(import.meta.dirname, ".") } },
    server: {
      host: "0.0.0.0",
      port: 3000,
      strictPort: true,
      proxy: {
        "/api/v1": apiProxy,
      },
    },
    preview: {
      host: "0.0.0.0",
      port: 4173,
      strictPort: true,
      proxy: { "/api/v1": apiProxy },
    },
    build: { outDir: "dist", sourcemap: false },
  };
});
