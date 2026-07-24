import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The FastAPI backend runs on 127.0.0.1:8000. We proxy /api -> backend in dev
// so the frontend can use same-origin relative URLs (no CORS surprises).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // three.js (~245 kB gz, the Build view's 3D rig) is lazy-loaded in its own
    // chunk and never touches the Browse critical path. Silence the size warning
    // for that intentionally large vendor chunk.
    chunkSizeWarningLimit: 1000,

    // No manualChunks here on purpose. Forcing recharts and framer-motion into
    // named chunks made Vite emit <link rel="modulepreload"> for both in
    // index.html, so a first-time visitor downloaded ~190 kB gzipped of chart
    // and animation code before any price rendered — even though nothing on the
    // browse view uses either. Every consumer of both now sits behind a lazy
    // import, so letting Rollup derive chunks from the actual import graph keeps
    // them out of the entry's preload set.
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
