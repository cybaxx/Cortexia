import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./pages/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        sans: ['Manrope', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      colors: {
        border: "hsl(var(--bg-border) / 0.08)",
        input: "hsl(var(--bg-border) / 0.08)",
        ring: "hsl(var(--accent-adopt))",
        background: "hsl(var(--bg-deep))",
        foreground: "hsl(var(--text-primary))",
        'bg-deep': "hsl(var(--bg-deep))",
        'bg-surface': "hsl(var(--bg-surface))",
        'bg-elevated': "hsl(var(--bg-elevated))",
        'text-primary': "hsl(var(--text-primary))",
        'text-secondary': "hsl(var(--text-secondary))",
        'text-muted': "hsl(var(--text-muted))",
        'accent-strain': "hsl(var(--accent-strain))",
        'accent-adopt': "hsl(var(--accent-adopt))",
        'pastel-1': "hsl(var(--pastel-1))",
        'pastel-2': "hsl(var(--pastel-2))",
        'pastel-3': "hsl(var(--pastel-3))",
        'neutral-agent': "hsl(var(--neutral-agent))",
        primary: {
          DEFAULT: "hsl(var(--accent-adopt))",
          foreground: "hsl(var(--text-primary))",
        },
        secondary: {
          DEFAULT: "hsl(var(--bg-elevated))",
          foreground: "hsl(var(--text-primary))",
        },
        destructive: {
          DEFAULT: "hsl(var(--accent-strain))",
          foreground: "hsl(var(--text-primary))",
        },
        muted: {
          DEFAULT: "hsl(var(--bg-elevated))",
          foreground: "hsl(var(--text-secondary))",
        },
        accent: {
          DEFAULT: "hsl(var(--bg-elevated))",
          foreground: "hsl(var(--text-primary))",
        },
        popover: {
          DEFAULT: "hsl(var(--bg-surface))",
          foreground: "hsl(var(--text-primary))",
        },
        card: {
          DEFAULT: "hsl(var(--bg-surface))",
          foreground: "hsl(var(--text-primary))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--bg-surface))",
          foreground: "hsl(var(--text-primary))",
          primary: "hsl(var(--accent-adopt))",
          "primary-foreground": "hsl(var(--text-primary))",
          accent: "hsl(var(--bg-elevated))",
          "accent-foreground": "hsl(var(--text-primary))",
          border: "hsl(var(--bg-border) / 0.08)",
          ring: "hsl(var(--accent-adopt))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: {
            height: "0",
          },
          to: {
            height: "var(--radix-accordion-content-height)",
          },
        },
        "accordion-up": {
          from: {
            height: "var(--radix-accordion-content-height)",
          },
          to: {
            height: "0",
          },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
