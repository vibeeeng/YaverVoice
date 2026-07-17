import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "desktop/renderer",
  plugins: [react()],
  base: "./",
  html: {
    cspNonce: "yavervoice-renderer"
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true
  },
  build: {
    outDir: "../dist/renderer",
    emptyOutDir: true
  }
});
