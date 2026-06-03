import type { Config } from "tailwindcss";

// MOEI palette (matched from moei.gov.ae screenshots May 2026):
// - bronze accent (golden-olive) on a near-white background
// - deep near-black headings and body text
// - subtle warm-grey lines/borders
// - hover state: soft cream fill on cards
const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        moei: {
          bronze: "#9c8853",
          "bronze-dark": "#7a6a3f",
          "bronze-light": "#c4b485",
          cream: "#fff8eb",          // card hover fill
          sand: "#faf6ee",           // soft section bg
          "ink": "#0a0a0a",          // headings (near-black, MOEI is very dark)
          "ink-2": "#1a1a1a",
          body: "#262626",           // body copy (darker than before)
          muted: "#6b6b6b",
          line: "#e7dfd0",
          "line-soft": "#f0ebe0",
        },
        uae: {
          red: "#EF3340",
          green: "#009639",
          black: "#000000",
          white: "#FFFFFF",
        },
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
      },
      fontFamily: {
        // MOEI is sans-only — single sans family across the site
        sans: ["var(--font-sans)", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        arabic: ["var(--font-arabic)", "Noto Sans Arabic", "sans-serif"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 8px)",
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      boxShadow: {
        // Soft, low elevation — MOEI cards are flat, just a hint
        "moei-card": "0 1px 2px rgba(0,0,0,0.04)",
        "moei-card-hover": "0 4px 16px rgba(156, 136, 83, 0.18)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
