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
        // Isolate AWS console so lazy AwsLabOverlay never side-imports the
        // LabRunner page module (circular init → lab crash). Lab chrome
        // (`components/lab/**`) is intentionally NOT forced into a manual
        // chunk: Rollup absorbs shared deps of manual chunks into them, which
        // made entry import `lab-shared` for helpers like reportClientError /
        // SimErrorBoundary (session 43). Let lab modules follow LabRunner.
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (
              id.includes("react-dom")
              || id.includes("/react/")
              || id.includes("react-router")
            ) {
              return "vendor";
            }
            // Keep lucide in its own chunk so tree-shaken icons from lazy routes
            // are not duplicated into every sim chunk. Eager layouts still
            // preload this (~155kB gzip9) until their lucide imports shrink —
            // residual W3 icons half.
            if (id.includes("lucide-react")) return "icons";
            if (id.includes("zustand") || id.includes("axios")) return "state";
            return undefined;
          }
          // MUST come before the aws-console rule. Modules reachable from the
          // entry AND imported by components/aws/** need an explicit home, or
          // Rollup folds them into aws-console and Vite preloads ~1.2MB on first
          // paint. Measured 2026-08-09: eager preload 877kB → 545kB gzip.
          if (
            id.includes("/src/store/authStore")
            || id.includes("/src/api/scenarios")
            || id.includes("/src/utils/userScopedStorage")
            || id.includes("/src/utils/lazyWithRetry")
            || id.includes("/src/store/labStore")
            || id.includes("/src/utils/reportClientError")
            || id.includes("/src/components/SimErrorBoundary")
          ) {
            return "app-shared";
          }
          if (id.includes("/src/components/aws/")) return "aws-console";
          if (id.includes("/src/api/labs")) return "labs-api";
          return undefined;
        },
      },
    },
  }
});
