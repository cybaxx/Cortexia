import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  // Bind IPv4 + IPv6 so `http://localhost` (often ::1) and `http://127.0.0.1` both hit Vite.
  // Avoids "not found" when another app only listened on one stack on the same port.
  server: {
    host: true,
    // Use default Vite port to avoid clashes with other tools (8080 is often in use on ::1 only).
    port: 5173,
    strictPort: true,
    hmr: {
      overlay: false,
    },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("mapbox-gl")) return "mapbox-gl";
          if (id.includes("react-map-gl") || id.includes("@deck.gl")) return "map-canvas";
          if (id.includes("recharts")) return "charts";
          if (id.includes("@radix-ui")) return "radix-ui";
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime", "@tanstack/react-query", "@tanstack/query-core"],
  },
}));
