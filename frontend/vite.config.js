import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  server: {
    host: true,        // allow external access (domain / IP)
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
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          icons: ['lucide-react'],
          state: ['zustand', 'axios'],
        },
      },
    },
  }
});
