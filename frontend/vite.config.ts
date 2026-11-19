import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the API is proxied, so no CORS setup is needed: `npm run dev`.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
