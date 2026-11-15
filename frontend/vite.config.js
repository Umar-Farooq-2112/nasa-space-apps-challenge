import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: npm run dev (port 5173) forwards /api to the Python server on 8000.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
});
