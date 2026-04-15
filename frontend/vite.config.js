import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Proxy API requests to the FastAPI backend during local development so
      // the frontend can use simple relative URLs while we iterate quickly.
      "/health": "http://127.0.0.1:8000",
      "/weather": "http://127.0.0.1:8000",
    },
  },
});
