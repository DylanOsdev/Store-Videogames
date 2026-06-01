/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Config de Vitest separada de astro.config.mjs para no interferir con el
// build de Astro. Usa el plugin de React (JSX/TSX) y jsdom para los tests de
// componentes y stores que tocan el DOM / localStorage.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // Solo nuestros tests; nada de node_modules ni el build.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
