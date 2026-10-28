import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        canvas: "#f6f5f0",
        panel: "#fffdfa",
        teal: {500: "#0f9f8f", 600: "#0b8175"},
        coral: "#f06d4f",
      },
      boxShadow: { card: "0 12px 40px rgba(22, 31, 42, .08)" },
    },
  },
  plugins: [],
} satisfies Config;

