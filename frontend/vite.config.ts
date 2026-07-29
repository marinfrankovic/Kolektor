import react from "@vitejs/plugin-react";
import { copyFileSync, mkdirSync } from "node:fs";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// The world map is bundled so the app also works on a LAN with no internet access.
function bundleWorldAtlas() {
  return {
    name: "bundle-world-atlas",
    buildStart() {
      mkdirSync("public/geo", { recursive: true });
      copyFileSync(
        "node_modules/world-atlas/countries-110m.json",
        "public/geo/countries-110m.json",
      );
    },
  };
}

export default defineConfig({
  plugins: [
    react(),
    bundleWorldAtlas(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "Kolektor",
        short_name: "Kolektor",
        description: "Coin and banknote collection manager",
        theme_color: "#12181f",
        background_color: "#12181f",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
          {
            src: "/icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
        share_target: {
          action: "/capture",
          method: "POST",
          enctype: "multipart/form-data",
          params: {
            files: [{ name: "file", accept: ["image/*"] }],
          },
        },
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,json}"],
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
        navigateFallbackDenylist: [/^\/api/],
        runtimeCaching: [
          {
            urlPattern: /\/api\/images\/.*\/(thumb|preview)$/,
            handler: "CacheFirst",
            options: {
              cacheName: "kolektor-images",
              expiration: { maxEntries: 500, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
    }),
  ],
  server: {
    port: 5174,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
