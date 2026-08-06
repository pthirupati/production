import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Rapier (@react-three/rapier) ships a WASM module — ensure Vite emits it
  // in production builds so Physics does not 404 and kill the 3D hall.
  assetsInclude: ['**/*.wasm'],
  optimizeDeps: {
    exclude: ['@dimforge/rapier3d-compat'],
  },
  test: {
    // Default stays `node`: 7 existing .test.js suites read their own source
    // via `new URL('./X.jsx', import.meta.url)`, and under jsdom import.meta.url
    // is an http:// URL, so those fs.readFile calls throw "URL must be of
    // scheme file". api/client.test.js also asserts on a raw window.location.href
    // string that a real jsdom Location would resolve to an absolute URL.
    environment: 'node',
    // ...but a .test.jsx is rendering a component and needs a DOM. Defaulting
    // those to jsdom stops a new .test.jsx from silently landing in `node` and
    // failing on a missing `document`. Every .test.jsx today already carries an
    // explicit jsdom pragma, so this changes no current behavior — it only sets
    // the default for the next one. Per-file pragmas still win over this.
    environmentMatchGlobs: [['**/*.test.jsx', 'jsdom']],
    include: ['src/**/*.test.{js,jsx}'],
  },

  server: {
    host: true,
    port: 5173,

    allowedHosts: [
      "localhost",
      "127.0.0.1"
    ],

    proxy: {
      "/api": {
        target: "http://backend:8000",
        changeOrigin: true
      },
      "/ws": {
        target: "ws://backend:8000",
        ws: true,
        changeOrigin: true
      },
      "/media": {
        target: "http://backend:8000",
        changeOrigin: true
      }
    }
  },

  build: {
    outDir: "dist",
    rollupOptions: {
      output: {
        // Isolate AWS console + shared lab chrome so lazy AwsLabOverlay never
        // side-imports the LabRunner page module (circular init → lab crash).
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (
              id.includes("react-dom")
              || id.includes("/react/")
              || id.includes("react-router")
            ) {
              return "vendor";
            }
            // Keep lucide in its own chunk. Measured 2026-08-09: dropping this
            // rule does NOT shrink the eager path (656.1kB → 656.5kB gzip) —
            // the icons just migrate into `lab-shared`, which is preloaded too,
            // taking it from 27kB to 904kB. The 877kB is eager because
            // `aws-console`/`lab-shared` are still statically reachable from the
            // entry, not because of this rule. Fix that reachability first;
            // splitting here only moves bytes between eager chunks.
            if (id.includes("lucide-react")) return "icons";
            if (id.includes("zustand") || id.includes("axios")) return "state";
            return undefined;
          }
          // MUST come before the aws-console rule. These three are reachable
          // from the entry (main → App → authStore / api/scenarios /
          // userScopedStorage) AND imported by components/aws/**. Without an
          // explicit home Rollup folds them into whichever chunk claims them
          // first — `aws-console` — so the entry ended up importing
          // aws-console, and Vite preloaded all 1.19MB of it on first paint.
          // No static import of components/aws/ exists anymore (awsSimLifecycle
          // made it dynamic); the preload was purely this grouping artifact.
          // Measured 2026-08-09: eager preload 877kB → 545kB gzip, i.e. the
          // 332.85kB aws-console chunk leaves the critical path entirely.
          if (
            id.includes("/src/store/authStore")
            || id.includes("/src/api/scenarios")
            || id.includes("/src/utils/userScopedStorage")
          ) {
            return "app-shared";
          }
          if (id.includes("/src/components/aws/")) return "aws-console";
          if (id.includes("/src/api/labs")) return "labs-api";
          if (
            id.includes("/src/components/lab/")
            || id.includes("/src/utils/simLayout")
            || id.includes("/src/store/labStore")
            || id.includes("/src/utils/lazyWithRetry")
          ) {
            return "lab-shared";
          }
          return undefined;
        },
      },
    },
  }
});
