import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The web app (this dev server, :5173) serves the gallery page at /g/{token}
// and calls the Solna API directly via VITE_API_BASE (default http://localhost:8000).
// They run on different ports, so there is no path collision on /g.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
