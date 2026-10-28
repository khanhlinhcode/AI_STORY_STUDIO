import { defineConfig } from "vitest/config";
import { fileURLToPath } from "url";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], exclude: ["tests/e2e/**", "node_modules/**"] },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
});

