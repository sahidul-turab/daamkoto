import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The FastAPI backend runs on 127.0.0.1:8000. We proxy /api -> backend in dev
// so the frontend can use same-origin relative URLs (no CORS surprises).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // recharts is a large dependency; it's lazy-loaded (see ProductDrawer) so it
    // never hits the initial bundle. Raise the warning ceiling accordingly.
    // three.js (253 kB gz) is lazy-loaded in its own chunk; it never touches the Browse
    // critical path. Silence the size warning for this intentionally large vendor chunk.
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          charts: ["recharts"],
          motion: ["framer-motion"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
});
