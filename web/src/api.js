// Base URL of the Solna API. In dev the web app (5173) and API (8080) are
// separate; in prod set VITE_API_BASE at build time.
export const API = import.meta.env.VITE_API_BASE || "http://localhost:8080";
