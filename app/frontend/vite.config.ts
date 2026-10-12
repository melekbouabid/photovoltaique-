import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En développement, les appels /api et les téléchargements /donnees sont relayés vers le backend FastAPI (port 8000).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000", "/donnees": "http://127.0.0.1:8000" } },
});
