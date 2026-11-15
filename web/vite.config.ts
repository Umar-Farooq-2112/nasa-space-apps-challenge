import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The build goes straight into ../public: FastAPI serves it locally, Vercel's CDN serves it in production.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../public", emptyOutDir: true },
  server: { proxy: { "/api": "http://localhost:8000" } },
});
