import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'node',
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
            if (id.includes("lucide-react")) return "icons";
            if (id.includes("zustand") || id.includes("axios")) return "state";
            return undefined;
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
