import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API calls to the FastAPI backend so the gallery can call
// /g/... and /internal-free endpoints without CORS friction during development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/g": "http://localhost:8000",
    },
  },
});
